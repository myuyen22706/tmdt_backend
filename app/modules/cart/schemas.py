from typing import List, Optional
from pydantic import BaseModel, Field


class CartItem(BaseModel):
    product_id: str
    product_name: str
    price: float
    size: str
    quantity: int = Field(1, ge=1)
    thumbnail: Optional[str] = None
    is_embroidered: bool = False
    embroidered_text: Optional[str] = None
    embroidery_fee: float = 0


class CartItemAdd(BaseModel):
    product_id: str
    size: str
    quantity: int = Field(1, ge=1)
    is_embroidered: bool = False
    embroidered_text: Optional[str] = None


class CartResponse(BaseModel):
    items: List[CartItem] = []
    total_items: int = 0
    subtotal: float = 0
    shipping_fee: float = 0
    discount_amount: float = 0
    grand_total: float = 0
