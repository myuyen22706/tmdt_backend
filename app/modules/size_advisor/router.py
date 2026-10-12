from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.responses import APIResponse
from app.modules.size_advisor.schemas import SizeConsultationRequest, SizeRecommendationResponse
from app.modules.products.models import SizeChart


router = APIRouter(prefix="/size-advisor", tags=["Size Advisor (USP #1)"])


@router.post("/recommend", response_model=APIResponse[SizeRecommendationResponse])
async def recommend_size(request: SizeConsultationRequest, db: Session = Depends(get_db)):
    """Tính năng điểm nhấn #1: Tư vấn chọn size thông minh đối chiếu bảng size quy chuẩn trong Database."""
    # Query bảng size theo môn võ
    charts = db.query(SizeChart).filter(SizeChart.martial_art_id == request.martial_art).all()
    if not charts:
        charts = db.query(SizeChart).all()

    # Tìm size khớp với chiều cao nhất
    best_size = None
    for c in charts:
        if c.height_min_cm <= request.height_cm <= c.height_max_cm:
            best_size = c.size_name
            break

    ordered_sizes = [
        "Size 00 (Trẻ em)", "Size 0 (Trẻ em)", "Size 1", "Size 2",
        "Size 3 (S)", "Size 4 (M)", "Size 5 (L)", "Size 6 (XL)", "Size 7 (XXL)"
    ]

    if not best_size:
        best_size = ordered_sizes[0] if request.height_cm < 115 else ordered_sizes[-1]

    idx = ordered_sizes.index(best_size) if best_size in ordered_sizes else 4

    fit_note = f"Đề xuất cho chiều cao {request.height_cm}cm, cân nặng {request.weight_kg}kg."
    if request.body_build == "bulky":
        if idx < len(ordered_sizes) - 1:
            idx += 1
            fit_note += " Dáng người đậm, hệ thống tự động tăng 1 size để đảm bảo sự thoải mái khi di chuyển tấn pháp."
    elif request.body_build == "lean":
        fit_note += " Dáng người thanh mảnh, form áo chuẩn theo chiều dài cánh tay và vạt áo."

    if request.child_buffer:
        if idx < len(ordered_sizes) - 1:
            idx += 1
            fit_note += " Đã cộng thêm 1 size trừ hao cho võ sinh nhí đang tuổi phát triển."

    recommended_size = ordered_sizes[idx]
    backup_size = ordered_sizes[idx - 1] if idx > 0 else ordered_sizes[1]

    data = SizeRecommendationResponse(
        recommended_size=recommended_size,
        backup_size=backup_size,
        fit_note=fit_note,
        size_specs={
            "martial_art": request.martial_art,
            "height_cm": request.height_cm,
            "weight_kg": request.weight_kg,
            "body_build": request.body_build,
        },
    )

    return APIResponse(
        success=True,
        message="Gợi ý size phù hợp thành công",
        data=data,
    )


@router.get("/chart")
async def get_size_chart(martial_art: str = "vovinam", db: Session = Depends(get_db)):
    """Lấy bảng size chuẩn theo môn võ từ database SQL Server."""
    items = db.query(SizeChart).filter(SizeChart.martial_art_id == martial_art).all()
    data = [
        {
            "size": item.size_name,
            "height_min": item.height_min_cm,
            "height_max": item.height_max_cm,
            "weight_min": item.weight_min_kg,
            "weight_max": item.weight_max_kg,
            "note": item.fit_note,
        }
        for item in items
    ]
    return APIResponse(
        success=True,
        message=f"Bảng size môn {martial_art}",
        data=data,
    )
