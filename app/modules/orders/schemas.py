from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from app.modules.cart.schemas import CartItem


class ShippingAddress(BaseModel):
    full_name: str
    phone: str
    city_province: str
    district: str
    ward: str
    street_address: str


class OrderCreate(BaseModel):
    customer_email: Optional[str] = None
    shipping_address: ShippingAddress
    payment_method: str = Field("VietQR", description="COD, VietQR, MoMo, ZaloPay")
    voucher_code: Optional[str] = None
    items: List[CartItem]
    note: Optional[str] = None


class OrderResponse(BaseModel):
    id: str
    order_code: str
    status: str = "PENDING"  # PENDING, CONFIRMED, PACKING, SHIPPING, COMPLETED, CANCELLED
    customer_name: str
    phone: str
    shipping_address_full: str
    payment_method: str
    payment_status: str = "UNPAID"  # UNPAID, PAID
    items: List[CartItem]
    subtotal: float
    shipping_fee: float
    discount_amount: float
    total_amount: float
    tracking_code: Optional[str] = None
    shipping_carrier: Optional[str] = "GHTK"
    vietqr_url: Optional[str] = None
    created_at: datetime


class SizeExchangeRequest(BaseModel):
    order_id: str
    product_id: str
    current_size: str
    desired_size: str
    reason: str = Field(..., description="Chật ngực/vai, dài quần, muốn đổi rộng hơn...")
    customer_note: Optional[str] = None
