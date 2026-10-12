from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.responses import APIResponse
from app.modules.reviews.models import Review

router = APIRouter(prefix="/reviews", tags=["Product Reviews & Sizing Feedback"])


class ReviewCreate(BaseModel):
    product_id: str
    user_name: str
    rating: int = Field(5, ge=1, le=5)
    comment: str
    size_fit: str = Field("fit", description="tight (hơi chật), fit (vừa vặn), loose (hơi rộng)")
    bought_size: str


@router.get("")
async def list_reviews(product_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Lấy danh sách đánh giá sản phẩm từ cơ sở dữ liệu."""
    query = db.query(Review)
    if product_id:
        query = query.filter(Review.product_id == product_id)
    items = query.order_by(Review.created_at.desc()).all()

    data = [
        {
            "id": r.id,
            "product_id": r.product_id,
            "user_name": r.user_name,
            "rating": r.rating,
            "comment": r.comment,
            "size_fit": r.size_fit,
            "bought_size": r.bought_size,
            "created_at": r.created_at,
        }
        for r in items
    ]
    return APIResponse(
        success=True,
        message="Lấy danh sách đánh giá thành công",
        data=data,
    )


@router.post("")
async def create_review(req: ReviewCreate, db: Session = Depends(get_db)):
    """Gửi đánh giá sản phẩm kèm độ vừa vặn của size vào database."""
    rev = Review(
        product_id=req.product_id,
        user_name=req.user_name,
        rating=req.rating,
        comment=req.comment,
        size_fit=req.size_fit,
        bought_size=req.bought_size,
    )
    db.add(rev)
    db.commit()
    db.refresh(rev)

    return APIResponse(
        success=True,
        message="Gửi đánh giá thành công",
        data={
            "id": rev.id,
            "user_name": rev.user_name,
            "rating": rev.rating,
            "size_fit": rev.size_fit,
        },
    )
