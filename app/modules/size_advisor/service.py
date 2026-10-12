from app.modules.size_advisor.schemas import (
    SizeConsultationRequest,
    SizeRecommendationResponse,
)


class SizeAdvisorService:
    # Standard size chart matrix based on height & weight
    STANDARD_SIZES = [
        {"size": "Size 00 (Trẻ em)", "height_min": 100, "height_max": 115, "weight_min": 15, "weight_max": 22},
        {"size": "Size 0 (Trẻ em)", "height_min": 115, "height_max": 125, "weight_min": 20, "weight_max": 28},
        {"size": "Size 1", "height_min": 125, "height_max": 135, "weight_min": 26, "weight_max": 35},
        {"size": "Size 2", "height_min": 135, "height_max": 145, "weight_min": 33, "weight_max": 42},
        {"size": "Size 3 (S)", "height_min": 145, "height_max": 155, "weight_min": 40, "weight_max": 50},
        {"size": "Size 4 (M)", "height_min": 155, "height_max": 165, "weight_min": 48, "weight_max": 60},
        {"size": "Size 5 (L)", "height_min": 165, "height_max": 172, "weight_min": 58, "weight_max": 70},
        {"size": "Size 6 (XL)", "height_min": 172, "height_max": 180, "weight_min": 68, "weight_max": 82},
        {"size": "Size 7 (XXL)", "height_min": 180, "height_max": 195, "weight_min": 80, "weight_max": 105},
    ]

    SIZE_ORDER = [
        "Size 00 (Trẻ em)",
        "Size 0 (Trẻ em)",
        "Size 1",
        "Size 2",
        "Size 3 (S)",
        "Size 4 (M)",
        "Size 5 (L)",
        "Size 6 (XL)",
        "Size 7 (XXL)",
    ]

    @classmethod
    def recommend(cls, req: SizeConsultationRequest) -> SizeRecommendationResponse:
        # Match based on height primary, weight secondary
        best_match = None
        for item in cls.STANDARD_SIZES:
            if item["height_min"] <= req.height_cm <= item["height_max"]:
                best_match = item["size"]
                break

        if not best_match:
            if req.height_cm < 115:
                best_match = cls.SIZE_ORDER[0]
            else:
                best_match = cls.SIZE_ORDER[-1]

        idx = cls.SIZE_ORDER.index(best_match)

        # Body build adjustments
        fit_note = f"Đề xuất cho chiều cao {req.height_cm}cm, cân nặng {req.weight_kg}kg."
        if req.body_build == "bulky":
            if idx < len(cls.SIZE_ORDER) - 1:
                idx += 1
                fit_note += " Bạn có dáng đậm người, hệ thống tự động cộng thêm 1 size để vận động thoải mái."
        elif req.body_build == "lean":
            fit_note += " Dáng người gầy, form võ phục sẽ mặc vừa chuẩn theo chiều dài ống tay và quần."

        # Child loose buffer adjustment
        if req.child_buffer:
            if idx < len(cls.SIZE_ORDER) - 1:
                idx += 1
                fit_note += " Đã cộng thêm 1 size trừ hao cho bé đang tuổi lớn."

        recommended_size = cls.SIZE_ORDER[idx]
        backup_size = cls.SIZE_ORDER[idx - 1] if idx > 0 else cls.SIZE_ORDER[1]

        return SizeRecommendationResponse(
            recommended_size=recommended_size,
            backup_size=backup_size,
            fit_note=fit_note,
            size_specs={
                "martial_art": req.martial_art,
                "height_cm": req.height_cm,
                "weight_kg": req.weight_kg,
                "body_build": req.body_build,
            },
        )
