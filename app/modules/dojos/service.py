from datetime import datetime, timedelta, timezone
from typing import List, Optional
import uuid
from app.modules.dojos.schemas import (
    DojoCampaignCreate,
    DojoCampaignResponse,
    StudentOrderCreate,
    StudentOrderItem,
)

# In-memory mock database for demo
MOCK_CAMPAIGNS: List[dict] = [
    {
        "id": "camp-vd-phudong",
        "campaign_code": "PHUDONG2026",
        "dojo_name": "CLB Vovinam Phù Đổng",
        "coach_name": "Võ sư Nguyễn Văn Hùng",
        "phone": "0987654321",
        "martial_art": "vovinam",
        "campaign_title": "Đợt đặt đồng phục khóa Hè 2026 - CLB Phù Đổng",
        "target_product_id": "prod-vovinam-standard",
        "logo_url": "https://placehold.co/200x200?text=Phu+Dong+Logo",
        "deadline": datetime.now(timezone.utc) + timedelta(days=14),
        "discount_tier_info": "10 bộ: giảm 5%, 20 bộ: giảm 10%, 50 bộ: giảm 15%",
        "shareable_link": "http://localhost:5173/dojo/PHUDONG2026",
        "total_ordered_count": 3,
        "created_at": datetime.now(timezone.utc),
        "orders": [
            {
                "id": "ord-std-1",
                "student_name": "Trần Bảo Nam",
                "parent_phone": "0912345678",
                "selected_size": "Size 2",
                "is_embroidered_name": True,
                "embroidered_text": "Bảo Nam",
                "is_paid": True,
                "payment_method": "VietQR",
                "total_amount": 260000,
                "created_at": datetime.now(timezone.utc) - timedelta(days=2),
            },
            {
                "id": "ord-std-2",
                "student_name": "Lê Gia Hân",
                "parent_phone": "0912345679",
                "selected_size": "Size 1",
                "is_embroidered_name": True,
                "embroidered_text": "Gia Hân",
                "is_paid": True,
                "payment_method": "VietQR",
                "total_amount": 260000,
                "created_at": datetime.now(timezone.utc) - timedelta(days=1),
            },
            {
                "id": "ord-std-3",
                "student_name": "Nguyễn Minh Khang",
                "parent_phone": "0912345680",
                "selected_size": "Size 3 (S)",
                "is_embroidered_name": False,
                "embroidered_text": None,
                "is_paid": False,
                "payment_method": "COD",
                "total_amount": 240000,
                "created_at": datetime.now(timezone.utc),
            },
        ],
    }
]


class DojoService:
    @classmethod
    def get_campaigns(cls) -> List[dict]:
        return MOCK_CAMPAIGNS

    @classmethod
    def get_by_code(cls, code: str) -> Optional[dict]:
        for c in MOCK_CAMPAIGNS:
            if c["campaign_code"].upper() == code.upper():
                return c
        return None

    @classmethod
    def create_campaign(cls, data: DojoCampaignCreate) -> dict:
        code = f"DOJO-{uuid.uuid4().hex[:6].upper()}"
        new_camp = {
            "id": f"camp-{uuid.uuid4().hex[:8]}",
            "campaign_code": code,
            "shareable_link": f"http://localhost:5173/dojo/{code}",
            "total_ordered_count": 0,
            "orders": [],
            "created_at": datetime.now(timezone.utc),
            **data.model_dump(),
        }
        MOCK_CAMPAIGNS.append(new_camp)
        return new_camp

    @classmethod
    def add_student_order(cls, campaign_code: str, order_data: StudentOrderCreate) -> dict:
        camp = cls.get_by_code(campaign_code)
        if not camp:
            return None
        new_order = {
            "id": f"ord-std-{uuid.uuid4().hex[:8]}",
            "student_name": order_data.student_name,
            "parent_phone": order_data.parent_phone,
            "selected_size": order_data.selected_size,
            "is_embroidered_name": order_data.is_embroidered_name,
            "embroidered_text": order_data.embroidered_text,
            "is_paid": order_data.payment_method == "VietQR",
            "payment_method": order_data.payment_method,
            "total_amount": 260000 if order_data.is_embroidered_name else 240000,
            "created_at": datetime.now(timezone.utc),
        }
        camp["orders"].append(new_order)
        camp["total_ordered_count"] = len(camp["orders"])
        return new_order
