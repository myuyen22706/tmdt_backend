from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Numeric, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class DojoClub(Base):
    """Thông tin Võ đường / Câu lạc bộ."""
    __tablename__ = "dojo_clubs"

    id = Column(String(50), primary_key=True, default=lambda: f"dojo-{uuid.uuid4().hex[:8]}")
    club_name = Column(String(200), nullable=False)
    coach_name = Column(String(100), nullable=False)
    coach_phone = Column(String(20), nullable=False)
    martial_art_id = Column(String(50), default="vovinam")
    address = Column(String(255), nullable=True)
    logo_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    campaigns = relationship("DojoOrderCampaign", back_populates="dojo", cascade="all, delete-orphan")


class DojoOrderCampaign(Base):
    """Đợt đặt hàng đồng phục theo lớp võ đường."""
    __tablename__ = "dojo_order_campaigns"

    id = Column(String(50), primary_key=True, default=lambda: f"camp-{uuid.uuid4().hex[:8]}")
    campaign_code = Column(String(50), unique=True, index=True, nullable=False)  # Ví dụ: PHUDONG2026
    dojo_id = Column(String(50), ForeignKey("dojo_clubs.id"), nullable=False)
    campaign_title = Column(String(255), nullable=False)
    target_product_id = Column(String(50), nullable=False)
    deadline = Column(DateTime, nullable=False)
    discount_tier_info = Column(String(255), default="10 bộ: giảm 5%, 20 bộ: giảm 10%, 50 bộ: giảm 15%")
    shareable_link = Column(String(255), nullable=False)
    status = Column(String(20), default="OPEN")  # OPEN, CLOSED, DELIVERED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    dojo = relationship("DojoClub", back_populates="campaigns")
    student_orders = relationship("DojoStudentOrder", back_populates="campaign", cascade="all, delete-orphan")


class DojoStudentOrder(Base):
    """Đơn hàng võ sinh được phụ huynh đặt qua link riêng của võ đường."""
    __tablename__ = "dojo_student_orders"

    id = Column(String(50), primary_key=True, default=lambda: f"dord-{uuid.uuid4().hex[:8]}")
    campaign_id = Column(String(50), ForeignKey("dojo_order_campaigns.id"), nullable=False)
    student_name = Column(String(100), nullable=False)
    parent_phone = Column(String(20), nullable=False)
    selected_size = Column(String(50), nullable=False)
    is_embroidered_name = Column(Boolean, default=False)
    embroidered_text = Column(String(100), nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=False)
    is_paid = Column(Boolean, default=False)
    payment_method = Column(String(50), default="VietQR")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    campaign = relationship("DojoOrderCampaign", back_populates="student_orders")
