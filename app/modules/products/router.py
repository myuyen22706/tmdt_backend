import asyncio
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_role
from app.core.responses import APIResponse
from app.modules.products.schemas import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
    ProductVariantResponse,
)

router = APIRouter(prefix="/products", tags=["Products & Catalog (F02, F03, F16)"])

# Thứ tự sắp xếp hỗ trợ cho danh mục (F02)
SORT_SPECS = {
    "newest": [("created_at", -1)],
    "price_asc": [("price", 1)],
    "price_desc": [("price", -1)],
    "popular": [("review_count", -1), ("rating", -1)],
    "discount": [("discount_percent", -1), ("price", 1)],
}


def _set_public_cache(response: Response) -> None:
    """Cho phép trình duyệt/CDN cache ngắn các endpoint catalog công khai."""
    max_age = settings.PUBLIC_CACHE_MAX_AGE
    response.headers["Cache-Control"] = f"public, max-age={max_age}, stale-while-revalidate={max_age * 5}"


def _format_product(doc: dict) -> ProductResponse:
    variants_resp = []
    total_stock = 0
    for v in doc.get("variants", []):
        stock = v.get("stock", 0)
        low_threshold = v.get("low_stock_threshold", 5)
        total_stock += stock
        variants_resp.append(
            ProductVariantResponse(
                sku=v.get("sku", ""),
                size=v.get("size", ""),
                color=v.get("color", "Trắng"),
                price=int(v.get("price", doc.get("price", 0))),
                stock=stock,
                low_stock_threshold=low_threshold,
                in_stock=stock > 0,
                is_low_stock=0 < stock <= low_threshold,
            )
        )

    return ProductResponse(
        id=doc.get("id", str(doc.get("_id", ""))),
        name=doc.get("name", ""),
        slug=doc.get("slug", ""),
        martial_art_id=doc.get("martial_art_id", ""),
        category_id=doc.get("category_id", ""),
        belt_rank=doc.get("belt_rank"),
        price=int(doc.get("price", 0)),
        original_price=int(doc["original_price"]) if doc.get("original_price") else None,
        discount_percent=int(doc.get("discount_percent", 0)),
        thumbnail=doc.get("thumbnail", ""),
        images=doc.get("images", []),
        material=doc.get("material", "Vải Kaki Cotton 100%"),
        description=doc.get("description", ""),
        is_customizable=doc.get("is_customizable", False),
        rating=float(doc.get("rating", 4.9)),
        review_count=int(doc.get("review_count", 0)),
        is_active=doc.get("is_active", True),
        variants=variants_resp,
        total_stock=total_stock,
        in_stock=total_stock > 0,
        created_at=doc.get("created_at"),
    )


