import random
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_db
from app.core.dependencies import get_current_user_token, require_role
from app.core.responses import APIResponse
from app.modules.orders.schemas import (
    OrderCreate,
    OrderResponse,
    OrderStatusUpdateRequest,
)
from app.modules.shipping.provider import shipping_service

router = APIRouter(prefix="/orders", tags=["Orders, Inventory & Checkout (F08, F09, F17)"])

# Luồng chuyển đổi trạng thái hợp lệ theo Mục 6
VALID_TRANSITIONS = {
    "pending_payment": ["paid", "cancelled"],
    "confirmed": ["processing", "cancelled"],
    "paid": ["processing", "cancelled"],
    "processing": ["shipping", "cancelled"],
    "shipping": ["delivered"],
    "delivered": ["completed", "return_requested"],
    "return_requested": ["returned", "completed"],
    "completed": [],
    "cancelled": [],
    "returned": [],
}


def _generate_order_code() -> str:
    """Sinh mã đơn theo định dạng chuẩn Mục 6: DT-YYYYMMDD-XXXX."""
    date_str = datetime.now().strftime("%Y%m%d")
    random_str = uuid.uuid4().hex[:4].upper()
    return f"DT-{date_str}-{random_str}"


def _format_order(doc: dict) -> OrderResponse:
    addr = doc.get("shipping_address", {})
    if isinstance(addr, dict):
        addr_str = f"{addr.get('street_address', '')}, {addr.get('ward', '')}, {addr.get('district', '')}, {addr.get('city_province', '')}"
    else:
        addr_str = str(addr)

    return OrderResponse(
        id=doc.get("id", str(doc.get("_id", ""))),
        order_code=doc.get("order_code", ""),
        user_id=doc.get("user_id"),
        channel=doc.get("channel", "retail"),
        customer_name=doc.get("customer_name", ""),
        customer_phone=doc.get("customer_phone", ""),
        customer_email=doc.get("customer_email"),
        shipping_address_full=addr_str,
        subtotal=int(doc.get("subtotal", 0)),
        shipping_fee=int(doc.get("shipping_fee", 0)),
        discount_amount=int(doc.get("discount_amount", 0)),
        embroidery_total=int(doc.get("embroidery_total", 0)),
        total_amount=int(doc.get("total_amount", 0)),
        payment_method=doc.get("payment_method", "COD"),
        payment_status=doc.get("payment_status", "unpaid"),
        status=doc.get("status", "pending_payment"),
        items=doc.get("items", []),
        tracking_code=doc.get("tracking_code"),
        status_history=doc.get("status_history", []),
        created_at=doc.get("created_at", datetime.now(timezone.utc)),
    )


