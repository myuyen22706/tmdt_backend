from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class StudentOrderItem(BaseModel):
    id: str
    student_name: str
    parent_phone: str
    selected_size: str
    is_embroidered_name: bool = False
    embroidered_text: Optional[str] = None
    is_paid: bool = False
    payment_method: str = "COD"
    total_amount: float
    created_at: datetime


class DojoCampaignCreate(BaseModel):
    dojo_name: str
    coach_name: str
    phone: str
    martial_art: str = "vovinam"
    campaign_title: str
    target_product_id: str
    logo_url: Optional[str] = None
    deadline: datetime
    discount_tier_info: str = "Đạt 10 bộ: giảm 5%, Đạt 20 bộ: giảm 10%, Đạt 50 bộ: giảm 15%"


class DojoCampaignResponse(DojoCampaignCreate):
    id: str
    campaign_code: str
    shareable_link: str
    total_ordered_count: int = 0
    orders: List[StudentOrderItem] = []
    created_at: datetime


class StudentOrderCreate(BaseModel):
    student_name: str
    parent_phone: str
    selected_size: str
    is_embroidered_name: bool = False
    embroidered_text: Optional[str] = None
    payment_method: str = "VietQR"
