from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class ClubRegister(BaseModel):
    club_name: str = Field(..., min_length=2, max_length=150, description="Tên câu lạc bộ / võ đường")
    martial_art_id: str = Field(..., description="vovinam, taekwondo, karate, vo_co_truyen")
    address: str = Field(..., min_length=5, description="Địa chỉ đặt võ đường")
    coach_name: str = Field(..., min_length=2, description="Tên huấn luyện viên / người phụ trách")
    coach_phone: str = Field(..., min_length=9, max_length=15, description="Số điện thoại HLV")
    coach_email: Optional[EmailStr] = None
    logo_url: Optional[str] = None


class ClubResponse(ClubRegister):
    id: str
    status: str = "pending"  # pending, active, rejected
    created_at: datetime


class CampaignCreate(BaseModel):
    club_id: str = Field(..., description="Mã võ đường tổ chức")
    campaign_title: str = Field(..., min_length=3, max_length=200, description="Tiêu đề đợt đặt hàng")
    applicable_product_ids: List[str] = Field(..., min_length=1, description="Danh sách sản phẩm áp dụng")
    target_quantity: int = Field(..., ge=10, description="Số lượng dự kiến gom (tối thiểu 10 bộ)")
    deadline: datetime = Field(..., description="Thời hạn chốt đợt")
    has_custom_logo: bool = Field(default=False, description="Có thêu/in logo võ đường không")
    allow_club_consolidated_payment: bool = Field(default=True, description="Cho phép võ đường thanh toán gộp")


class CampaignResponse(BaseModel):
    id: str
    campaign_code: str
    club_id: str
    club_name: str
    campaign_title: str
    applicable_product_ids: List[str]
    target_quantity: int
    discount_percent: int
    deadline: datetime
    has_custom_logo: bool
    allow_club_consolidated_payment: bool
    campaign_url: str
    qr_code_url: str
    status: str = "open"  # open, closed, delivered
    total_ordered: int = 0
    total_amount: int = 0
    deposit_amount: int = 0
    deposit_paid: bool = False
    remaining_amount_paid: bool = False
    created_at: datetime


class StudentOrderCreate(BaseModel):
    student_name: str = Field(..., min_length=2, max_length=100, description="Tên võ sinh")
    parent_phone: str = Field(..., min_length=9, max_length=15, description="Số điện thoại phụ huynh")
    product_id: str
    sku: str
    size: str
    color: str = "Trắng"
    is_embroidered: bool = False
    embroidery_name: Optional[str] = Field(None, max_length=20, description="Tên thêu (tối đa 20 ký tự)")
    club_consolidated_payment: bool = Field(default=False, description="Chọn võ đường thanh toán gộp")


class StudentOrderResponse(BaseModel):
    id: str
    order_code: str
    student_name: str
    parent_phone: str
    product_name: str
    sku: str
    size: str
    price: int
    embroidery_fee: int = 0
    total_amount: int
    payment_method: str  # MOMO hoặc CLUB_CONSOLIDATED
    is_paid: bool = False
    created_at: datetime
