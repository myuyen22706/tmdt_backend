from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.responses import APIResponse
from app.modules.products.models import Product, ProductVariant, MartialArt, ProductCategory


router = APIRouter(prefix="/products", tags=["Products (Catalog & USP #2 Filter)"])


@router.get("")
async def list_products(
    martial_art: Optional[str] = Query(None, description="Lọc theo môn võ: vovinam, taekwondo, karate, vo_co_truyen"),
    category: Optional[str] = Query(None, description="Lọc theo loại: vo_phuc, dai, bao_ho, phu_kien"),
    belt_rank: Optional[str] = Query(None, description="USP #2: Lọc theo cấp đai (lam_dai, dai_den...)"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo từ khóa"),
    min_price: Optional[float] = Query(None, description="Giá tối thiểu"),
    max_price: Optional[float] = Query(None, description="Giá tối đa"),
    db: Session = Depends(get_db),
):
    """Lấy danh sách sản phẩm từ Database SQL Server với bộ lọc chuyên sâu theo Môn võ & Cấp đai (USP #2)."""
    query = db.query(Product).filter(Product.is_active == True)

    if martial_art and martial_art != "all":
        query = query.filter(Product.martial_art_id == martial_art)
    if category and category != "all":
        query = query.filter(Product.category_id == category)
    if belt_rank and belt_rank != "all":
        query = query.filter(Product.belt_rank == belt_rank)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(Product.name.ilike(search_fmt) | Product.description.ilike(search_fmt))

    products = query.all()

    # Format output
    result = []
    for p in products:
        result.append({
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "martial_art": p.martial_art_id,
            "category": p.category_id,
            "belt_rank": p.belt_rank,
            "price": float(p.price),
            "original_price": float(p.original_price) if p.original_price else None,
            "discount_percent": p.discount_percent,
            "thumbnail": p.thumbnail,
            "material": p.material,
            "description": p.description,
            "is_customizable": p.is_customizable,
            "rating": p.rating,
            "review_count": p.review_count,
            "variants": [
                {
                    "id": v.id,
                    "size": v.size,
                    "color": v.color,
                    "stock": v.stock_quantity,
                    "price_adjustment": float(v.price_adjustment),
                }
                for v in p.variants
            ],
        })

    return APIResponse(
        success=True,
        message="Lấy danh sách sản phẩm thành công",
        data=result,
    )


@router.get("/{id_or_slug}")
async def get_product_detail(id_or_slug: str, db: Session = Depends(get_db)):
    """Chi tiết sản phẩm kèm danh sách size tồn kho từ SQL Server."""
    p = db.query(Product).filter(
        (Product.id == id_or_slug) | (Product.slug == id_or_slug)
    ).first()

    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy sản phẩm")

    data = {
        "id": p.id,
        "name": p.name,
        "slug": p.slug,
        "martial_art": p.martial_art_id,
        "category": p.category_id,
        "belt_rank": p.belt_rank,
        "price": float(p.price),
        "original_price": float(p.original_price) if p.original_price else None,
        "discount_percent": p.discount_percent,
        "thumbnail": p.thumbnail,
        "material": p.material,
        "description": p.description,
        "is_customizable": p.is_customizable,
        "rating": p.rating,
        "review_count": p.review_count,
        "variants": [
            {
                "id": v.id,
                "size": v.size,
                "color": v.color,
                "stock": v.stock_quantity,
                "price_adjustment": float(v.price_adjustment),
            }
            for v in p.variants
        ],
    }

    return APIResponse(
        success=True,
        message="Lấy chi tiết sản phẩm thành công",
        data=data,
    )
