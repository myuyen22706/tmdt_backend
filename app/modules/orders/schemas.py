from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ShippingAddress(BaseModel):
    recipient_name: str = Field(..., min_length=2, max_length=100, description="Họ tên người nhận")
    phone: str = Field(..., min_length=9, max_length=15, description="Số điện thoại nhận hàng")
    street_address: str = Field(..., min_length=3, description="Địa chỉ cụ thể (Số nhà, tên đường)")
    ward: Optional[str] = Field("", description="Phường / Xã")
    district: Optional[str] = Field("", description="Quận / Huyện")
    city_province: str = Field(..., description="Tỉnh / Thành phố")


class OrderItemCreate(BaseModel):
    product_id: str
    sku: str
    product_name: str
    size: str
    color: str = "Trắng"
    price: int = Field(..., ge=0, description="Đơn giá sản phẩm VND (số nguyên)")
    quantity: int = Field(1, ge=1)
    is_embroidered: bool = False
    embroidery_name: Optional[str] = Field(None, max_length=20, description="Tên thêu (tối đa 20 ký tự)")
    embroidery_fee: int = Field(default=0, ge=0, description="Phí thêu (30.000 VND / sản phẩm nếu có)")


class OrderCreate(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    shipping_address: ShippingAddress
    payment_method: str = Field("COD", description="COD hoặc MoMo (Mục 6)")
    items: List[OrderItemCreate] = Field(..., min_length=1)
    voucher_code: Optional[str] = None
    note: Optional[str] = None
    club_campaign_id: Optional[str] = None  # Giai đoạn 5 B2B


class OrderStatusHistoryItem(BaseModel):
    old_status: Optional[str] = None
    new_status: str
    changed_by: str
    timestamp: datetime
    note: Optional[str] = None


class OrderResponse(BaseModel):
    id: str
    order_code: str  # Dạng DT-YYYYMMDD-XXXX (Mục 6)
    user_id: Optional[str] = None
    channel: str = "retail"  # retail hoặc club
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    shipping_address_full: str
    subtotal: int
    shipping_fee: int
    discount_amount: int = 0
    embroidery_total: int = 0
    total_amount: int
    payment_method: str  # COD hoặc MoMo
    payment_status: str  # unpaid, paid
    status: str  # pending_payment, confirmed, processing, shipping, delivered, completed, cancelled
    items: List[OrderItemCreate]
    tracking_code: Optional[str] = None
    status_history: List[OrderStatusHistoryItem] = []
    created_at: datetime


class OrderStatusUpdateRequest(BaseModel):
    new_status: str = Field(..., description="confirmed, processing, shipping, delivered, completed, cancelled")
    note: Optional[str] = None


class SizeExchangeRequest(BaseModel):
    order_id: str
    product_id: str
    current_size: str
    desired_size: str
    reason: str
    customer_note: Optional[str] = None
