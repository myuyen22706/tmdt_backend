from datetime import datetime, timezone
from typing import Any, Dict, List
from xml.sax.saxutils import escape as xml_escape
from fastapi import APIRouter, Depends, HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_db
from app.core.responses import APIResponse
from app.modules.seo.schemas import (
    BreadcrumbItem,
    OrganizationSEOMeta,
    ProductSEOMeta,
)

router = APIRouter(prefix="/seo", tags=["Search Engine Optimization & Structured Data (F24)"])

BASE_URL = "https://daitrang.vn"


@router.get("/sitemap.xml", response_class=Response)
async def generate_sitemap(db: AsyncIOMotorDatabase = Depends(get_db)):
    """F24: Sinh tệp sitemap.xml động chứa toàn bộ URL sản phẩm, danh mục và bài viết.
    Tuân thủ giao thức chuẩn của Sitemaps.org XML Schema.
    """
    products_col = db["products"]
    categories_col = db["categories"]
    martial_arts_col = db["martial_arts"]
    blog_col = db["blog_posts"]
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    urls = [
        {"loc": f"{BASE_URL}/", "lastmod": now_iso, "changefreq": "daily", "priority": "1.0"},
        {"loc": f"{BASE_URL}/about", "lastmod": now_iso, "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{BASE_URL}/size-guide", "lastmod": now_iso, "changefreq": "monthly", "priority": "0.8"},
        {"loc": f"{BASE_URL}/contact", "lastmod": now_iso, "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{BASE_URL}/dojos", "lastmod": now_iso, "changefreq": "weekly", "priority": "0.8"},
    ]

    # Môn võ
    martial_arts = await martial_arts_col.find({}).to_list(length=50)
    for ma in martial_arts:
        slug = ma.get("slug") or ma.get("id")
        urls.append({
            "loc": f"{BASE_URL}/martial-arts/{slug}",
            "lastmod": now_iso,
            "changefreq": "weekly",
            "priority": "0.8",
        })

    # Danh mục
    categories = await categories_col.find({}).to_list(length=50)
    for cat in categories:
        slug = cat.get("slug") or cat.get("id")
        urls.append({
            "loc": f"{BASE_URL}/categories/{slug}",
            "lastmod": now_iso,
            "changefreq": "weekly",
            "priority": "0.8",
        })

    # Toàn bộ sản phẩm đang hoạt động
    products = await products_col.find({"is_active": True}).to_list(length=1000)
    for prod in products:
        slug = prod.get("slug") or prod.get("id")
        updated_at = prod.get("updated_at")
        lastmod = updated_at.strftime("%Y-%m-%d") if updated_at else now_iso
        urls.append({
            "loc": f"{BASE_URL}/products/{slug}",
            "lastmod": lastmod,
            "changefreq": "daily",
            "priority": "0.9",
        })

    # Bài viết blog nếu có
    articles = await blog_col.find({"is_published": True}).to_list(length=200)
    for art in articles:
        slug = art.get("slug") or art.get("id")
        urls.append({
            "loc": f"{BASE_URL}/blog/{slug}",
            "lastmod": now_iso,
            "changefreq": "weekly",
            "priority": "0.7",
        })

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for u in urls:
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{xml_escape(u['loc'])}</loc>")
        xml_lines.append(f"    <lastmod>{u['lastmod']}</lastmod>")
        xml_lines.append(f"    <changefreq>{u['changefreq']}</changefreq>")
        xml_lines.append(f"    <priority>{u['priority']}</priority>")
        xml_lines.append("  </url>")
    xml_lines.append("</urlset>")

    xml_content = "\n".join(xml_lines)
    return Response(content=xml_content, media_type="application/xml")


@router.get("/robots.txt", response_class=Response)
async def generate_robots_txt():
    """F24: Cung cấp tệp robots.txt quy chuẩn hướng dẫn trình thu thập thông tin (Googlebot, Bingbot)."""
    content = f"""# Robots.txt for Đai Trắng Martial Arts E-commerce (F24)
User-agent: *
Allow: /
Allow: /products/
Allow: /categories/
Allow: /martial-arts/
Allow: /size-guide
Allow: /blog/
Allow: /about
Allow: /contact

# Chặn thu thập thông tin các trang quản trị, tài khoản riêng tư và thanh toán
Disallow: /admin/
Disallow: /api/
Disallow: /checkout/
Disallow: /cart/
Disallow: /me/
Disallow: /auth/

# Đường dẫn sitemap chính thức
Sitemap: {BASE_URL}/sitemap.xml
"""
    return Response(content=content, media_type="text/plain")


