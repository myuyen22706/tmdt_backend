import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user_token, require_role
from app.core.responses import APIResponse
from app.modules.payments.momo import (
    create_momo_payment,
    generate_mock_ipn_payload,
    verify_ipn_signature,
)
from app.modules.payments.schemas import (
    MockCallbackRequest,
    MoMoIPNPayload,
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentRecordResponse,
    RefundRequest,
)

router = APIRouter(prefix="/payments/momo", tags=["MoMo Payment & IPN (F08, F19, Mục 7)"])


@router.post("/create", response_model=APIResponse[PaymentCreateResponse])
async def create_payment(
    payload: PaymentCreateRequest,
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F08 & Mục 7: Tạo yêu cầu thanh toán MoMo (sinh chữ ký HMAC-SHA256, chuyển sang MoMo)."""
    orders_col = db["orders"]
    order = await orders_col.find_one({"order_code": payload.order_code})
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng cần thanh toán")

    if order.get("status") not in ["pending_payment", "confirmed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Đơn hàng đang ở trạng thái '{order.get('status')}', không thể tạo thanh toán.",
        )

    amount = int(order.get("total_amount", 0))
    order_info = f"Thanh toan don hang {order.get('order_code')}"

    # Gọi hàm tích hợp MoMo
    momo_resp = await create_momo_payment(
        order_id=order.get("order_code"),
        amount=amount,
        order_info=order_info,
    )

    pay_url = momo_resp.get("payUrl") or momo_resp.get("qrCodeUrl") or ""
    return APIResponse(
        success=True,
        message="Tạo yêu cầu thanh toán MoMo thành công",
        data=PaymentCreateResponse(
            order_code=order.get("order_code"),
            amount=amount,
            request_id=momo_resp.get("requestId", str(uuid.uuid4())),
            pay_url=pay_url,
            qr_code_url=momo_resp.get("qrCodeUrl"),
            message=momo_resp.get("message", "Thành công"),
        ),
    )


@router.post("/ipn")
async def momo_ipn_webhook(
    payload: MoMoIPNPayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Mục 7: Webhook IPN từ MoMo - Căn cứ DUY NHẤT để ghi nhận thanh toán.
    1. Xác minh chữ ký số HMAC-SHA256.
    2. Kiểm tra số tiền khớp với tổng giá trị đơn hàng.
    3. Xử lý lặp an toàn (Idempotency): IPN đến nhiều lần chỉ ghi nhận 1 lần.
    4. Trừ hẳn tồn kho khi thanh toán thành công (Mục 7 & F08).
    5. Lưu bản ghi thanh toán vào collection 'payments' (F19).
    """
    orders_col = db["orders"]
    products_col = db["products"]
    payments_col = db["payments"]
    movements_col = db["stock_movements"]
    now = datetime.now(timezone.utc)

    # 1. Xác minh chữ ký số HMAC-SHA256 (Mục 7 & 9)
    payload_dict = payload.model_dump()
    if not verify_ipn_signature(payload_dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chữ ký số MoMo không hợp lệ (Signature verification failed).",
        )

    # 2. Tìm đơn hàng tương ứng
    order = await orders_col.find_one({"order_code": payload.orderId})
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Đơn hàng '{payload.orderId}' không tồn tại trong hệ thống.",
        )

    # 3. Đối chiếu số tiền thanh toán (Chống gian lận - Mục 7 & 9)
    expected_amount = int(order.get("total_amount", 0))
    if payload.amount != expected_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Số tiền thanh toán ({payload.amount} VND) không khớp với giá trị đơn hàng ({expected_amount} VND).",
        )

    # 4. Xử lý lặp an toàn (Idempotency - Mục 7)
    existing_payment = await payments_col.find_one({
        "$or": [
            {"request_id": payload.requestId},
            {"momo_trans_id": str(payload.transId)},
        ]
    })

    if existing_payment or order.get("status") == "paid":
        # IPN gửi lặp lại -> Trả về thành công ngay mà không thao tác tồn kho lần thứ hai
        return {
            "resultCode": 0,
            "message": "Thông báo IPN đã được xử lý trước đó (Idempotent).",
        }

    # 5. Xử lý kết quả thanh toán
    if payload.resultCode == 0:
        # Thanh toán THÀNH CÔNG
        # Chuyển trạng thái đơn sang 'paid', trừ hẳn tồn kho
        history_entry = {
            "old_status": order.get("status"),
            "new_status": "paid",
            "changed_by": "momo_ipn",
            "timestamp": now,
            "note": f"Thanh toán MoMo thành công. TransId: {payload.transId}",
        }

        # Trừ tồn kho trong MongoDB Atlas (nếu trước đó chưa trừ)
        if order.get("status") == "pending_payment":
            for it in order.get("items", []):
                await products_col.update_one(
                    {"id": it["product_id"], "variants.sku": it["sku"]},
                    {"$inc": {"variants.$.stock": -it["quantity"]}},
                )
                await movements_col.insert_one({
                    "id": str(uuid.uuid4()),
                    "product_id": it["product_id"],
                    "sku": it["sku"],
                    "quantity_change": -it["quantity"],
                    "reason": f"Xuất kho sau khi thanh toán MoMo thành công: {order.get('order_code')}",
                    "performed_by": "momo_ipn",
                    "created_at": now,
                })

        await orders_col.update_one(
            {"order_code": payload.orderId},
            {
                "$set": {
                    "status": "paid",
                    "payment_status": "paid",
                    "updated_at": now,
                },
                "$push": {"status_history": history_entry},
            },
        )

        payment_status = "success"
    else:
        # Thanh toán THẤT BẠI HOẶC BỊ HỦY
        history_entry = {
            "old_status": order.get("status"),
            "new_status": "cancelled",
            "changed_by": "momo_ipn",
            "timestamp": now,
            "note": f"Thanh toán MoMo thất bại/hủy. Mã lỗi: {payload.resultCode} - {payload.message}",
        }

        await orders_col.update_one(
            {"order_code": payload.orderId},
            {
                "$set": {
                    "status": "cancelled",
                    "payment_status": "unpaid",
                    "updated_at": now,
                },
                "$push": {"status_history": history_entry},
            },
        )
        payment_status = "failed"

    # 6. Lưu bản ghi thanh toán vào collection 'payments' (Mục 7 & F19)
    payment_doc = {
        "id": f"pay-{uuid.uuid4().hex[:8]}",
        "order_code": payload.orderId,
        "amount": payload.amount,
        "request_id": payload.requestId,
        "momo_trans_id": str(payload.transId),
        "result_code": payload.resultCode,
        "status": payment_status,
        "raw_response": payload_dict,
        "created_at": now,
    }
    await payments_col.insert_one(payment_doc)

    return {"resultCode": 0, "message": "Xử lý IPN MoMo thành công."}


