import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_db
from app.core.responses import APIResponse

router = APIRouter(prefix="/reviews", tags=["Product Reviews & Sizing Feedback"])


class ReviewCreate(BaseModel):
    product_id: str
    user_name: str
    rating: int = Field(5, ge=1, le=5)
    comment: str
    size_fit: str = Field("fit", description="tight (hơi chật), fit (vừa vặn), loose (hơi rộng)")
    bought_size: str


@router.get("")
async def list_reviews(product_id: Optional[str] = None, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lấy danh sách đánh giá sản phẩm từ cơ sở dữ liệu MongoDB."""
    reviews_col = db["reviews"]
    query = {}
    if product_id:
        query["product_id"] = product_id

    cursor = reviews_col.find(query).sort("created_at", -1)
    items = await cursor.to_list(length=100)

    data = [
        {
            "id": r.get("id", str(r.get("_id", ""))),
            "product_id": r.get("product_id", ""),
            "user_name": r.get("user_name", ""),
            "rating": r.get("rating", 5),
            "comment": r.get("comment", ""),
            "size_fit": r.get("size_fit", "fit"),
            "bought_size": r.get("bought_size", ""),
            "created_at": r.get("created_at"),
        }
        for r in items
    ]
    return APIResponse(
        success=True,
        message="Lấy danh sách đánh giá thành công",
        data=data,
    )


@router.post("")
async def create_review(req: ReviewCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Gửi đánh giá sản phẩm kèm độ vừa vặn của size vào database MongoDB."""
    reviews_col = db["reviews"]
    rev_id = f"rev-{uuid.uuid4().hex[:8]}"
    rev_doc = {
        "id": rev_id,
        "product_id": req.product_id,
        "user_name": req.user_name,
        "rating": req.rating,
        "comment": req.comment,
        "size_fit": req.size_fit,
        "bought_size": req.bought_size,
        "created_at": datetime.now(timezone.utc),
    }
    await reviews_col.insert_one(rev_doc)

    return APIResponse(
        success=True,
        message="Gửi đánh giá thành công",
        data={
            "id": rev_id,
            "user_name": req.user_name,
            "rating": req.rating,
            "size_fit": req.size_fit,
        },
    )

