from typing import List, Optional
from pydantic import BaseModel, Field


class CartItem(BaseModel):
    product_id: str
    sku: str
    product_name: str
    size: str
    color: str = "Trắng"
    price: int = Field(..., ge=0, description="Giá sản phẩm (VND)")
    quantity: int = Field(1, ge=1)
    thumbnail: Optional[str] = None
    is_embroidered: bool = False
    embroidery_name: Optional[str] = Field(None, max_length=20, description="Tên thêu tối đa 20 ký tự có dấu")
    embroidery_fee: int = Field(default=0, ge=0, description="Phí thêu (30.000 VND / sản phẩm nếu có)")


class CartItemAdd(BaseModel):
    product_id: str
    sku: str
    quantity: int = Field(1, ge=1)
    is_embroidered: bool = False
    embroidery_name: Optional[str] = Field(None, max_length=20, description="Tên thêu tối đa 20 ký tự")


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1, description="Số lượng mới")


class CartMergeRequest(BaseModel):
    session_id: str = Field(..., description="Mã phiên của giỏ hàng khách vãng lai cần gộp")


class CartResponse(BaseModel):
    items: List[CartItem] = []
    total_items: int = 0
    subtotal: int = 0
    embroidery_total: int = 0
    has_embroidery: bool = False
    shipping_fee: int = 0
    grand_total: int = 0
