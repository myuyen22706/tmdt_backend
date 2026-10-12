from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.responses import APIResponse
from app.modules.products.schemas import ProductFilterParams, ProductResponse
from app.modules.products.service import ProductService

router = APIRouter(prefix="/products", tags=["Products (Catalog & USP #2 Filter)"])


@router.get("", response_model=APIResponse[List[ProductResponse]])
async def list_products(
    martial_art: Optional[str] = Query(None, description="Lọc theo môn võ: vovinam, taekwondo, karate, vo_co_truyen"),
    category: Optional[str] = Query(None, description="Lọc theo loại: vo_phuc, dai, bao_ho, phu_kien"),
    belt_rank: Optional[str] = Query(None, description="USP #2: Lọc theo cấp đai (lam_dai, dai_den...)"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo từ khóa"),
    min_price: Optional[float] = Query(None, description="Giá tối thiểu"),
    max_price: Optional[float] = Query(None, description="Giá tối đa"),
):
    """Lấy danh sách sản phẩm với bộ lọc chuyên sâu theo Môn võ & Cấp đai (USP #2)."""
    filters = ProductFilterParams(
        martial_art=martial_art,
        category=category,
        belt_rank=belt_rank,
        search=search,
        min_price=min_price,
        max_price=max_price,
    )
    items = ProductService.get_list(filters)
    return APIResponse(
        success=True,
        message="Lấy danh sách sản phẩm thành công",
        data=items,
    )


@router.get("/{id_or_slug}", response_model=APIResponse[ProductResponse])
async def get_product_detail(id_or_slug: str):
    """Chi tiết sản phẩm kèm biến thể size, kho theo size và tùy chọn in/thêu logo."""
    prod = ProductService.get_by_id_or_slug(id_or_slug)
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm",
        )
    return APIResponse(
        success=True,
        message="Lấy chi tiết sản phẩm thành công",
        data=prod,
    )
