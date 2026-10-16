import csv
import io
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_db
from app.core.dependencies import get_current_user_token, require_role
from app.core.responses import APIResponse
from app.modules.dojos.schemas import (
    CampaignCreate,
    CampaignResponse,
    ClubRegister,
    ClubResponse,
    StudentOrderCreate,
    StudentOrderResponse,
)
from app.modules.payments.momo import create_momo_payment

router = APIRouter(prefix="/dojos", tags=["Dojos & B2B Campaigns (F11 - F15)"])


def _calculate_discount_tier(quantity: int) -> int:
    """Xác định bậc chiết khấu sỉ theo số lượng dự kiến (Mục 2 & docs/gia-dinh.md):
    - 10-29 bộ: giảm 10%
    - 30-49 bộ: giảm 15%
    - 50-99 bộ: giảm 20%
    - >= 100 bộ: giảm 25%
    """
    if quantity >= 100:
        return 25
    elif quantity >= 50:
        return 20
    elif quantity >= 30:
        return 15
    elif quantity >= 10:
        return 10
    return 0


# ==============================================================================
# F11: Đăng ký & Phê duyệt Võ đường
# ==============================================================================

@router.post("/clubs", response_model=APIResponse[ClubResponse])
async def register_club(
    payload: ClubRegister,
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F11: Đăng ký thông tin võ đường / câu lạc bộ mới.
    - Quản trị viên duyệt mới kích hoạt hoạt động.
    """
    clubs_col = db["clubs"]
    now = datetime.now(timezone.utc)
    club_id = f"club-{uuid.uuid4().hex[:8]}"

    doc = payload.model_dump()
    doc["id"] = club_id
    doc["status"] = "pending"  # Chờ quản trị duyệt
    doc["created_at"] = now
    doc["updated_at"] = now

    await clubs_col.insert_one(doc)

    return APIResponse(
        success=True,
        message="Đăng ký võ đường thành công, đang chờ Quản trị viên xét duyệt (F11)",
        data=ClubResponse(**doc),
    )


@router.get("/clubs", response_model=APIResponse[List[ClubResponse]])
async def list_clubs(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Lấy danh sách các võ đường / CLB."""
    clubs_col = db["clubs"]
    filter_q = {}
    if status_filter:
        filter_q["status"] = status_filter

    cursor = clubs_col.find(filter_q).sort("created_at", -1)
    docs = await cursor.to_list(length=100)
    for d in docs:
        d["_id"] = str(d["_id"])
    return APIResponse(success=True, message="Danh sách võ đường", data=[ClubResponse(**d) for d in docs])


@router.patch("/clubs/{club_id}/approve", response_model=APIResponse[ClubResponse])
async def approve_club(
    club_id: str,
    action: str = Query("approve", description="approve hoặc reject"),
    current_user: dict = Depends(require_role(["admin"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F11: Quản trị viên duyệt kích hoạt võ đường."""
    clubs_col = db["clubs"]
    new_status = "active" if action == "approve" else "rejected"

    res = await clubs_col.update_one(
        {"id": club_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy võ đường")

    updated = await clubs_col.find_one({"id": club_id})

    # Ghi nhận Audit Log F23
    from app.core.activity import record_activity
    await record_activity(
        db=db,
        actor=current_user.get("phone", current_user.get("sub", "admin")),
        actor_role=current_user.get("role", "admin"),
        action="APPROVE_DOJO" if action == "approve" else "REJECT_DOJO",
        target_type="dojo",
        target_id=club_id,
        details={"status": new_status, "club_name": updated.get("name") if updated else None},
    )

    return APIResponse(
        success=True,
        message=f"Đã duyệt võ đường sang trạng thái '{new_status}'",
        data=ClubResponse(**updated),
    )


# ==============================================================================
# F12: Tạo đợt đặt hàng chung (Campaign)
# ==============================================================================

@router.post("/campaigns", response_model=APIResponse[CampaignResponse])
async def create_campaign(
    payload: CampaignCreate,
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F12: Huấn luyện viên tạo đợt đặt hàng chung.
    - Xác định bậc chiết khấu sỉ theo số lượng dự kiến.
    - Sinh đường dẫn riêng và mã QR chia sẻ cho phụ huynh.
    """
    clubs_col = db["clubs"]
    campaigns_col = db["club_campaigns"]
    now = datetime.now(timezone.utc)

    club = await clubs_col.find_one({"id": payload.club_id})
    if not club:
        raise HTTPException(status_code=404, detail="Không tìm thấy võ đường")
    if club.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Võ đường chưa được Quản trị viên phê duyệt kích hoạt",
        )

    discount_percent = _calculate_discount_tier(payload.target_quantity)
    code = f"CP-{club.get('martial_art_id', 'VO')[:3].upper()}-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:4].upper()}"
    campaign_url = f"http://localhost:3000/clubs/campaign/{code}"
    qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={campaign_url}"

    campaign_id = f"cmp-{uuid.uuid4().hex[:8]}"
    doc = {
        "id": campaign_id,
        "campaign_code": code,
        "club_id": payload.club_id,
        "club_name": club.get("club_name"),
        "campaign_title": payload.campaign_title,
        "applicable_product_ids": payload.applicable_product_ids,
        "target_quantity": payload.target_quantity,
        "discount_percent": discount_percent,
        "deadline": payload.deadline,
        "has_custom_logo": payload.has_custom_logo,
        "allow_club_consolidated_payment": payload.allow_club_consolidated_payment,
        "campaign_url": campaign_url,
        "qr_code_url": qr_code_url,
        "status": "open",
        "total_ordered": 0,
        "total_amount": 0,
        "deposit_amount": 0,
        "deposit_paid": False,
        "remaining_amount_paid": False,
        "created_at": now,
        "updated_at": now,
    }

    await campaigns_col.insert_one(doc)

    return APIResponse(
        success=True,
        message="Tạo đợt đặt hàng chung thành công",
        data=CampaignResponse(**doc),
    )


@router.get("/campaigns/{code}", response_model=APIResponse[CampaignResponse])
async def get_campaign_detail(code: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """F13: Phụ huynh mở đường dẫn đợt hàng xem thông tin chi tiết."""
    campaigns_col = db["club_campaigns"]
    doc = await campaigns_col.find_one({"$or": [{"campaign_code": code}, {"id": code}]})
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy đợt đặt hàng")

    return APIResponse(success=True, message="Thông tin đợt đặt hàng", data=CampaignResponse(**doc))


# ==============================================================================
# F13: Phụ huynh đặt theo đợt
# ==============================================================================

@router.post("/campaigns/{code}/orders", response_model=APIResponse[StudentOrderResponse])
async def parent_order_in_campaign(
    code: str,
    payload: StudentOrderCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F13: Phụ huynh đặt võ phục theo đợt của võ đường.
    - Áp dụng bậc giá sỉ (chiết khấu) của đợt hàng.
    - Tùy chọn thanh toán MoMo ngay hoặc võ đường thanh toán gộp.
    """
    campaigns_col = db["club_campaigns"]
    products_col = db["products"]
    student_orders_col = db["student_orders"]
    now = datetime.now(timezone.utc)

    campaign = await campaigns_col.find_one({"$or": [{"campaign_code": code}, {"id": code}]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Không tìm thấy đợt đặt hàng")
    if campaign.get("status") != "open":
        raise HTTPException(status_code=400, detail="Đợt đặt hàng này đã đóng sổ")

    # Kiểm tra sản phẩm
    product = await products_col.find_one({"id": payload.product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")

    base_price = int(product.get("price", 0))
    discount_percent = campaign.get("discount_percent", 0)
    # Giá sỉ đã chiết khấu
    discounted_price = int(base_price * (100 - discount_percent) / 100)

    emb_fee = 30000 if payload.is_embroidered else 0
    total_amount = discounted_price + emb_fee

    pay_method = "CLUB_CONSOLIDATED" if payload.club_consolidated_payment else "MOMO"

    order_id = f"so-{uuid.uuid4().hex[:8]}"
    order_code = f"SO-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

    doc = {
        "id": order_id,
        "campaign_id": campaign.get("id"),
        "campaign_code": campaign.get("campaign_code"),
        "order_code": order_code,
        "student_name": payload.student_name,
        "parent_phone": payload.parent_phone,
        "product_id": payload.product_id,
        "product_name": product.get("name"),
        "sku": payload.sku,
        "size": payload.size,
        "color": payload.color,
        "price": discounted_price,
        "is_embroidered": payload.is_embroidered,
        "embroidery_name": payload.embroidery_name,
        "embroidery_fee": emb_fee,
        "total_amount": total_amount,
        "payment_method": pay_method,
        "is_paid": False if pay_method == "CLUB_CONSOLIDATED" else True,  # MoMo giả lập
        "created_at": now,
    }

    await student_orders_col.insert_one(doc)

    # Cập nhật số lượng và tổng tiền trong campaign
    await campaigns_col.update_one(
        {"id": campaign.get("id")},
        {
            "$inc": {"total_ordered": 1, "total_amount": total_amount},
            "$set": {"updated_at": now},
        },
    )

    return APIResponse(
        success=True,
        message="Phụ huynh đặt hàng theo đợt thành công (F13)",
        data=StudentOrderResponse(
            id=order_id,
            order_code=order_code,
            student_name=payload.student_name,
            parent_phone=payload.parent_phone,
            product_name=product.get("name"),
            sku=payload.sku,
            size=payload.size,
            price=discounted_price,
            embroidery_fee=emb_fee,
            total_amount=total_amount,
            payment_method=pay_method,
            is_paid=doc["is_paid"],
            created_at=now,
        ),
    )


# ==============================================================================
# F14: Theo dõi đợt, Xuất CSV, Đóng đợt gom lô chung
# ==============================================================================

@router.get("/campaigns/{code}/orders", response_model=APIResponse[List[StudentOrderResponse]])
async def list_campaign_orders(
    code: str,
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F14: Huấn luyện viên theo dõi danh sách học viên đặt hàng của đợt."""
    campaigns_col = db["club_campaigns"]
    student_orders_col = db["student_orders"]

    campaign = await campaigns_col.find_one({"$or": [{"campaign_code": code}, {"id": code}]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Không tìm thấy đợt đặt hàng")

    cursor = student_orders_col.find({"campaign_id": campaign.get("id")}).sort("created_at", -1)
    orders = await cursor.to_list(length=500)

    results = []
    for o in orders:
        results.append(
            StudentOrderResponse(
                id=o.get("id", str(o.get("_id", ""))),
                order_code=o.get("order_code", ""),
                student_name=o.get("student_name", ""),
                parent_phone=o.get("parent_phone", ""),
                product_name=o.get("product_name", ""),
                sku=o.get("sku", ""),
                size=o.get("size", ""),
                price=int(o.get("price", 0)),
                embroidery_fee=int(o.get("embroidery_fee", 0)),
                total_amount=int(o.get("total_amount", 0)),
                payment_method=o.get("payment_method", "MOMO"),
                is_paid=o.get("is_paid", False),
                created_at=o.get("created_at", datetime.now(timezone.utc)),
            )
        )

    return APIResponse(success=True, message="Danh sách đơn của đợt hàng", data=results)


@router.get("/campaigns/{code}/export-csv")
async def export_campaign_orders_csv(code: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """F14: Xuất danh sách đơn của đợt thành file CSV (hỗ trợ tiếng Việt UTF-8 BOM)."""
    campaigns_col = db["club_campaigns"]
    student_orders_col = db["student_orders"]

    campaign = await campaigns_col.find_one({"$or": [{"campaign_code": code}, {"id": code}]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Không tìm thấy đợt đặt hàng")

    cursor = student_orders_col.find({"campaign_id": campaign.get("id")}).sort("created_at", 1)
    orders = await cursor.to_list(length=1000)

    output = io.StringIO()
    # Ghi UTF-8 BOM để Excel hiển thị đúng tiếng Việt
    output.write("\ufeff")
    writer = csv.writer(output)

    # Tiêu đề cột
    writer.writerow([
        "STT",
        "Mã Đơn",
        "Tên Võ Sinh",
        "SĐT Phụ Huynh",
        "Sản Phẩm",
        "Size",
        "Thêu Tên",
        "Đơn Giá (VND)",
        "Hình Thức",
        "Trạng Thái Thanh Toán",
        "Thời Điểm Đặt",
    ])

    for idx, o in enumerate(orders, start=1):
        emb_text = o.get("embroidery_name") if o.get("is_embroidered") else "Không"
        pay_status = "Đã thanh toán" if o.get("is_paid") else "Chưa thanh toán (Thanh toán gộp)"
        pay_method_vn = "MoMo" if o.get("payment_method") == "MOMO" else "Võ đường thanh toán gộp"
        time_str = o.get("created_at").strftime("%d/%m/%Y %H:%M") if o.get("created_at") else ""

        writer.writerow([
            idx,
            o.get("order_code"),
            o.get("student_name"),
            o.get("parent_phone"),
            o.get("product_name"),
            o.get("size"),
            emb_text,
            f"{o.get('total_amount', 0):,}",
            pay_method_vn,
            pay_status,
            time_str,
        ])

    csv_data = output.getvalue()
    filename = f"danh-sach-don-{code}.csv"

    return Response(
        content=csv_data.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/campaigns/{code}/close", response_model=APIResponse[dict])
async def close_campaign_and_create_batch(code: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """F14: Đóng đợt đặt hàng và gom thành một lô giao chung về võ đường."""
    campaigns_col = db["club_campaigns"]
    clubs_col = db["clubs"]
    now = datetime.now(timezone.utc)

    campaign = await campaigns_col.find_one({"$or": [{"campaign_code": code}, {"id": code}]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Không tìm thấy đợt đặt hàng")

    club = await clubs_col.find_one({"id": campaign.get("club_id")})
    total_amount = int(campaign.get("total_amount", 0))
    # Yêu cầu đặt cọc 50% qua MoMo khi đóng đợt (F15)
    deposit_amount = int(total_amount * 0.5)

    batch_tracking = f"BATCH-SHIP-{uuid.uuid4().hex[:8].upper()}"

    await campaigns_col.update_one(
        {"id": campaign.get("id")},
        {
            "$set": {
                "status": "closed",
                "deposit_amount": deposit_amount,
                "consignment_batch": {
                    "batch_code": f"LO-GOM-{code}",
                    "tracking_code": batch_tracking,
                    "destination_address": club.get("address") if club else "Võ đường",
                    "coach_name": club.get("coach_name") if club else "",
                    "total_quantity": campaign.get("total_ordered", 0),
                    "total_amount": total_amount,
                    "deposit_amount": deposit_amount,
                    "closed_at": now,
                },
                "updated_at": now,
            }
        },
    )

    return APIResponse(
        success=True,
        message=f"Đã đóng đợt đặt hàng và tạo lô gom chung về địa chỉ: {club.get('address') if club else 'Võ đường'}",
        data={
            "campaign_code": code,
            "status": "closed",
            "total_ordered": campaign.get("total_ordered", 0),
            "total_amount": total_amount,
            "deposit_amount": deposit_amount,
            "batch_tracking": batch_tracking,
        },
    )


# ==============================================================================
# F15: Thanh toán gộp & Đặt cọc 50% qua MoMo
# ==============================================================================

@router.post("/campaigns/{code}/deposit-momo", response_model=APIResponse[dict])
async def deposit_campaign_momo(code: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """F15: Võ đường đặt cọc 50% qua MoMo khi đóng đợt."""
    campaigns_col = db["club_campaigns"]
    campaign = await campaigns_col.find_one({"$or": [{"campaign_code": code}, {"id": code}]})
    if not campaign:
        raise HTTPException(status_code=404, detail="Không tìm thấy đợt đặt hàng")

    deposit_amount = int(campaign.get("deposit_amount", campaign.get("total_amount", 0) * 0.5))
    if deposit_amount <= 0:
        deposit_amount = 100000  # Mặc định tối thiểu nếu chưa có đơn

    momo_resp = await create_momo_payment(
        order_id=f"DEP-{code}",
        amount=deposit_amount,
        order_info=f"Dat coc 50% dot hang chung {code}",
    )

    return APIResponse(
        success=True,
        message="Tạo yêu cầu thanh toán đặt cọc 50% qua MoMo thành công",
        data={
            "campaign_code": code,
            "deposit_amount": deposit_amount,
            "pay_url": momo_resp.get("payUrl"),
            "qr_code_url": momo_resp.get("qrCodeUrl"),
        },
    )


@router.post("/campaigns/{code}/confirm-deposit", response_model=APIResponse[dict])
async def confirm_deposit(code: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    """F15: Xác nhận võ đường đã hoàn tất đặt cọc 50%."""
    campaigns_col = db["club_campaigns"]
    now = datetime.now(timezone.utc)

    await campaigns_col.update_one(
        {"$or": [{"campaign_code": code}, {"id": code}]},
        {"$set": {"deposit_paid": True, "updated_at": now}},
    )

    return APIResponse(
        success=True,
        message="Xác nhận đặt cọc 50% thành công (F15)",
        data={"campaign_code": code, "deposit_paid": True},
    )


@router.post("/campaigns/{code}/record-final-payment", response_model=APIResponse[dict])
async def record_final_payment(
    code: str,
    current_user: dict = Depends(require_role(["admin", "staff"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F15: Quản trị viên/Nhân viên ghi nhận thanh toán 50% còn lại khi giao hàng tận nơi."""
    campaigns_col = db["club_campaigns"]
    now = datetime.now(timezone.utc)

    await campaigns_col.update_one(
        {"$or": [{"campaign_code": code}, {"id": code}]},
        {"$set": {"remaining_amount_paid": True, "status": "delivered", "updated_at": now}},
    )

    return APIResponse(
        success=True,
        message="Đã ghi nhận thanh toán phần còn lại và hoàn tất giao hàng lô gom (F15)",
        data={"campaign_code": code, "status": "delivered", "remaining_amount_paid": True},
    )