@router.get("/meta/product/{slug}", response_model=APIResponse[ProductSEOMeta])
async def get_product_seo_meta(
    slug: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F24: Lấy siêu dữ liệu SEO (Title, Description, Canonical, OG, Twitter Card) và dữ liệu có cấu trúc JSON-LD Schema.org cho sản phẩm."""
    products_col = db["products"]
    product = await products_col.find_one({"$or": [{"slug": slug}, {"id": slug}]})
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sản phẩm có slug '{slug}'",
        )

    name = product.get("name", "Võ phục")
    raw_desc = product.get("description", "")
    short_desc = raw_desc[:150] + "..." if len(raw_desc) > 150 else raw_desc or f"Mua {name} chất lượng cao tại Đai Trắng."
    price = int(product.get("price", 0))
    canonical_url = f"{BASE_URL}/products/{product.get('slug', slug)}"
    thumbnail = product.get("thumbnail") or "/images/default-gi.jpg"
    if not thumbnail.startswith("http"):
        image_url = f"{BASE_URL}{thumbnail}"
    else:
        image_url = thumbnail

    # Kiểm tra còn hàng
    variants = product.get("variants", [])
    total_stock = sum(int(v.get("stock", 0)) for v in variants)
    availability = (
        "https://schema.org/InStock" if total_stock > 0 else "https://schema.org/OutOfStock"
    )

    # 1. Schema.org Product
    product_schema = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": name,
        "image": [image_url],
        "description": short_desc,
        "sku": product.get("id", slug),
        "brand": {
            "@type": "Brand",
            "name": "Đai Trắng",
        },
        "offers": {
            "@type": "Offer",
            "url": canonical_url,
            "priceCurrency": "VND",
            "price": price,
            "priceValidUntil": "2027-12-31",
            "itemCondition": "https://schema.org/NewCondition",
            "availability": availability,
            "seller": {
                "@type": "Organization",
                "name": "Đai Trắng",
            },
        },
    }

    # 2. Schema.org BreadcrumbList
    martial_art_id = product.get("martial_art_id", "martial-arts")
    breadcrumbs = [
        BreadcrumbItem(name="Trang chủ", url=f"{BASE_URL}/"),
        BreadcrumbItem(name=f"Võ phục {martial_art_id.capitalize()}", url=f"{BASE_URL}/martial-arts/{martial_art_id}"),
        BreadcrumbItem(name=name, url=canonical_url),
    ]

    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": idx + 1,
                "name": b.name,
                "item": b.url,
            }
            for idx, b in enumerate(breadcrumbs)
        ],
    }

    combined_structured_data = {
        "@graph": [product_schema, breadcrumb_schema]
    }

    seo_meta = ProductSEOMeta(
        title=f"{name} - Võ Phục & Phụ Kiện Cao Cấp | Đai Trắng",
        description=short_desc,
        canonical_url=canonical_url,
        og_title=f"{name} | Đai Trắng",
        og_description=short_desc,
        og_image=image_url,
        og_type="product",
        twitter_card="summary_large_image",
        structured_data=combined_structured_data,
        breadcrumbs=breadcrumbs,
    )

    return APIResponse(
        success=True,
        message="Lấy dữ liệu SEO sản phẩm thành công",
        data=seo_meta,
    )


@router.get("/meta/organization", response_model=APIResponse[OrganizationSEOMeta])
async def get_organization_seo_meta():
    """F24: Lấy dữ liệu có cấu trúc Schema.org Organization / LocalBusiness của thương hiệu Đai Trắng."""
    org_meta = OrganizationSEOMeta(
        structured_data={
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": "Đai Trắng",
            "legalName": "Công Ty TNHH Võ Phục & Dụng Cụ Võ Thuật Đai Trắng",
            "url": BASE_URL,
            "logo": f"{BASE_URL}/logo.png",
            "image": f"{BASE_URL}/storefront.jpg",
            "description": "Thương hiệu cung cấp võ phục và phụ kiện võ thuật chuyên nghiệp hàng đầu Việt Nam",
            "telephone": "0988000001",
            "email": "cskh@daitrang.vn",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "Số 123 Đường Ba Tháng Hai, Phường 11",
                "addressLocality": "Quận 10",
                "addressRegion": "TP. Hồ Chí Minh",
                "postalCode": "700000",
                "addressCountry": "VN",
            },
            "priceRange": "50.000 VND - 850.000 VND",
            "openingHoursSpecification": [
                {
                    "@type": "OpeningHoursSpecification",
                    "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                    "opens": "08:00",
                    "closes": "21:00",
                }
            ],
            "sameAs": [
                "https://facebook.com/daitrang.vophuc",
                "https://youtube.com/@daitrangvophuc",
                "https://tiktok.com/@daitrang.vn",
            ],
        }
    )

    return APIResponse(
        success=True,
        message="Lấy dữ liệu cấu trúc tổ chức thành công",
        data=org_meta,
    )
