from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Numeric, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(String(50), primary_key=True, default=lambda: f"ord-{uuid.uuid4().hex[:8]}")
    order_code = Column(String(50), unique=True, index=True, nullable=False)
    user_id = Column(String(50), nullable=True)  # Nullable để hỗ trợ Guest Checkout
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    customer_email = Column(String(100), nullable=True)
    shipping_address = Column(Text, nullable=False)
    payment_method = Column(String(50), default="VietQR")  # COD, VietQR, MoMo, ZaloPay
    payment_status = Column(String(20), default="UNPAID")  # UNPAID, PAID
    order_status = Column(String(30), default="PENDING")   # PENDING, CONFIRMED, PACKING, SHIPPING, COMPLETED, CANCELLED
    subtotal = Column(Numeric(12, 2), nullable=False)
    shipping_fee = Column(Numeric(12, 2), default=0)
    discount_amount = Column(Numeric(12, 2), default=0)
    total_amount = Column(Numeric(12, 2), nullable=False)
    tracking_code = Column(String(50), nullable=True)
    shipping_carrier = Column(String(50), default="GHTK")
    vietqr_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    exchange_requests = relationship("SizeExchangeRequest", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(String(50), primary_key=True, default=lambda: f"item-{uuid.uuid4().hex[:8]}")
    order_id = Column(String(50), ForeignKey("orders.id"), nullable=False)
    product_id = Column(String(50), nullable=False)
    product_name = Column(String(200), nullable=False)
    size = Column(String(50), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Numeric(12, 2), nullable=False)
    is_embroidered = Column(Boolean, default=False)
    embroidery_fee = Column(Numeric(12, 2), default=0)
    embroidered_text = Column(String(100), nullable=True)

    order = relationship("Order", back_populates="items")


class SizeExchangeRequest(Base):
    """Yêu cầu đổi size miễn phí (Cam kết đổi size 1 lần)."""
    __tablename__ = "size_exchange_requests"

    id = Column(String(50), primary_key=True, default=lambda: f"ex-{uuid.uuid4().hex[:8]}")
    order_id = Column(String(50), ForeignKey("orders.id"), nullable=False)
    product_id = Column(String(50), nullable=False)
    current_size = Column(String(50), nullable=False)
    desired_size = Column(String(50), nullable=False)
    reason = Column(Text, nullable=False)
    customer_note = Column(Text, nullable=True)
    status = Column(String(30), default="PENDING")  # PENDING, APPROVED, SHIPPED, COMPLETED, REJECTED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="exchange_requests")
