from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ProductVariantItem(BaseModel):
    sku: str = Field(..., description="Mã biến thể duy nhất, ví dụ: VOV-STD-S1-TRANG")
    size: str = Field(..., description="Kích thước: Size 00, Size 0, Size 1, Size 2... hoặc S, M, L, XL")
    color: str = Field(default="Trắng", description="Màu sắc")
    price: int = Field(..., ge=0, description="Giá bán theo VND (số nguyên)")
    stock: int = Field(default=10, ge=0, description="Số lượng tồn kho (>= 0)")
    low_stock_threshold: int = Field(default=5, ge=0, description="Ngưỡng cảnh báo tồn kho thấp")


class ProductBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., min_length=2, max_length=200)
    martial_art_id: str = Field(..., description="vovinam, taekwondo, karate, vo_co_truyen")
    category_id: str = Field(..., description="vo_phuc, dai, bao_ho, tui_dung, phu_kien")
    belt_rank: Optional[str] = Field(None, description="lam_dai, hoang_dai, dai_den, dai_trang...")
    price: int = Field(..., ge=0, description="Giá niêm yết theo VND (số nguyên)")
    original_price: Optional[int] = Field(None, ge=0, description="Giá gốc trước giảm (VND)")
    discount_percent: int = Field(default=0, ge=0, le=100)
    thumbnail: str = Field(..., description="URL ảnh đại diện")
    images: List[str] = Field(default=[], description="Danh sách ảnh chi tiết")
    material: str = Field(default="Vải Kaki Cotton 100%", description="Chất liệu vải")
    description: str = Field(default="", description="Mô tả sản phẩm")
    is_customizable: bool = Field(default=False, description="Hỗ trợ thêu tên riêng (F07)")
    rating: float = Field(default=4.9, ge=0, le=5)
    review_count: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)


class ProductCreate(ProductBase):
    variants: List[ProductVariantItem] = Field(default=[], description="Danh sách các biến thể size & màu")


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    martial_art_id: Optional[str] = None
    category_id: Optional[str] = None
    belt_rank: Optional[str] = None
    price: Optional[int] = None
    original_price: Optional[int] = None
    discount_percent: Optional[int] = None
    thumbnail: Optional[str] = None
    images: Optional[List[str]] = None
    material: Optional[str] = None
    description: Optional[str] = None
    is_customizable: Optional[bool] = None
    is_active: Optional[bool] = None
    variants: Optional[List[ProductVariantItem]] = None


class ProductVariantResponse(ProductVariantItem):
    in_stock: bool
    is_low_stock: bool


class ProductResponse(ProductBase):
    id: str
    variants: List[ProductVariantResponse] = []
    total_stock: int = 0
    in_stock: bool = True
    created_at: Optional[datetime] = None


class ProductListResponse(BaseModel):
    total: int
    items: List[ProductResponse]


# Compatibility aliases for legacy service imports
ProductVariant = ProductVariantItem


class ProductFilterParams(BaseModel):
    martial_art: Optional[str] = None
    category: Optional[str] = None
    belt_rank: Optional[str] = None
    size: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    search: Optional[str] = None