@router.get("", response_model=APIResponse[ProductListResponse])
async def list_products(
    response: Response,
    martial_art: Optional[str] = Query(None, description="Lọc theo môn: vovinam, taekwondo, karate, vo_co_truyen"),
    category: Optional[str] = Query(None, description="Lọc theo loại: vo_phuc, dai, bao_ho, tui_dung, phu_kien"),
    belt_rank: Optional[str] = Query(None, description="Lọc theo cấp đai: lam_dai, hoang_dai, dai_den..."),
    size: Optional[str] = Query(None, description="Lọc theo kích cỡ"),
    color: Optional[str] = Query(None, description="Lọc theo màu sắc"),
    min_price: Optional[int] = Query(None, ge=0, description="Khoảng giá tối thiểu (VND)"),
    max_price: Optional[int] = Query(None, ge=0, description="Khoảng giá tối đa (VND)"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên sản phẩm"),
    sort_by: Optional[str] = Query("newest", description="Sắp xếp: newest, popular, discount, price_asc, price_desc"),
    exclude_id: Optional[str] = Query(None, description="Bỏ qua một sản phẩm (dùng cho gợi ý sản phẩm liên quan)"),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F02: Xem danh mục, lọc đa tiêu chí, tìm kiếm và sắp xếp theo giá / mới nhất."""
    products_col = db["products"]
    filter_query = {"is_active": True}

    if martial_art and martial_art != "all":
        filter_query["martial_art_id"] = martial_art
    if category and category != "all":
        filter_query["category_id"] = category
    if belt_rank and belt_rank != "all":
        filter_query["belt_rank"] = belt_rank
    if size and size != "all":
        filter_query["variants.size"] = size
    if color and color != "all":
        filter_query["variants.color"] = color

    # Lọc khoảng giá
    price_filter = {}
    if min_price is not None:
        price_filter["$gte"] = min_price
    if max_price is not None:
        price_filter["$lte"] = max_price
    if price_filter:
        filter_query["price"] = price_filter

    # Tìm kiếm theo tên
    if search and search.strip():
        filter_query["name"] = {"$regex": re.escape(search.strip()), "$options": "i"}
    if exclude_id:
        filter_query["id"] = {"$ne": exclude_id}

    sort_spec = SORT_SPECS.get(sort_by or "newest", SORT_SPECS["newest"])

    # Đếm và lấy trang dữ liệu song song để giảm độ trễ
    cursor = (
        products_col.find(filter_query, {"_id": 0})
        .sort(sort_spec)
        .skip((page - 1) * limit)
        .limit(limit)
    )
    total, docs = await asyncio.gather(
        products_col.count_documents(filter_query),
        cursor.to_list(length=limit),
    )
    items = [_format_product(d) for d in docs]
    _set_public_cache(response)

    return APIResponse(
        success=True,
        message="Lấy danh sách sản phẩm thành công",
        data=ProductListResponse(total=total, items=items),
    )


@router.get("/meta/martial-arts", response_model=APIResponse[List[dict]])
async def get_martial_arts(response: Response, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lấy danh sách các môn võ."""
    cursor = db["martial_arts"].find({})
    items = await cursor.to_list(length=20)
    for it in items:
        it["_id"] = str(it["_id"])
    _set_public_cache(response)
    return APIResponse(success=True, message="Danh sách môn võ", data=items)


@router.get("/meta/categories", response_model=APIResponse[List[dict]])
async def get_categories(response: Response, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lấy danh sách các loại sản phẩm."""
    cursor = db["categories"].find({})
    items = await cursor.to_list(length=20)
    for it in items:
        it["_id"] = str(it["_id"])
    _set_public_cache(response)
    return APIResponse(success=True, message="Danh sách loại sản phẩm", data=items)


@router.get("/meta/facets", response_model=APIResponse[dict])
async def get_catalog_facets(response: Response, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Số lượng sản phẩm theo môn võ, loại, cấp đai và khoảng giá (phục vụ bộ lọc catalog)."""
    products_col = db["products"]
    active = {"is_active": True}

    async def count_by(field: str) -> dict:
        values = await products_col.distinct(field, active)
        counts = await asyncio.gather(
            *[products_col.count_documents({**active, field: v}) for v in values if v]
        )
        return {v: c for v, c in zip([v for v in values if v], counts)}

    martial_arts_docs, categories_docs, by_martial_art, by_category, by_belt, total, cheapest, priciest = await asyncio.gather(
        db["martial_arts"].find({}, {"_id": 0}).to_list(length=20),
        db["categories"].find({}, {"_id": 0}).to_list(length=20),
        count_by("martial_art_id"),
        count_by("category_id"),
        count_by("belt_rank"),
        products_col.count_documents(active),
        products_col.find(active, {"_id": 0, "price": 1}).sort("price", 1).limit(1).to_list(length=1),
        products_col.find(active, {"_id": 0, "price": 1}).sort("price", -1).limit(1).to_list(length=1),
    )

    _set_public_cache(response)
    return APIResponse(
        success=True,
        message="Thống kê bộ lọc danh mục",
        data={
            "total": total,
            "martial_arts": [
                {"id": m.get("id"), "name": m.get("name"), "description": m.get("description", ""), "count": by_martial_art.get(m.get("id"), 0)}
                for m in martial_arts_docs
            ],
            "categories": [
                {"id": c.get("id"), "name": c.get("name"), "count": by_category.get(c.get("id"), 0)}
                for c in categories_docs
            ],
            "belt_ranks": by_belt,
            "price_min": int(cheapest[0]["price"]) if cheapest else 0,
            "price_max": int(priciest[0]["price"]) if priciest else 0,
        },
    )


@router.get("/{id_or_slug}", response_model=APIResponse[dict])
async def get_product_detail(id_or_slug: str, response: Response, db: AsyncIOMotorDatabase = Depends(get_db)):
    """F03: Chi tiết sản phẩm kèm ảnh, mô tả, bảng size, biến thể và trạng thái tồn kho."""
    products_col = db["products"]
    doc = await products_col.find_one({
        "$or": [{"id": id_or_slug}, {"slug": id_or_slug}]
    })
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm",
        )

    product = _format_product(doc)

    # Lấy kèm bảng size tương ứng với môn võ của sản phẩm (F03)
    size_charts_cursor = db["size_charts"].find({"martial_art_id": product.martial_art_id})
    charts_docs = await size_charts_cursor.to_list(length=50)
    size_charts = [
        {
            "size": c.get("size_name"),
            "height_min_cm": c.get("height_min_cm"),
            "height_max_cm": c.get("height_max_cm"),
            "weight_min_kg": c.get("weight_min_kg"),
            "weight_max_kg": c.get("weight_max_kg"),
            "age_range": f"{c.get('age_min', 0)}-{c.get('age_max', 0)} tuổi" if c.get("age_min") else None,
            "fit_note": c.get("fit_note"),
        }
        for c in charts_docs
    ]

    _set_public_cache(response)
    return APIResponse(
        success=True,
        message="Lấy chi tiết sản phẩm thành công",
        data={
            "product": product.model_dump(),
            "size_chart": size_charts,
        },
    )


# ==============================================================================
# F16: Quản lý sản phẩm (Dành cho Quản trị viên và Nhân viên vận hành)
# ==============================================================================

@router.post("", response_model=APIResponse[ProductResponse])
async def create_product(
    payload: ProductCreate,
    current_user: dict = Depends(require_role(["admin", "staff"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F16: Tạo sản phẩm mới (chỉ admin / staff)."""
    products_col = db["products"]
    existing = await products_col.find_one({"slug": payload.slug})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slug sản phẩm đã tồn tại, vui lòng chọn slug khác",
        )

    now = datetime.now(timezone.utc)
    product_dict = payload.model_dump()
    product_dict["id"] = f"prod-{uuid.uuid4().hex[:8]}"
    product_dict["created_at"] = now
    product_dict["updated_at"] = now

    await products_col.insert_one(product_dict)
    return APIResponse(
        success=True,
        message="Tạo sản phẩm thành công",
        data=_format_product(product_dict),
    )


@router.put("/{product_id}", response_model=APIResponse[ProductResponse])
async def update_product(
    product_id: str,
    payload: ProductUpdate,
    current_user: dict = Depends(require_role(["admin", "staff"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F16: Cập nhật thông tin sản phẩm hoặc biến thể (chỉ admin / staff)."""
    products_col = db["products"]
    existing = await products_col.find_one({"id": product_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm cần cập nhật",
        )

    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)

    # Ghi nhận Audit Log F23 nếu có cập nhật giá sản phẩm
    if payload.price is not None and payload.price != existing.get("price"):
        from app.core.activity import record_activity
        await record_activity(
            db=db,
            actor=current_user.get("phone", current_user.get("sub", "staff")),
            actor_role=current_user.get("role", "staff"),
            action="UPDATE_PRODUCT_PRICE",
            target_type="product",
            target_id=product_id,
            details={
                "product_name": existing.get("name"),
                "old_price": existing.get("price"),
                "new_price": payload.price,
            },
        )

    await products_col.update_one({"id": product_id}, {"$set": update_data})
    updated_doc = await products_col.find_one({"id": product_id})

    return APIResponse(
        success=True,
        message="Cập nhật sản phẩm thành công",
        data=_format_product(updated_doc),
    )


@router.delete("/{product_id}", response_model=APIResponse[dict])
async def delete_product(
    product_id: str,
    current_user: dict = Depends(require_role(["admin"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F16: Xóa sản phẩm (chỉ admin)."""
    products_col = db["products"]
    res = await products_col.delete_one({"id": product_id})
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm",
        )

    return APIResponse(
        success=True,
        message="Đã xóa sản phẩm thành công",
        data={"deleted_id": product_id},
    )