@router.post("", response_model=APIResponse[OrderResponse])
async def create_order(
    payload: OrderCreate,
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F08: Đặt hàng (COD & MoMo).
    - Ràng buộc F07: Đơn có hàng thêu KHÔNG CHO CHỌN thanh toán COD.
    - Đơn COD: Trừ tồn kho nguyên tử (atomic) ngay khi tạo đơn, ghi nhận StockMovement.
    - Tính phí giao hàng theo mô-đun vận chuyển MockShippingProvider (Freeship >= 500k).
    - Mã đơn dạng DT-YYYYMMDD-XXXX (Mục 6).
    """
    products_col = db["products"]
    orders_col = db["orders"]
    movements_col = db["stock_movements"]
    now = datetime.now(timezone.utc)

    # 1. Kiểm tra ràng buộc F07: Hàng thêu không được chọn COD
    has_embroidered_item = any(item.is_embroidered for item in payload.items)
    if has_embroidered_item and payload.payment_method.upper() == "COD":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đơn hàng có sản phẩm thêu tên riêng yêu cầu thanh toán trước (MoMo), không áp dụng hình thức COD (Mục 2 & F07).",
        )

    # 2. Tính toán tiền hàng và phí thêu
    subtotal = 0
    embroidery_total = 0
    for item in payload.items:
        item_price = int(item.price)
        emb_fee = int(item.embroidery_fee) if item.is_embroidered else 0
        subtotal += item_price * item.quantity
        embroidery_total += emb_fee * item.quantity

    # 3. Tính phí vận chuyển qua ShippingProvider
    shipping_address_dict = payload.shipping_address.model_dump()
    shipping_fee = shipping_service.quote(
        address=shipping_address_dict,
        weight=0.5 * len(payload.items),
        subtotal=subtotal,
    )
    total_amount = subtotal + embroidery_total + shipping_fee - 0

    order_code = _generate_order_code()
    user_id = token_payload.get("sub") if token_payload else None
    customer_name = payload.customer_name or payload.shipping_address.recipient_name
    customer_phone = payload.customer_phone or payload.shipping_address.phone

    # 4. Trừ tồn kho ngay nếu là đơn COD
    deducted_items = []
    if payload.payment_method.upper() == "COD":
        for item in payload.items:
            # Atomic update trên MongoDB: Trừ stock chỉ khi stock >= quantity
            res = await products_col.update_one(
                {
                    "id": item.product_id,
                    "variants.sku": item.sku,
                    "variants.stock": {"$gte": item.quantity},
                },
                {"$inc": {"variants.$.stock": -item.quantity}},
            )

            if res.modified_count == 0:
                # Rollback các item đã trừ trước đó
                for roll in deducted_items:
                    await products_col.update_one(
                        {"id": roll["product_id"], "variants.sku": roll["sku"]},
                        {"$inc": {"variants.$.stock": roll["quantity"]}},
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sản phẩm '{item.product_name}' (SKU: {item.sku}) không đủ số lượng tồn kho để đặt hàng.",
                )

            deducted_items.append({
                "product_id": item.product_id,
                "sku": item.sku,
                "quantity": item.quantity,
            })

            # Ghi nhận biến động kho StockMovement (F17)
            await movements_col.insert_one({
                "id": str(uuid.uuid4()),
                "product_id": item.product_id,
                "sku": item.sku,
                "quantity_change": -item.quantity,
                "reason": f"Xuất kho đơn hàng COD: {order_code}",
                "performed_by": user_id or "customer_checkout",
                "created_at": now,
            })

    initial_status = "confirmed" if payload.payment_method.upper() == "COD" else "pending_payment"
    payment_status = "unpaid"

    # 5. Sinh mã vận đơn từ shipping provider
    shipment_info = shipping_service.create_shipment({"shipping_fee": shipping_fee})

    initial_history = [
        {
            "old_status": None,
            "new_status": initial_status,
            "changed_by": user_id or "customer",
            "timestamp": now,
            "note": "Khởi tạo đơn hàng thành công" + (" (COD - Đã trừ tồn kho)" if payload.payment_method.upper() == "COD" else " (Chờ thanh toán MoMo)"),
        }
    ]

    order_doc = {
        "id": f"ord-{uuid.uuid4().hex[:8]}",
        "order_code": order_code,
        "user_id": user_id,
        "channel": "retail",
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_email": payload.customer_email,
        "shipping_address": shipping_address_dict,
        "subtotal": subtotal,
        "shipping_fee": shipping_fee,
        "discount_amount": 0,
        "embroidery_total": embroidery_total,
        "total_amount": total_amount,
        "payment_method": payload.payment_method.upper(),
        "payment_status": payment_status,
        "status": initial_status,
        "items": [item.model_dump() for item in payload.items],
        "tracking_code": shipment_info.get("tracking_code"),
        "status_history": initial_history,
        "created_at": now,
        "updated_at": now,
    }

    await orders_col.insert_one(order_doc)

    return APIResponse(
        success=True,
        message="Đặt hàng thành công",
        data=_format_order(order_doc),
    )


@router.get("", response_model=APIResponse[List[OrderResponse]])
async def list_orders(
    token_payload: Optional[dict] = Depends(get_current_user_token),
    phone: Optional[str] = Query(None, description="Tra cứu đơn hàng của khách theo SĐT"),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F09: Danh sách đơn hàng (Khách hàng chỉ xem đơn của mình; Hỗ trợ tra cứu theo SĐT)."""
    orders_col = db["orders"]
    query = {}

    if token_payload and token_payload.get("sub"):
        user_role = token_payload.get("role", "customer")
        if user_role not in ["admin", "staff"]:
            # Khách hàng chỉ xem đơn của mình (IDOR check)
            query["$or"] = [
                {"user_id": token_payload.get("sub")},
                {"customer_phone": token_payload.get("phone", "")},
            ]
    elif phone:
        query["customer_phone"] = phone
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần đăng nhập hoặc cung cấp số điện thoại để tra cứu đơn hàng",
        )

    if status_filter and status_filter != "all":
        query["status"] = status_filter

    cursor = orders_col.find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=100)
    results = [_format_order(d) for d in docs]

    return APIResponse(
        success=True,
        message="Lấy danh sách đơn hàng thành công",
        data=results,
    )


