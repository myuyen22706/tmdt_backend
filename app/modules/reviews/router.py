from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.core.responses import APIResponse

router = APIRouter(prefix="/reviews", tags=["Product Reviews & Sizing Feedback"])


class ReviewCreate(BaseModel):
    product_id: str
    user_name: str
    rating: int = Field(5, ge=1, le=5)
    comment: str
    size_fit: str = Field("fit", description="tight (hơi chật), fit (vừa vặn), loose (hơi rộng)")
    bought_size: str


class ReviewResponse(ReviewCreate):
    id: str
    created_at: datetime


MOCK_REVIEWS = [
    {
        "id": "rev-1",
        "product_id": "prod-vovinam-standard",
        "user_name": "Phụ huynh bé Tuấn",
        "rating": 5,
        "comment": "Vải dày dặn, thấm mồ hôi tốt. Bé 1m35 nặng 33kg mặc Size 2 vừa vặn rất đẹp!",
        "size_fit": "fit",
        "bought_size": "Size 2",
        "created_at": datetime.now(timezone.utc),
    },
    {
        "id": "rev-2",
        "product_id": "prod-vovinam-standard",
        "user_name": "Trần Thanh",
        "rating": 5,
        "comment": "Được tư vấn size chuẩn xác, giao hàng nhanh.",
        "size_fit": "fit",
        "bought_size": "Size 4 (M)",
        "created_at": datetime.now(timezone.utc),
    },
]


@router.get("", response_model=APIResponse[List[ReviewResponse]])
async def list_reviews(product_id: Optional[str] = None):
    """Lấy danh sách đánh giá sản phẩm (lọc theo product_id)."""
    items = MOCK_REVIEWS
    if product_id:
        items = [r for r in items if r["product_id"] == product_id]
    return APIResponse(
        success=True,
        message="Lấy danh sách đánh giá thành công",
        data=items,
    )


@router.post("", response_model=APIResponse[ReviewResponse])
async def create_review(req: ReviewCreate):
    """Đăng đánh giá sản phẩm kèm nhận xét độ vừa vặn của size."""
    new_rev = {
        "id": f"rev-{len(MOCK_REVIEWS) + 1}",
        "created_at": datetime.now(timezone.utc),
        **req.model_dump(),
    }
    MOCK_REVIEWS.append(new_rev)
    return APIResponse(
        success=True,
        message="Gửi đánh giá thành công",
        data=new_rev,
    )
