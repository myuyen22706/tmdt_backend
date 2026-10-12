from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Numeric, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class MartialArt(Base):
    """Môn võ: Vovinam, Taekwondo, Karate, Võ Cổ Truyền..."""
    __tablename__ = "martial_arts"

    id = Column(String(50), primary_key=True)  # vovinam, taekwondo, karate, vo_co_truyen
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon_url = Column(String(500), nullable=True)

    products = relationship("Product", back_populates="martial_art_rel")


class ProductCategory(Base):
    """Loại sản phẩm: Võ phục, Đai, Bảo hộ, Phụ kiện..."""
    __tablename__ = "product_categories"

    id = Column(String(50), primary_key=True)  # vo_phuc, dai, bao_ho, phu_kien
    name = Column(String(100), nullable=False)

    products = relationship("Product", back_populates="category_rel")


class Product(Base):
    __tablename__ = "products"

    id = Column(String(50), primary_key=True, default=lambda: f"prod-{uuid.uuid4().hex[:8]}")
    name = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, index=True, nullable=False)
    martial_art_id = Column(String(50), ForeignKey("martial_arts.id"), nullable=False)
    category_id = Column(String(50), ForeignKey("product_categories.id"), nullable=False)
    belt_rank = Column(String(50), nullable=True, index=True)  # lam_dai, hoang_dai, dai_den, dai_trang...
    price = Column(Numeric(12, 2), nullable=False)
    original_price = Column(Numeric(12, 2), nullable=True)
    discount_percent = Column(Integer, default=0)
    thumbnail = Column(String(500), nullable=False)
    material = Column(String(200), default="Vải Kaki Cotton 100%")
    description = Column(Text, nullable=True)
    is_customizable = Column(Boolean, default=False)  # Hỗ trợ thêu tên, in logo
    rating = Column(Float, default=4.9)
    review_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    martial_art_rel = relationship("MartialArt", back_populates="products")
    category_rel = relationship("ProductCategory", back_populates="products")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")


class ProductVariant(Base):
    """Biến thể sản phẩm theo từng size và màu sắc."""
    __tablename__ = "product_variants"

    id = Column(String(50), primary_key=True, default=lambda: f"var-{uuid.uuid4().hex[:8]}")
    product_id = Column(String(50), ForeignKey("products.id"), nullable=False)
    size = Column(String(50), nullable=False)  # Size 00, Size 0, Size 1, Size 2, Size 3 (S)...
    color = Column(String(50), default="Trắng")
    stock_quantity = Column(Integer, default=20)
    price_adjustment = Column(Numeric(12, 2), default=0)
    sku = Column(String(50), nullable=True)

    product = relationship("Product", back_populates="variants")


class SizeChart(Base):
    """Bảng size quy chuẩn theo môn võ và thông số nhân trắc học."""
    __tablename__ = "size_charts"

    id = Column(String(50), primary_key=True, default=lambda: f"size-{uuid.uuid4().hex[:8]}")
    martial_art_id = Column(String(50), nullable=False)
    size_name = Column(String(50), nullable=False)
    height_min_cm = Column(Float, nullable=False)
    height_max_cm = Column(Float, nullable=False)
    weight_min_kg = Column(Float, nullable=False)
    weight_max_kg = Column(Float, nullable=False)
    fit_note = Column(String(255), nullable=True)