@router.get("/{order_code}", response_model=APIResponse[OrderResponse])
async def get_order_detail(
    order_code: str,
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F09: Chi tiết đơn hàng, lịch sử trạng thái, mã vận đơn."""
    orders_col = db["orders"]
    doc = await orders_col.find_one({"order_code": order_code})
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

    # Kiểm tra IDOR: Khách hàng chỉ xem đơn của mình
    if token_payload:
        user_role = token_payload.get("role", "customer")
        user_id = token_payload.get("sub")
        if user_role not in ["admin", "staff"] and doc.get("user_id") and doc.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Không có quyền truy cập đơn hàng này")

    return APIResponse(
        success=True,
        message="Lấy chi tiết đơn hàng thành công",
        data=_format_order(doc),
    )


@router.patch("/{order_code}/status", response_model=APIResponse[OrderResponse])
async def update_order_status(
    order_code: str,
    payload: OrderStatusUpdateRequest,
    current_user: dict = Depends(require_role(["admin", "staff"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Mục 6: Chuyển trạng thái đơn hàng theo luồng hợp lệ nghiêm ngặt.
    Chuyển sai luồng bị từ chối và báo lỗi.
    """
    orders_col = db["orders"]
    products_col = db["products"]
    movements_col = db["stock_movements"]
    now = datetime.now(timezone.utc)

    order = await orders_col.find_one({"order_code": order_code})
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

    curr_status = order.get("status")
    new_status = payload.new_status

    # Kiểm tra luồng trạng thái hợp lệ
    allowed_next = VALID_TRANSITIONS.get(curr_status, [])
    if new_status not in allowed_next:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chuyển trạng thái không hợp lệ: Không thể chuyển từ '{curr_status}' sang '{new_status}'. Luồng hợp lệ tiếp theo: {allowed_next}",
        )

    # Nếu chuyển sang cancelled trước shipping -> Hoàn lại tồn kho
    if new_status == "cancelled" and curr_status in ["confirmed", "paid", "processing"]:
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
                "reason": f"Hoàn tồn kho do hủy đơn hàng: {order_code}",
                "performed_by": current_user.get("phone", "staff"),
                "created_at": now,
            })

    history_entry = {
        "old_status": curr_status,
        "new_status": new_status,
        "changed_by": current_user.get("phone", "staff"),
        "timestamp": now,
        "note": payload.note or f"Chuyển trạng thái sang {new_status}",
    }

    await orders_col.update_one(
        {"order_code": order_code},
        {
            "$set": {"status": new_status, "updated_at": now},
            "$push": {"status_history": history_entry},
        },
    )

    # Ghi nhận Audit Log F23
    from app.core.activity import record_activity
    await record_activity(
        db=db,
        actor=current_user.get("phone", current_user.get("sub", "staff")),
        actor_role=current_user.get("role", "staff"),
        action="CHANGE_ORDER_STATUS",
        target_type="order",
        target_id=order_code,
        details={
            "old_status": curr_status,
            "new_status": new_status,
            "note": payload.note,
        },
    )

    updated_order = await orders_col.find_one({"order_code": order_code})
    return APIResponse(
        success=True,
        message=f"Đã chuyển trạng thái đơn hàng sang '{new_status}' thành công",
        data=_format_order(updated_order),
    )


