from typing import List, Optional
from pydantic import BaseModel, Field


class ProductVariant(BaseModel):
    id: str
    size: str
    color: Optional[str] = "Trắng"
    stock: int = 10
    price_adjustment: float = 0


class ProductBase(BaseModel):
    name: str
    slug: str
    martial_art: str = Field(..., description="vovinam, taekwondo, karate, vo_co_truyen")
    category: str = Field(..., description="vo_phuc, dai, bao_ho, phu_kien")
    belt_rank: Optional[str] = Field(None, description="lam_dai, hoang_dai, dai_den...")
    price: float
    original_price: Optional[float] = None
    thumbnail: str
    images: List[str] = []
    material: str = "Kaki Cotton thấm hút mồ hôi"
    description: str
    is_customizable: bool = Field(False, description="Hỗ trợ in/thêu logo, tên võ sinh")


class ProductCreate(ProductBase):
    variants: List[ProductVariant] = []


class ProductResponse(ProductBase):
    id: str
    rating: float = 4.9
    review_count: int = 24
    variants: List[ProductVariant] = []


class ProductFilterParams(BaseModel):
    martial_art: Optional[str] = None
    category: Optional[str] = None
    belt_rank: Optional[str] = None
    size: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    search: Optional[str] = None
