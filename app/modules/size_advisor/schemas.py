from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SizeConsultationRequest(BaseModel):
    martial_art: str = Field("vovinam", description="Môn võ: vovinam, taekwondo, karate, vo_co_truyen")
    height_cm: float = Field(..., ge=60, le=240, description="Chiều cao tính bằng cm")
    weight_kg: float = Field(..., ge=10, le=160, description="Cân nặng tính bằng kg")
    age: Optional[int] = Field(None, ge=3, le=100, description="Độ tuổi")
    gender: Optional[str] = Field("unisex", description="Giới tính: male, female, unisex")
    body_build: str = Field("standard", description="Vóc dáng: lean (gầy), standard (vừa), bulky (đậm/mập)")
    child_buffer: bool = Field(False, description="Mua rộng 1 size cho trẻ đang lớn")


class SizeRecommendationResponse(BaseModel):
    recommended_size: str
    backup_size: Optional[str] = None
    fit_note: str
    is_out_of_range: bool = False
    size_specs: dict
    free_exchange_guarantee: str = "Cam kết đổi size trong 7 ngày kể từ khi giao thành công"


class StudentProfileCreate(BaseModel):
    student_name: str = Field(..., min_length=2, max_length=100, description="Tên gọi võ sinh/con")
    birth_year: Optional[int] = Field(None, ge=1950, le=2026, description="Năm sinh")
    martial_art: str = Field(..., description="vovinam, taekwondo, karate, vo_co_truyen")
    height_cm: float = Field(..., ge=60, le=240, description="Chiều cao (cm)")
    weight_kg: float = Field(..., ge=10, le=160, description="Cân nặng (kg)")
    recommended_size: Optional[str] = None


class StudentProfileUpdate(BaseModel):
    student_name: Optional[str] = None
    birth_year: Optional[int] = None
    martial_art: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    recommended_size: Optional[str] = None


class StudentProfileResponse(BaseModel):
    id: str
    user_id: str
    student_name: str
    birth_year: Optional[int] = None
    martial_art: str
    height_cm: float
    weight_kg: float
    recommended_size: Optional[str] = None
    measured_date: datetime
    days_since_measured: int
    needs_remeasure: bool = False
    remeasure_alert: Optional[str] = None
