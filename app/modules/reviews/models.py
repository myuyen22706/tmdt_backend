from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from app.core.database import Base


class Review(Base):
    """Đánh giá sản phẩm và phản hồi độ vừa vặn của size."""
    __tablename__ = "reviews"

    id = Column(String(50), primary_key=True, default=lambda: f"rev-{uuid.uuid4().hex[:8]}")
    product_id = Column(String(50), nullable=False, index=True)
    user_name = Column(String(100), nullable=False)
    rating = Column(Integer, default=5)
    comment = Column(Text, nullable=False)
    size_fit = Column(String(20), default="fit")  # tight (hơi chật), fit (vừa vặn), loose (hơi rộng)
    bought_size = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
