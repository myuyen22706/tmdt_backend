from fastapi import APIRouter
from app.core.responses import APIResponse
from app.modules.size_advisor.schemas import (
    SizeConsultationRequest,
    SizeRecommendationResponse,
)
from app.modules.size_advisor.service import SizeAdvisorService

router = APIRouter(prefix="/size-advisor", tags=["Size Advisor (USP #1)"])


@router.post("/recommend", response_model=APIResponse[SizeRecommendationResponse])
async def recommend_size(request: SizeConsultationRequest):
    """Tính năng điểm nhấn #1: Tư vấn chọn size thông minh theo chiều cao, cân nặng và dáng người."""
    result = SizeAdvisorService.recommend(request)
    return APIResponse(
        success=True,
        message="Gợi ý size phù hợp thành công",
        data=result,
    )


@router.get("/chart")
async def get_size_chart(martial_art: str = "vovinam"):
    """Lấy bảng size chuẩn theo môn võ."""
    return APIResponse(
        success=True,
        message=f"Bảng size môn {martial_art}",
        data=SizeAdvisorService.STANDARD_SIZES,
    )