@router.post("/{order_code}/cancel", response_model=APIResponse[OrderResponse])
async def customer_cancel_order(
    order_code: str,
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Mục 6: Khách hàng hủy đơn trước khi vận chuyển (shipping); tự động hoàn kho."""
    orders_col = db["orders"]
    products_col = db["products"]
    movements_col = db["stock_movements"]
    now = datetime.now(timezone.utc)

    order = await orders_col.find_one({"order_code": order_code})
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")

    # Kiểm tra quyền sở hữu
    if token_payload and order.get("user_id"):
        if token_payload.get("sub") != order.get("user_id"):
            raise HTTPException(status_code=403, detail="Không có quyền hủy đơn hàng này")

    curr_status = order.get("status")
    # Cho phép hủy từ mọi trạng thái trước shipping (Mục 6)
    if curr_status in ["shipping", "delivered", "completed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể hủy đơn hàng khi đã ở trạng thái '{curr_status}' (chỉ được hủy trước khi giao hàng).",
        )

    # Hoàn trả tồn kho nếu đơn đã trừ tồn kho
    if curr_status in ["confirmed", "paid", "processing"]:
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
                "reason": f"Khách hàng hủy đơn {order_code} - Hoàn kho",
                "performed_by": order.get("user_id") or "customer",
                "created_at": now,
            })

    history_entry = {
        "old_status": curr_status,
        "new_status": "cancelled",
        "changed_by": order.get("user_id") or "customer",
        "timestamp": now,
        "note": "Khách hàng yêu cầu hủy đơn hàng trước khi vận chuyển",
    }

    await orders_col.update_one(
        {"order_code": order_code},
        {
            "$set": {"status": "cancelled", "updated_at": now},
            "$push": {"status_history": history_entry},
        },
    )

    updated_order = await orders_col.find_one({"order_code": order_code})
    return APIResponse(
        success=True,
        message="Hủy đơn hàng thành công, số lượng tồn kho đã được hoàn lại.",
        data=_format_order(updated_order),
    )


# ==============================================================================
# F17: Quản lý Tồn kho & Lịch sử biến động (Staff & Admin)
# ==============================================================================

@router.get("/inventory/movements", response_model=APIResponse[List[dict]])
async def list_stock_movements(
    sku: Optional[str] = Query(None, description="Lọc theo mã SKU"),
    current_user: dict = Depends(require_role(["admin", "staff"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F17: Xem lịch sử biến động kho (StockMovement)."""
    movements_col = db["stock_movements"]
    filter_q = {}
    if sku:
        filter_q["sku"] = sku

    cursor = movements_col.find(filter_q).sort("created_at", -1)
    docs = await cursor.to_list(length=100)
    for d in docs:
        d["_id"] = str(d["_id"])

    return APIResponse(
        success=True,
        message="Lấy lịch sử biến động kho thành công",
        data=docs,
    )


@router.post("/inventory/adjust", response_model=APIResponse[dict])
async def adjust_inventory(
    product_id: str = Query(...),
    sku: str = Query(...),
    quantity_change: int = Query(..., description="Số lượng nhập (+) hoặc xuất (-)"),
    reason: str = Query(..., description="Lý do điều chỉnh kho"),
    current_user: dict = Depends(require_role(["admin", "staff"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F17: Điều chỉnh tồn kho thủ công (Nhập kho / Kiểm kê)."""
    products_col = db["products"]
    movements_col = db["stock_movements"]
    now = datetime.now(timezone.utc)

    # Đảm bảo sau điều chỉnh tồn kho không âm
    if quantity_change < 0:
        res = await products_col.update_one(
            {
                "id": product_id,
                "variants.sku": sku,
                "variants.stock": {"$gte": abs(quantity_change)},
            },
            {"$inc": {"variants.$.stock": quantity_change}},
        )
        if res.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tồn kho không đủ để xuất kho (ràng buộc tồn kho không âm).",
            )
    else:
        await products_col.update_one(
            {"id": product_id, "variants.sku": sku},
            {"$inc": {"variants.$.stock": quantity_change}},
        )

    # Ghi log biến động kho
    await movements_col.insert_one({
        "id": str(uuid.uuid4()),
        "product_id": product_id,
        "sku": sku,
        "quantity_change": quantity_change,
        "reason": reason,
        "performed_by": current_user.get("phone", "staff"),
        "created_at": now,
    })

    # Ghi nhận Audit Log F23
    from app.core.activity import record_activity
    await record_activity(
        db=db,
        actor=current_user.get("phone", current_user.get("sub", "staff")),
        actor_role=current_user.get("role", "staff"),
        action="ADJUST_INVENTORY",
        target_type="inventory",
        target_id=sku,
        details={
            "product_id": product_id,
            "quantity_change": quantity_change,
            "reason": reason,
        },
    )

    return APIResponse(
        success=True,
        message="Điều chỉnh tồn kho thành công",
        data={"sku": sku, "quantity_change": quantity_change},
    )


@router.get("/inventory/low-stock", response_model=APIResponse[List[dict]])
async def list_low_stock_variants(
    current_user: dict = Depends(require_role(["admin", "staff"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F17: Cảnh báo tồn kho thấp theo ngưỡng của từng biến thể."""
    products_col = db["products"]
    cursor = products_col.find({"is_active": True})
    products = await cursor.to_list(length=200)

    low_stock_items = []
    for p in products:
        for v in p.get("variants", []):
            stock = v.get("stock", 0)
            threshold = v.get("low_stock_threshold", 5)
            if stock <= threshold:
                low_stock_items.append({
                    "product_id": p.get("id"),
                    "product_name": p.get("name"),
                    "sku": v.get("sku"),
                    "size": v.get("size"),
                    "color": v.get("color"),
                    "stock": stock,
                    "threshold": threshold,
                    "is_out_of_stock": stock == 0,
                })

    return APIResponse(
        success=True,
        message="Danh sách biến thể tồn kho thấp",
        data=low_stock_items,
    )
