from typing import Optional
from pydantic import BaseModel, Field


class SizeConsultationRequest(BaseModel):
    martial_art: str = Field("vovinam", description="Môn võ: vovinam, taekwondo, karate, vo_co_truyen")
    height_cm: float = Field(..., ge=80, le=220, description="Chiều cao tính bằng cm")
    weight_kg: float = Field(..., ge=15, le=150, description="Cân nặng tính bằng kg")
    age: Optional[int] = Field(None, ge=3, le=100, description="Độ tuổi")
    gender: Optional[str] = Field("male", description="Giới tính: male, female, unisex")
    body_build: str = Field("standard", description="Vóc dáng: lean (gầy), standard (vừa), bulky (đậm/mập)")
    child_buffer: bool = Field(False, description="Mua rộng 1 size cho trẻ đang lớn")


class SizeRecommendationResponse(BaseModel):
    recommended_size: str
    backup_size: Optional[str] = None
    fit_note: str
    size_specs: dict
    free_exchange_guarantee: str = "Cam kết đổi size miễn phí 1 lần trong 7 ngày nếu không vừa"
