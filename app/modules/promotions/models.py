from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Numeric, Integer, Boolean, DateTime
from app.core.database import Base


class Voucher(Base):
    """Mã giảm giá, khuyến mãi."""
    __tablename__ = "vouchers"

    id = Column(String(50), primary_key=True, default=lambda: f"vouc-{uuid.uuid4().hex[:8]}")
    code = Column(String(50), unique=True, index=True, nullable=False)
    discount_type = Column(String(20), default="PERCENT")  # PERCENT, FIXED
    discount_value = Column(Numeric(12, 2), nullable=False)
    min_order_amount = Column(Numeric(12, 2), default=0)
    usage_limit = Column(Integer, default=100)
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
