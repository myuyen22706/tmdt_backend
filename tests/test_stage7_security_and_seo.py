import pytest
from httpx import AsyncClient
from app.core.security import mask_sensitive_data, sanitize_html, sanitize_nosql_input


@pytest.mark.asyncio
async def test_security_headers_owasp_standards(client: AsyncClient):
    """Mục 9: Kiểm tra toàn bộ phản hồi HTTP có đầy đủ Security Headers theo chuẩn OWASP."""
    res = await client.get("/api/v1/products", headers={"X-Bypass-Rate-Limit": "true"})
    assert res.status_code == 200

    headers = {k.lower(): v for k, v in res.headers.items()}

    # 1. Chống MIME-sniffing
    assert headers.get("x-content-type-options") == "nosniff"

    # 2. Chống Clickjacking
    assert headers.get("x-frame-options") == "DENY"

    # 3. Kích hoạt bộ lọc XSS
    assert headers.get("x-xss-protection") == "1; mode=block"

    # 4. Ép HTTPS với HSTS
    assert "max-age=31536000" in headers.get("strict-transport-security", "")

    # 5. Content Security Policy (CSP)
    assert "default-src 'self'" in headers.get("content-security-policy", "")

    # 6. Referrer Policy
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_rate_limiting_auth_endpoint(client: AsyncClient):
    """Mục 9: Kiểm tra giới hạn tần suất yêu cầu (Rate Limiting) chống Brute-force mật khẩu."""
    payload = {"phone": "0988000000", "password": "wrongpassword"}

    # Gửi liên tiếp 15 request đến endpoint /auth/login (ngưỡng tối đa 15 req/phút)
    for _ in range(15):
        await client.post("/api/v1/auth/login", json=payload)

    # Request thứ 16 bắt buộc bị chặn với mã trạng thái HTTP 429 Too Many Requests
    res_blocked = await client.post("/api/v1/auth/login", json=payload)
    assert res_blocked.status_code == 429
    data = res_blocked.json()
    assert data["error_code"] == "AUTH_RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in res_blocked.headers


def test_input_sanitization_xss_nosql_and_masking():
    """Mục 9: Kiểm tra khử mã độc XSS, ngăn chặn NoSQL Injection và che dữ liệu nhạy cảm."""
    # 1. Chống XSS (Cross-Site Scripting)
    xss_payload_1 = "<script>alert('hack')</script>Nguyễn Văn Võ"
    cleaned_1 = sanitize_html(xss_payload_1)
    assert "<script>" not in cleaned_1
    assert "Nguyễn Văn Võ" in cleaned_1

    xss_payload_2 = "<img src=x onerror=alert(document.cookie)>Võ Sinh"
    cleaned_2 = sanitize_html(xss_payload_2)
    assert "onerror" not in cleaned_2
    assert "Võ Sinh" in cleaned_2

    xss_payload_3 = "javascript:alert(1)"
    cleaned_3 = sanitize_html(xss_payload_3)
    assert "javascript:" not in cleaned_3

    # 2. Chống NoSQL Injection
    nosql_payload = "$where"
    cleaned_nosql = sanitize_nosql_input(nosql_payload)
    assert not cleaned_nosql.startswith("$")

    # 3. Che giấu dữ liệu nhạy cảm trong Log & Response
    raw_user_info = {
        "user_id": "usr-123",
        "phone": "0988111222",
        "password": "plain_password_123",
        "secret_key": "my_super_secret",
        "token": "eyJhbGciOi...",
    }
    masked = mask_sensitive_data(raw_user_info)
    assert masked["password"] == "***MASKED***"
    assert masked["secret_key"] == "***MASKED***"
    assert masked["token"] == "***MASKED***"
    assert masked["phone"] == "0988111222"


@pytest.mark.asyncio
async def test_f24_seo_sitemap_xml(client: AsyncClient, mock_mongo_db):
    """F24: Kiểm tra sinh tệp sitemap.xml động chuẩn Sitemaps.org XML Schema."""
    # Thêm sản phẩm mẫu vào database
    await mock_mongo_db["products"].insert_one({
        "id": "prod-vovinam-sitemap",
        "name": "Võ phục Vovinam Sitemap Test",
        "slug": "vo-phuc-vovinam-sitemap-test",
        "is_active": True,
        "price": 320000,
    })

    # 1. Kiểm tra root sitemap.xml
    res_root = await client.get("/sitemap.xml", headers={"X-Bypass-Rate-Limit": "true"})
    assert res_root.status_code == 200
    assert "xml" in res_root.headers.get("content-type", "")
    xml_root = res_root.text
    assert "<urlset" in xml_root
    assert "<loc>https://daitrang.vn/</loc>" in xml_root
    assert "<loc>https://daitrang.vn/products/vo-phuc-vovinam-sitemap-test</loc>" in xml_root
    assert "<priority>0.9</priority>" in xml_root

    # 2. Kiểm tra API endpoint /api/v1/seo/sitemap.xml
    res_api = await client.get("/api/v1/seo/sitemap.xml", headers={"X-Bypass-Rate-Limit": "true"})
    assert res_api.status_code == 200
    assert "<urlset" in res_api.text


