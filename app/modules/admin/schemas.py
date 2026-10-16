from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReturnRequestCreate(BaseModel):
    order_code: str = Field(..., description="Mã đơn hàng cần đổi size")
    product_id: str = Field(..., description="Mã sản phẩm")
    sku: str = Field(..., description="Mã biến thể SKU hiện tại")
    desired_size: str = Field(..., description="Kích cỡ mới mong muốn đổi")
    reason: str = Field(..., min_length=5, description="Lý do đổi (chật vai, dài quần...)")
    image_url: Optional[str] = None


class ReturnRequestResponse(BaseModel):
    id: str
    order_code: str
    user_id: Optional[str] = None
    product_id: str
    product_name: str
    sku: str
    current_size: str
    desired_size: str
    reason: str
    image_url: Optional[str] = None
    status: str = "pending"  # pending, approved, rejected, completed
    review_note: Optional[str] = None
    exchange_order_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ReturnReviewAction(BaseModel):
    action: str = Field(..., description="approve hoặc reject")
    note: Optional[str] = None


class ActivityLogEntry(BaseModel):
    id: str
    actor: str  # Số điện thoại hoặc user_id của người thực hiện
    actor_role: str  # admin, staff
    action: str  # ADMIN_LOGIN, CHANGE_ORDER_STATUS, UPDATE_PRODUCT_PRICE, ADJUST_INVENTORY, REFUND_ORDER
    target_type: str  # order, product, inventory, payment, auth
    target_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime


class PackingSlipResponse(BaseModel):
    order_code: str
    created_at: datetime
    customer_name: str
    customer_phone: str
    shipping_address: str
    tracking_code: Optional[str] = None
    carrier: str = "MockShipping"
    items: List[Dict[str, Any]]
    total_quantity: int
    notes: Optional[str] = None


class RevenueReportResponse(BaseModel):
    total_revenue: int
    retail_revenue: int
    club_revenue: int
    total_orders: int
    return_rate: str
    revenue_by_day: List[Dict[str, Any]]
    revenue_by_month: List[Dict[str, Any]]
    top_selling_products: List[Dict[str, Any]]
    low_stock_count: int