@router.post("/mock-callback")
async def mock_momo_callback(
    payload: MockCallbackRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Mục 7: Giả lập gọi IPN MoMo khi MOMO_MOCK=True phục vụ demo và kiểm thử tự động."""
    if not settings.MOMO_MOCK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ dùng được khi bật chế độ MOMO_MOCK",
        )
    orders_col = db["orders"]
    order = await orders_col.find_one({"order_code": payload.order_code})
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

    amount = int(order.get("total_amount", 0))
    ipn_data = generate_mock_ipn_payload(
        order_id=payload.order_code,
        amount=amount,
        result_code=payload.result_code,
    )

    # Chuyển qua hàm xử lý IPN chính thức
    momo_payload = MoMoIPNPayload(**ipn_data)
    result = await momo_ipn_webhook(momo_payload, db=db)
    return {
        "success": True,
        "message": "Đã giả lập IPN MoMo thành công",
        "result": result,
        "simulated_ipn": ipn_data,
    }


@router.post("/check-expired")
async def check_expired_momo_orders(db: AsyncIOMotorDatabase = Depends(get_db)):
    """F08: Quá hạn 15 phút chưa thanh toán MoMo thì tự động hủy đơn và hoàn trả tồn kho."""
    orders_col = db["orders"]
    products_col = db["products"]
    movements_col = db["stock_movements"]
    now = datetime.now(timezone.utc)
    expired_threshold = now - timedelta(minutes=15)

    cursor = orders_col.find({
        "status": "pending_payment",
        "payment_method": "MOMO",
        "created_at": {"$lte": expired_threshold},
    })
    expired_orders = await cursor.to_list(length=100)

    cancelled_count = 0
    for order in expired_orders:
        code = order.get("order_code")
        # Hoàn lại tồn kho
        for it in order.get("items", []):
            await products_col.update_one(
                {"id": it["product_id"], "variants.sku": it["sku"]},
                {"$inc": {"variants.$.stock": it["quantity"]}},
            )
            await movements_col.insert_one({
                "id": str(uuid.uuid4()),
                "product_id": it["product_id"],
                "sku": it["sku"],
                "quantity_change": it["quantity"],
                "reason": f"Hoàn kho do đơn MoMo {code} quá hạn 15 phút",
                "performed_by": "system_auto_cancel",
                "created_at": now,
            })

        history_entry = {
            "old_status": "pending_payment",
            "new_status": "cancelled",
            "changed_by": "system",
            "timestamp": now,
            "note": "Đơn hàng MoMo quá hạn 15 phút không thanh toán. Hệ thống tự động hủy đơn và hoàn tồn kho.",
        }

        await orders_col.update_one(
            {"_id": order["_id"]},
            {
                "$set": {"status": "cancelled", "updated_at": now},
                "$push": {"status_history": history_entry},
            },
        )
        cancelled_count += 1

    return {
        "success": True,
        "cancelled_count": cancelled_count,
        "message": f"Đã quét và hủy {cancelled_count} đơn hàng MoMo quá hạn 15 phút.",
    }


# ==============================================================================
# F19: Quản lý Thanh toán & Đối soát MoMo (Staff & Admin)
# ==============================================================================

@router.get("/transactions", response_model=APIResponse[List[PaymentRecordResponse]])
async def list_payment_transactions(
    order_code: Optional[str] = Query(None, description="Lọc theo mã đơn hàng"),
    current_user: dict = Depends(require_role(["admin", "staff"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F19: Xem danh sách giao dịch MoMo, đối soát với đơn hàng."""
    payments_col = db["payments"]
    filter_q = {}
    if order_code:
        filter_q["order_code"] = order_code

    cursor = payments_col.find(filter_q).sort("created_at", -1)
    docs = await cursor.to_list(length=100)

    results = []
    for d in docs:
        results.append(
            PaymentRecordResponse(
                id=d.get("id", str(d.get("_id", ""))),
                order_code=d.get("order_code", ""),
                amount=int(d.get("amount", 0)),
                request_id=d.get("request_id", ""),
                momo_trans_id=d.get("momo_trans_id"),
                result_code=int(d.get("result_code", 0)),
                status=d.get("status", "success"),
                raw_response=d.get("raw_response"),
                created_at=d.get("created_at", datetime.now(timezone.utc)),
            )
        )

    return APIResponse(
        success=True,
        message="Lấy danh sách giao dịch MoMo thành công",
        data=results,
    )


@router.post("/transactions/{payment_id}/refund", response_model=APIResponse[dict])
async def mark_manual_refund(
    payment_id: str,
    payload: RefundRequest,
    current_user: dict = Depends(require_role(["admin"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F19: Đánh dấu hoàn tiền thủ công cho giao dịch MoMo (chỉ Admin)."""
    payments_col = db["payments"]
    now = datetime.now(timezone.utc)

    payment = await payments_col.find_one({"id": payment_id})
    if not payment:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi thanh toán")

    await payments_col.update_one(
        {"id": payment_id},
        {
            "$set": {
                "status": "refunded",
                "refund_reason": payload.reason,
                "refunded_by": current_user.get("phone", "admin"),
                "refunded_at": now,
            }
        },
    )

    # Ghi nhận Audit Log F23
    from app.core.activity import record_activity
    await record_activity(
        db=db,
        actor=current_user.get("phone", current_user.get("sub", "admin")),
        actor_role=current_user.get("role", "admin"),
        action="REFUND_ORDER",
        target_type="payment",
        target_id=payment_id,
        details={
            "order_code": payment.get("order_code"),
            "amount": payment.get("amount"),
            "reason": payload.reason,
        },
    )

    return APIResponse(
        success=True,
        message="Đã đánh dấu hoàn tiền thủ công thành công",
        data={"payment_id": payment_id, "status": "refunded"},
    )
