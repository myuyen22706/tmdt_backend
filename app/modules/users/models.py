from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone = Column(String(20), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="customer")  # customer, coach, admin, staff
    email = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    student_profiles = relationship("StudentProfile", back_populates="parent_user", cascade="all, delete-orphan")


class StudentProfile(Base):
    """Hồ sơ võ sinh (con 1, con 2) lưu môn võ, cấp đai và số đo để mua lại nhanh."""
    __tablename__ = "student_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    student_name = Column(String(100), nullable=False)
    martial_art = Column(String(50), nullable=False)  # vovinam, taekwondo, karate...
    belt_rank = Column(String(50), nullable=True)
    height_cm = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)
    recommended_size = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    parent_user = relationship("User", back_populates="student_profiles")
