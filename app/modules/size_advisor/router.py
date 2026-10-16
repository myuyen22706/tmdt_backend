import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.responses import APIResponse
from app.modules.size_advisor.schemas import (
    SizeConsultationRequest,
    SizeRecommendationResponse,
    StudentProfileCreate,
    StudentProfileResponse,
    StudentProfileUpdate,
)

router = APIRouter(prefix="/size-advisor", tags=["Size Advisor & Profiles (F04, F05)"])


@router.post("/recommend", response_model=APIResponse[SizeRecommendationResponse])
async def recommend_size(
    request: SizeConsultationRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F04: Tư vấn size thông minh theo nhân trắc học đối chiếu bảng size trong CSDL.
    - Quản trị sửa được bảng size trong DB.
    - Nằm giữa hai size thì gợi ý size lớn hơn kèm ghi chú.
    - Xử lý các trường hợp ngoài bảng size.
    """
    charts_col = db["size_charts"]
    charts = await charts_col.find({"martial_art_id": request.martial_art}).sort("height_min_cm", 1).to_list(length=50)

    if not charts:
        # Fallback tìm bảng size chung nếu môn chưa có bảng riêng
        charts = await charts_col.find({}).sort("height_min_cm", 1).to_list(length=50)

    # Nếu DB chưa có bảng size, dùng bảng mặc định
    if not charts:
        default_sizes = [
            {"size_name": "Size 00", "height_min_cm": 100, "height_max_cm": 115, "weight_min_kg": 15, "weight_max_kg": 22},
            {"size_name": "Size 0", "height_min_cm": 115, "height_max_cm": 125, "weight_min_kg": 20, "weight_max_kg": 28},
            {"size_name": "Size 1", "height_min_cm": 125, "height_max_cm": 135, "weight_min_kg": 26, "weight_max_kg": 35},
            {"size_name": "Size 2", "height_min_cm": 135, "height_max_cm": 145, "weight_min_kg": 33, "weight_max_kg": 42},
            {"size_name": "Size 3", "height_min_cm": 145, "height_max_cm": 155, "weight_min_kg": 40, "weight_max_kg": 50},
            {"size_name": "Size 4", "height_min_cm": 155, "height_max_cm": 165, "weight_min_kg": 48, "weight_max_kg": 60},
            {"size_name": "Size 5", "height_min_cm": 165, "height_max_cm": 172, "weight_min_kg": 58, "weight_max_kg": 70},
            {"size_name": "Size 6", "height_min_cm": 172, "height_max_cm": 180, "weight_min_kg": 68, "weight_max_kg": 82},
            {"size_name": "Size 7", "height_min_cm": 180, "height_max_cm": 195, "weight_min_kg": 80, "weight_max_kg": 105},
        ]
        charts = default_sizes

    h = request.height_cm
    w = request.weight_kg

    min_h = charts[0]["height_min_cm"]
    max_h = charts[-1]["height_max_cm"]
    min_w = charts[0]["weight_min_kg"]
    max_w = charts[-1]["weight_max_kg"]

    # 1. Trường hợp ngoài bảng size (dưới chuẩn nhỏ nhất hoặc vượt chuẩn lớn nhất)
    if h < min_h or w < min_w:
        rec_size = charts[0]["size_name"]
        backup = charts[1]["size_name"] if len(charts) > 1 else rec_size
        note = (
            f"Chỉ số chiều cao ({h}cm) hoặc cân nặng ({w}kg) nhỏ hơn giới hạn chuẩn của bảng size. "
            f"Hệ thống đề xuất size nhỏ nhất ({rec_size}) hoặc liên hệ cửa hàng để may đo riêng cho võ sinh nhí."
        )
        return APIResponse(
            success=True,
            message="Tư vấn size thành công (Ngoài bảng size - Thể trạng nhỏ)",
            data=SizeRecommendationResponse(
                recommended_size=rec_size,
                backup_size=backup,
                fit_note=note,
                is_out_of_range=True,
                size_specs={"height_cm": h, "weight_kg": w, "martial_art": request.martial_art},
            ),
        )

    if h > max_h or w > max_w:
        rec_size = charts[-1]["size_name"]
        backup = charts[-2]["size_name"] if len(charts) > 1 else rec_size
        note = (
            f"Chỉ số chiều cao ({h}cm) hoặc cân nặng ({w}kg) vượt trên giới hạn bảng size thông thường. "
            f"Đề xuất chọn size lớn nhất ({rec_size}) hoặc liên hệ xưởng may đo theo kích thước riêng."
        )
        return APIResponse(
            success=True,
            message="Tư vấn size thành công (Ngoài bảng size - Thể trạng lớn)",
            data=SizeRecommendationResponse(
                recommended_size=rec_size,
                backup_size=backup,
                fit_note=note,
                is_out_of_range=True,
                size_specs={"height_cm": h, "weight_kg": w, "martial_art": request.martial_art},
            ),
        )

    # 2. Tìm size phù hợp theo chiều cao và cân nặng
    height_idx = None
    weight_idx = None

    for idx, c in enumerate(charts):
        if c["height_min_cm"] <= h <= c["height_max_cm"]:
            height_idx = idx
            break

    for idx, c in enumerate(charts):
        if c["weight_min_kg"] <= w <= c["weight_max_kg"]:
            weight_idx = idx
            break

    # Nếu không tìm thấy chính xác mốc, tìm mốc tiệm cận gần nhất
    if height_idx is None:
        for idx in range(len(charts) - 1):
            if charts[idx]["height_max_cm"] <= h <= charts[idx + 1]["height_min_cm"]:
                # Nằm ngay ranh giới giữa 2 size -> chọn size lớn hơn
                height_idx = idx + 1
                break
        if height_idx is None:
            height_idx = 0

    if weight_idx is None:
        weight_idx = height_idx

    # Kiểm tra quy tắc: "Nằm giữa hai size thì gợi ý size lớn hơn kèm ghi chú" (F04)
    # Ví dụ: Chiều cao ở size 1 nhưng cân nặng ở size 2, hoặc chiều cao sát ranh giới giữa 2 size
    is_between_sizes = False
    notes_list = [f"Chỉ số: Chiều cao {h}cm, cân nặng {w}kg."]

    chosen_idx = height_idx
    if weight_idx > height_idx:
        # Cân nặng đậm hơn chiều cao -> Chọn size lớn hơn
        chosen_idx = weight_idx
        is_between_sizes = True
        notes_list.append("Chỉ số cân nặng nằm ở khung size lớn hơn. Hệ thống ưu tiên gợi ý size lớn hơn để đảm bảo độ rộng rãi khi di chuyển tấn pháp.")
    elif weight_idx < height_idx:
        # Chiều cao dài hơn nhưng dáng gầy -> Chọn size theo chiều cao để quần áo không bị cộc
        chosen_idx = height_idx
        notes_list.append("Dáng người thanh mảnh, hệ thống ưu tiên chiều dài vạt áo và ống quần theo chiều cao.")

    # Kiểm tra vị trí sát ranh giới trên của size hiện tại
    curr_chart = charts[chosen_idx]
    if (curr_chart["height_max_cm"] - h) <= 2.0 and chosen_idx < len(charts) - 1:
        chosen_idx += 1
        is_between_sizes = True
        notes_list.append("Chiều cao nằm sát ranh giới giữa hai size, hệ thống gợi ý size lớn hơn kèm trừ hao.")

    # Tùy chọn mua rộng cho trẻ em đang lớn
    if request.child_buffer and chosen_idx < len(charts) - 1:
        chosen_idx += 1
        notes_list.append("Đã cộng thêm 1 size trừ hao cho võ sinh đang tuổi phát triển nhanh.")

    rec_size = charts[chosen_idx]["size_name"]
    backup_size = charts[chosen_idx - 1]["size_name"] if chosen_idx > 0 else (
        charts[chosen_idx + 1]["size_name"] if chosen_idx < len(charts) - 1 else None
    )

    fit_note = " ".join(notes_list)

    return APIResponse(
        success=True,
        message="Gợi ý size phù hợp thành công",
        data=SizeRecommendationResponse(
            recommended_size=rec_size,
            backup_size=backup_size,
            fit_note=fit_note,
            is_out_of_range=False,
            size_specs={
                "height_cm": h,
                "weight_kg": w,
                "martial_art": request.martial_art,
                "is_between_sizes": is_between_sizes,
            },
        ),
    )


# ==============================================================================
# F05: Quản lý Hồ sơ Size (Dành cho khách hàng lưu số đo võ sinh/con)
# ==============================================================================

@router.get("/profiles", response_model=APIResponse[List[StudentProfileResponse]])
async def list_student_profiles(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F05: Lấy danh sách hồ sơ size của khách hàng. Tự động nhắc đo lại nếu hồ sơ quá 6 tháng."""
    profiles_col = db["student_profiles"]
    user_id = current_user.get("id", str(current_user.get("_id", "")))

    cursor = profiles_col.find({"user_id": user_id}).sort("created_at", -1)
    docs = await cursor.to_list(length=50)

    now = datetime.now(timezone.utc)
    results = []

    for d in docs:
        measured_date = d.get("measured_date", d.get("created_at", now))
        if measured_date.tzinfo is None:
            measured_date = measured_date.replace(tzinfo=timezone.utc)

        days_passed = max(0, (now - measured_date).days)
        needs_remeasure = days_passed > 180  # Quá 6 tháng
        alert_msg = None
        if needs_remeasure:
            alert_msg = (
                f"Hồ sơ đã được đo cách đây {days_passed} ngày (quá 6 tháng). "
                "Trẻ em phát triển nhanh, vui lòng cập nhật lại chiều cao và cân nặng để được tư vấn size chính xác nhất."
            )

        results.append(
            StudentProfileResponse(
                id=d.get("id", str(d.get("_id", ""))),
                user_id=user_id,
                student_name=d.get("student_name", ""),
                birth_year=d.get("birth_year"),
                martial_art=d.get("martial_art", "vovinam"),
                height_cm=float(d.get("height_cm", 0)),
                weight_kg=float(d.get("weight_kg", 0)),
                recommended_size=d.get("recommended_size"),
                measured_date=measured_date,
                days_since_measured=days_passed,
                needs_remeasure=needs_remeasure,
                remeasure_alert=alert_msg,
            )
        )

    return APIResponse(
        success=True,
        message="Lấy danh sách hồ sơ size thành công",
        data=results,
    )


@router.post("/profiles", response_model=APIResponse[StudentProfileResponse])
async def create_student_profile(
    payload: StudentProfileCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F05: Lưu hồ sơ size mới cho con/võ sinh."""
    profiles_col = db["student_profiles"]
    user_id = current_user.get("id", str(current_user.get("_id", "")))
    now = datetime.now(timezone.utc)

    profile_id = str(uuid.uuid4())
    doc = {
        "id": profile_id,
        "user_id": user_id,
        "student_name": payload.student_name,
        "birth_year": payload.birth_year,
        "martial_art": payload.martial_art,
        "height_cm": payload.height_cm,
        "weight_kg": payload.weight_kg,
        "recommended_size": payload.recommended_size,
        "measured_date": now,
        "created_at": now,
    }

    await profiles_col.insert_one(doc)

    return APIResponse(
        success=True,
        message="Lưu hồ sơ size võ sinh thành công",
        data=StudentProfileResponse(
            id=profile_id,
            user_id=user_id,
            student_name=payload.student_name,
            birth_year=payload.birth_year,
            martial_art=payload.martial_art,
            height_cm=payload.height_cm,
            weight_kg=payload.weight_kg,
            recommended_size=payload.recommended_size,
            measured_date=now,
            days_since_measured=0,
            needs_remeasure=False,
            remeasure_alert=None,
        ),
    )


@router.put("/profiles/{profile_id}", response_model=APIResponse[dict])
async def update_student_profile(
    profile_id: str,
    payload: StudentProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F05: Cập nhật lại số đo cho hồ sơ size (đo lại)."""
    profiles_col = db["student_profiles"]
    user_id = current_user.get("id", str(current_user.get("_id", "")))

    existing = await profiles_col.find_one({"id": profile_id, "user_id": user_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hồ sơ size hoặc không có quyền thao tác",
        )

    now = datetime.now(timezone.utc)
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    # Cập nhật ngày đo mới nhất
    if "height_cm" in update_data or "weight_kg" in update_data:
        update_data["measured_date"] = now

    await profiles_col.update_one({"id": profile_id}, {"$set": update_data})
    return APIResponse(
        success=True,
        message="Cập nhật hồ sơ size thành công",
        data={"updated_id": profile_id},
    )


@router.delete("/profiles/{profile_id}", response_model=APIResponse[dict])
async def delete_student_profile(
    profile_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F05: Khách xóa hồ sơ size."""
    profiles_col = db["student_profiles"]
    user_id = current_user.get("id", str(current_user.get("_id", "")))

    res = await profiles_col.delete_one({"id": profile_id, "user_id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hồ sơ hoặc bạn không có quyền xóa",
        )

    return APIResponse(
        success=True,
        message="Đã xóa hồ sơ size thành công",
        data={"deleted_id": profile_id},
    )


# ==============================================================================
# Bảng Size CSDL (F04, F16: Quản trị viên sửa được bảng size)
# ==============================================================================

@router.get("/chart", response_model=APIResponse[List[dict]])
async def get_size_chart(
    martial_art: str = Query("vovinam", description="Môn võ: vovinam, taekwondo, karate, vo_co_truyen"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Lấy bảng size chuẩn theo môn võ từ database MongoDB Atlas."""
    charts_col = db["size_charts"]
    cursor = charts_col.find({"martial_art_id": martial_art}).sort("height_min_cm", 1)
    items = await cursor.to_list(length=50)

    data = []
    for it in items:
        data.append({
            "id": it.get("id", str(it.get("_id", ""))),
            "martial_art_id": it.get("martial_art_id"),
            "size": it.get("size_name"),
            "height_min_cm": it.get("height_min_cm"),
            "height_max_cm": it.get("height_max_cm"),
            "weight_min_kg": it.get("weight_min_kg"),
            "weight_max_kg": it.get("weight_max_kg"),
            "age_min": it.get("age_min"),
            "age_max": it.get("age_max"),
            "note": it.get("fit_note"),
        })

    return APIResponse(
        success=True,
        message=f"Bảng size môn {martial_art}",
        data=data,
    )


@router.post("/chart", response_model=APIResponse[dict])
async def create_or_update_size_chart_entry(
    entry: dict,
    current_user: dict = Depends(require_role(["admin"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F16: Quản trị viên thêm/cập nhật mốc trong bảng size."""
    charts_col = db["size_charts"]
    entry_id = entry.get("id", str(uuid.uuid4()))
    entry["id"] = entry_id

    await charts_col.update_one(
        {"id": entry_id},
        {"$set": entry},
        upsert=True,
    )
    return APIResponse(
        success=True,
        message="Cập nhật mốc bảng size thành công",
        data={"id": entry_id},
    )