@pytest.mark.asyncio
async def test_f24_seo_robots_txt(client: AsyncClient):
    """F24: Kiểm tra sinh tệp robots.txt quy chuẩn cho Search Engine Crawlers."""
    # 1. Kiểm tra root robots.txt
    res_root = await client.get("/robots.txt", headers={"X-Bypass-Rate-Limit": "true"})
    assert res_root.status_code == 200
    assert "text/plain" in res_root.headers.get("content-type", "")
    txt_root = res_root.text
    assert "User-agent: *" in txt_root
    assert "Disallow: /admin/" in txt_root
    assert "Disallow: /checkout/" in txt_root
    assert "Sitemap: https://daitrang.vn/sitemap.xml" in txt_root

    # 2. Kiểm tra API endpoint /api/v1/seo/robots.txt
    res_api = await client.get("/api/v1/seo/robots.txt", headers={"X-Bypass-Rate-Limit": "true"})
    assert res_api.status_code == 200
    assert "Disallow: /admin/" in res_api.text


@pytest.mark.asyncio
async def test_f24_seo_product_metadata_and_structured_data(client: AsyncClient, mock_mongo_db):
    """F24: Kiểm tra SEO Meta Tags và Dữ liệu có cấu trúc Schema.org (Product & BreadcrumbList)."""
    # Thêm sản phẩm mẫu
    await mock_mongo_db["products"].insert_one({
        "id": "prod-taekwondo-seo",
        "name": "Võ phục Taekwondo Poomsae Cao Cấp",
        "slug": "vo-phuc-taekwondo-poomsae-cao-cap",
        "description": "Võ phục Taekwondo quyền tiêu chuẩn thi đấu quốc tế, chất liệu vải gân kim cương thoáng mát.",
        "martial_art_id": "taekwondo",
        "price": 550000,
        "thumbnail": "/images/taekwondo-poomsae.jpg",
        "variants": [
            {"sku": "TAE-POOM-160", "size": "160cm", "stock": 10},
        ],
        "is_active": True,
    })

    res = await client.get(
        "/api/v1/seo/meta/product/vo-phuc-taekwondo-poomsae-cao-cap",
        headers={"X-Bypass-Rate-Limit": "true"},
    )
    assert res.status_code == 200
    meta = res.json()["data"]

    # Kiểm tra Meta Tags cơ bản
    assert "Võ phục Taekwondo Poomsae Cao Cấp" in meta["title"]
    assert meta["canonical_url"] == "https://daitrang.vn/products/vo-phuc-taekwondo-poomsae-cao-cap"
    assert meta["og_type"] == "product"
    assert meta["twitter_card"] == "summary_large_image"

    # Kiểm tra JSON-LD Structured Data Schema.org
    graph = meta["structured_data"]["@graph"]
    assert len(graph) >= 2

    # Schema 1: Product
    product_schema = next(s for s in graph if s.get("@type") == "Product")
    assert product_schema["name"] == "Võ phục Taekwondo Poomsae Cao Cấp"
    assert product_schema["brand"]["name"] == "Đai Trắng"
    assert product_schema["offers"]["price"] == 550000
    assert product_schema["offers"]["priceCurrency"] == "VND"
    assert product_schema["offers"]["availability"] == "https://schema.org/InStock"

    # Schema 2: BreadcrumbList
    breadcrumb_schema = next(s for s in graph if s.get("@type") == "BreadcrumbList")
    elements = breadcrumb_schema["itemListElement"]
    assert len(elements) == 3
    assert elements[0]["name"] == "Trang chủ"
    assert elements[2]["name"] == "Võ phục Taekwondo Poomsae Cao Cấp"


@pytest.mark.asyncio
async def test_f24_seo_organization_meta(client: AsyncClient):
    """F24: Kiểm tra siêu dữ liệu Schema.org LocalBusiness / Organization."""
    res = await client.get("/api/v1/seo/meta/organization", headers={"X-Bypass-Rate-Limit": "true"})
    assert res.status_code == 200
    org_data = res.json()["data"]
    assert org_data["name"] == "Đai Trắng"
    assert org_data["structured_data"]["@type"] == "LocalBusiness"
    assert org_data["structured_data"]["priceRange"] == "50.000 VND - 850.000 VND"
    assert org_data["email"] == "cskh@daitrang.vn"
