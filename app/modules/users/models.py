from datetime import datetime, timezone
import uuid
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr


class StudentProfileDoc(BaseModel):
    """Hồ sơ võ sinh (con 1, con 2) lưu môn võ, cấp đai và số đo để tư vấn size nhanh (F05)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    student_name: str
    birth_year: Optional[int] = None
    martial_art: str  # vovinam, taekwondo, karate, vo_co_truyen
    belt_rank: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    recommended_size: Optional[str] = None
    measured_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserDoc(BaseModel):
    """Tài khoản người dùng lưu trong MongoDB (F01)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phone: str
    full_name: str
    hashed_password: str
    role: str = "customer"  # customer, coach, staff, admin
    email: Optional[str] = None
    address: Optional[str] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    reset_token: Optional[str] = None
    reset_token_expires_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserResponse(BaseModel):
    id: str
    phone: str
    full_name: str
    role: str
    email: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    created_at: datetime
