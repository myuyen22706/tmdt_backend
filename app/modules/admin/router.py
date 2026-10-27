import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.activity import record_activity
from app.core.database import get_db
from app.core.dependencies import get_current_user_token, require_role
from app.core.responses import APIResponse
from app.modules.admin.schemas import (
    ActivityLogEntry,
    PackingSlipResponse,
    ReturnRequestCreate,
    ReturnRequestResponse,
    ReturnReviewAction,
    RevenueReportResponse,
)

router = APIRouter(prefix="/admin", tags=["Admin Back-office, Returns & Reports (F10, F18, F20, F22, F23)"])


def _format_return_request(doc: dict) -> ReturnRequestResponse:
    return ReturnRequestResponse(
        id=doc.get("id", str(doc.get("_id", ""))),
        order_code=doc.get("order_code", ""),
        user_id=doc.get("user_id"),
        product_id=doc.get("product_id", ""),
        product_name=doc.get("product_name", ""),
        sku=doc.get("sku", ""),
        current_size=doc.get("current_size", ""),
        desired_size=doc.get("desired_size", ""),
        reason=doc.get("reason", ""),
        image_url=doc.get("image_url"),
        status=doc.get("status", "pending"),
        review_note=doc.get("review_note"),
        exchange_order_code=doc.get("exchange_order_code"),
        created_at=doc.get("created_at", datetime.now(timezone.utc)),
        updated_at=doc.get("updated_at", datetime.now(timezone.utc)),
    )


# ==============================================================================
# KPI Dashboard tổng quan (Staff & Admin)
# ==============================================================================

@router.get("/dashboard/kpi")
async def get_dashboard_kpis(
    current_user: dict = Depends(require_role(["admin", "staff"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Báo cáo KPI tổng quan từ MongoDB Atlas: Doanh thu, số đơn, tỷ lệ đổi size, đơn võ đường."""
    orders_col = db["orders"]
    returns_col = db["return_requests"]
    campaigns_col = db["club_campaigns"]
    products_col = db["products"]

    # Tổng đơn và doanh thu (tính từ các đơn đã xác nhận / thanh toán)
    all_orders = await orders_col.find({}).to_list(length=1000)
    total_orders = len(all_orders)
    total_revenue = sum(
        int(o.get("total_amount", 0))
        for o in all_orders
        if o.get("status") in ["paid", "processing", "shipping", "delivered", "completed"]
    )
    pending_orders = sum(1 for o in all_orders if o.get("status") in ["pending_payment", "confirmed"])

    # Tỷ lệ đổi size (F10 / F20)
    total_returns = await returns_col.count_documents({})
    exchange_rate = f"{(total_returns / total_orders * 100):.1f}%" if total_orders > 0 else "0.0%"

    # Số đợt gom đơn võ đường đang mở
    active_campaigns = await campaigns_col.count_documents({"status": "open"})

    # Cảnh báo tồn kho thấp (dưới ngưỡng)
    all_prods = await products_col.find({"is_active": True}).to_list(length=200)
    low_stock_alerts = []
    for p in all_prods:
        for v in p.get("variants", []):
            stock = v.get("stock", 0)
            threshold = v.get("low_stock_threshold", 5)
            if stock <= threshold:
                low_stock_alerts.append({
                    "product_name": p.get("name", "Võ phục"),
                    "sku": v.get("sku"),
                    "size": v.get("size"),
                    "remaining": stock,
                    "threshold": threshold,
                })

    return APIResponse(
        success=True,
        message="Lấy dữ liệu KPI thành công",
        data={
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "total_returns": total_returns,
            "size_exchange_rate": exchange_rate,
            "active_dojo_campaigns": active_campaigns,
            "low_stock_alerts": low_stock_alerts[:10],
        },
    )


# ==============================================================================
# F10: Yêu cầu Đổi size từ Khách hàng
# ==============================================================================

@router.post("/returns/request", response_model=APIResponse[ReturnRequestResponse])
async def create_return_request(
    payload: ReturnRequestCreate,
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F10: Khách hàng gửi yêu cầu đổi size.
    Ràng buộc nghiệp vụ nghiêm ngặt:
    - 1. Đơn hàng phải tồn tại và ở trạng thái 'delivered' hoặc 'completed'.
    - 2. Hàng thêu tên riêng (is_embroidered=True) TUYỆT ĐỐI KHÔNG ĐƯỢC ĐỔI TRẢ.
    - 3. Chỉ được đổi trong vòng 7 ngày kể từ lúc nhận hàng ('delivered').
    """
    orders_col = db["orders"]
    returns_col = db["return_requests"]
    now = datetime.now(timezone.utc)

    # 1. Tìm đơn hàng
    order = await orders_col.find_one({"order_code": payload.order_code})
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy đơn hàng có mã '{payload.order_code}'",
        )

    # Nếu người dùng đã đăng nhập, kiểm tra xem có đúng đơn của họ không (hoặc vãng lai khớp số điện thoại)
    if token_payload and order.get("user_id"):
        if token_payload.get("sub") != order.get("user_id") and token_payload.get("role") not in ["admin", "staff"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền gửi yêu cầu đổi size cho đơn hàng này",
            )

    # Kiểm tra trạng thái đơn hàng (phải là delivered hoặc completed)
    curr_status = order.get("status")
    if curr_status not in ["delivered", "completed", "return_requested"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ được yêu cầu đổi size sau khi đã nhận hàng thành công (trạng thái 'delivered' hoặc 'completed'). Trạng thái hiện tại: '{curr_status}'.",
        )

    # 2. Tìm sản phẩm trong đơn hàng
    target_item = None
    for item in order.get("items", []):
        if item.get("sku") == payload.sku or (item.get("product_id") == payload.product_id and item.get("size") == payload.sku):
            target_item = item
            break

    if not target_item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sản phẩm với SKU '{payload.sku}' không nằm trong danh sách mua của đơn hàng này",
        )

    # Kiểm tra ràng buộc F10 & Mục 2: Hàng thêu không được đổi trả
    if target_item.get("is_embroidered", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sản phẩm đã thêu tên riêng theo yêu cầu không được áp dụng chính sách đổi trả (Mục 2 & F10).",
        )

    # 3. Kiểm tra thời hạn 7 ngày
    # Tìm mốc thời gian giao hàng thành công từ status_history hoặc order.updated_at
    delivered_time = None
    for hist in order.get("status_history", []):
        if hist.get("new_status") == "delivered":
            delivered_time = hist.get("timestamp")
            break

    if not delivered_time:
        delivered_time = order.get("updated_at") or order.get("created_at") or now

    # Đảm bảo delivered_time có timezone UTC
    if delivered_time.tzinfo is None:
        delivered_time = delivered_time.replace(tzinfo=timezone.utc)

    days_passed = (now - delivered_time).total_seconds() / 86400
    if days_passed > 7.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Đã quá thời hạn 7 ngày đổi size kể từ khi nhận hàng ({int(days_passed)} ngày đã trôi qua). Chính sách áp dụng trong 7 ngày.",
        )

    # Tạo bản ghi yêu cầu đổi size
    request_id = f"ret-{uuid.uuid4().hex[:8]}"
    return_doc = {
        "id": request_id,
        "order_code": order["order_code"],
        "user_id": order.get("user_id"),
        "customer_phone": order.get("customer_phone"),
        "customer_name": order.get("customer_name"),
        "product_id": target_item.get("product_id"),
        "product_name": target_item.get("product_name", "Võ phục"),
        "sku": target_item.get("sku"),
        "current_size": target_item.get("size", ""),
        "desired_size": payload.desired_size,
        "reason": payload.reason,
        "image_url": payload.image_url,
        "status": "pending",
        "review_note": None,
        "exchange_order_code": None,
        "created_at": now,
        "updated_at": now,
    }
    await returns_col.insert_one(return_doc)

    # Cập nhật đơn hàng sang trạng thái return_requested nếu đang ở delivered
    if curr_status == "delivered":
        history_entry = {
            "old_status": curr_status,
            "new_status": "return_requested",
            "changed_by": order.get("user_id") or "customer",
            "timestamp": now,
            "note": f"Khách hàng yêu cầu đổi size sang {payload.desired_size} (Mã yêu cầu: {request_id})",
        }
        await orders_col.update_one(
            {"order_code": order["order_code"]},
            {
                "$set": {"status": "return_requested", "updated_at": now},
                "$push": {"status_history": history_entry},
            },
        )

    return APIResponse(
        success=True,
        message="Gửi yêu cầu đổi size thành công. Bộ phận CSKH sẽ duyệt và gửi hướng dẫn gửi lại hàng.",
        data=_format_return_request(return_doc),
    )


# ==============================================================================
# F20: Quản lý Đổi trả cho Staff & Admin
# ==============================================================================

@router.get("/returns", response_model=APIResponse[List[ReturnRequestResponse]])
async def list_return_requests(
    status_filter: Optional[str] = Query(None, alias="status", description="Lọc theo trạng thái"),
    order_code: Optional[str] = Query(None, description="Lọc theo mã đơn"),
    current_user: dict = Depends(require_role(["admin", "staff"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F20: Xem danh sách yêu cầu đổi trả (Staff & Admin)."""
    returns_col = db["return_requests"]
    query = {}
    if status_filter:
        query["status"] = status_filter
    if order_code:
        query["order_code"] = order_code

    cursor = returns_col.find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=200)
    items = [_format_return_request(d) for d in docs]

    return APIResponse(
        success=True,
        message="Lấy danh sách yêu cầu đổi trả thành công",
        data=items,
    )


@router.get("/returns/{return_id}", response_model=APIResponse[ReturnRequestResponse])
async def get_return_detail(
    return_id: str,
    current_user: dict = Depends(require_role(["admin", "staff"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F20: Xem chi tiết yêu cầu đổi trả."""
    doc = await db["return_requests"].find_one({"id": return_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu đổi trả")
    return APIResponse(
        success=True,
        message="Lấy thông tin yêu cầu đổi trả thành công",
        data=_format_return_request(doc),
    )


@router.patch("/returns/{return_id}/review", response_model=APIResponse[ReturnRequestResponse])
async def review_return_request(
    return_id: str,
    payload: ReturnReviewAction,
    current_user: dict = Depends(require_role(["admin", "staff"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F20: Duyệt (approve) hoặc Từ chối (reject) yêu cầu đổi size.
    - Khi duyệt: Sinh mã đơn đổi mới (EX-YYYYMMDD-XXXX).
    - Ghi nhận Audit Log F23.
    """
    returns_col = db["return_requests"]
    now = datetime.now(timezone.utc)

    req_doc = await returns_col.find_one({"id": return_id})
    if not req_doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu đổi trả")

    action = payload.action.lower()
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Hành động chỉ có thể là 'approve' hoặc 'reject'")

    update_fields: Dict[str, Any] = {
        "updated_at": now,
        "review_note": payload.note,
    }

    if action == "approve":
        update_fields["status"] = "approved"
        # Sinh mã đơn đổi hàng
        date_str = datetime.now().strftime("%Y%m%d")
        exchange_code = f"EX-{date_str}-{uuid.uuid4().hex[:4].upper()}"
        update_fields["exchange_order_code"] = exchange_code
    else:
        update_fields["status"] = "rejected"

    await returns_col.update_one({"id": return_id}, {"$set": update_fields})
    updated_doc = await returns_col.find_one({"id": return_id})

    # Ghi nhận Audit Log F23
    await record_activity(
        db=db,
        actor=current_user.get("phone", current_user.get("sub", "staff")),
        actor_role=current_user.get("role", "staff"),
        action="APPROVE_RETURN" if action == "approve" else "REJECT_RETURN",
        target_type="return",
        target_id=return_id,
        details={
            "order_code": req_doc.get("order_code"),
            "action": action,
            "note": payload.note,
            "exchange_order_code": update_fields.get("exchange_order_code"),
        },
    )

    return APIResponse(
        success=True,
        message=f"Đã xử lý yêu cầu đổi trả: {action.upper()}",
        data=_format_return_request(updated_doc),
    )


@router.post("/returns/{return_id}/receive", response_model=APIResponse[dict])
async def receive_returned_item(
    return_id: str,
    current_user: dict = Depends(require_role(["admin", "staff"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F20: Xác nhận kho đã nhận lại hàng trả.
    - Chuyển trạng thái yêu cầu sang 'completed'.
    - Tự động cộng lại 1 đơn vị tồn kho cho size cũ (SKU cũ).
    - Ghi nhận biến động kho StockMovement.
    - Cập nhật trạng thái đơn hàng sang 'returned'.
    - Ghi nhận Audit Log F23.
    """
    returns_col = db["return_requests"]
    products_col = db["products"]
    orders_col = db["orders"]
    movements_col = db["stock_movements"]
    now = datetime.now(timezone.utc)

    req_doc = await returns_col.find_one({"id": return_id})
    if not req_doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu đổi trả")

    if req_doc.get("status") != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chỉ có thể xác nhận nhận hàng cho yêu cầu đã được duyệt ('approved'). Trạng thái hiện tại: '{req_doc.get('status')}'",
        )

    # 1. Hoàn lại 1 sản phẩm vào tồn kho của SKU size cũ
    product_id = req_doc.get("product_id")
    sku = req_doc.get("sku")

    await products_col.update_one(
        {"id": product_id, "variants.sku": sku},
        {"$inc": {"variants.$.stock": 1}},
    )

    # Ghi log biến động kho
    await movements_col.insert_one({
        "id": str(uuid.uuid4()),
        "product_id": product_id,
        "sku": sku,
        "quantity_change": 1,
        "reason": f"Nhập hoàn kho hàng đổi size từ yêu cầu {return_id} (Đơn {req_doc.get('order_code')})",
        "performed_by": current_user.get("phone", "staff"),
        "created_at": now,
    })

    # 2. Cập nhật trạng thái yêu cầu sang completed
    await returns_col.update_one(
        {"id": return_id},
        {"$set": {"status": "completed", "received_at": now, "updated_at": now}},
    )

    # 3. Cập nhật trạng thái đơn hàng sang returned nếu đang ở return_requested
    order_code = req_doc.get("order_code")
    await orders_col.update_one(
        {"order_code": order_code, "status": "return_requested"},
        {
            "$set": {"status": "returned", "updated_at": now},
            "$push": {
                "status_history": {
                    "old_status": "return_requested",
                    "new_status": "returned",
                    "changed_by": current_user.get("phone", "staff"),
                    "timestamp": now,
                    "note": f"Đã nhận hàng đổi size về kho theo yêu cầu {return_id}",
                }
            },
        },
    )

    # 4. Ghi nhận Audit Log F23
    await record_activity(
        db=db,
        actor=current_user.get("phone", current_user.get("sub", "staff")),
        actor_role=current_user.get("role", "staff"),
        action="RECEIVE_RETURN",
        target_type="return",
        target_id=return_id,
        details={
            "order_code": order_code,
            "sku": sku,
            "quantity_restocked": 1,
        },
    )

    return APIResponse(
        success=True,
        message="Đã xác nhận nhận hàng trả về kho và tự động cộng hoàn tồn kho thành công.",
        data={
            "return_id": return_id,
            "order_code": order_code,
            "sku_restocked": sku,
            "status": "completed",
        },
    )


# ==============================================================================
# F18: In phiếu đóng gói (Packing Slip) (Staff & Admin)
# ==============================================================================

@router.get("/orders/{order_code}/packing-slip", response_model=APIResponse[PackingSlipResponse])
async def get_packing_slip(
    order_code: str,
    current_user: dict = Depends(require_role(["admin", "staff"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F18: Lấy dữ liệu in phiếu đóng gói (Packing Slip) chuẩn bị giao cho bên vận chuyển."""
    orders_col = db["orders"]
    order = await orders_col.find_one({"order_code": order_code})
    if not order:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn hàng {order_code}")

    addr = order.get("shipping_address", {})
    if isinstance(addr, dict):
        parts = [addr.get("street_address"), addr.get("ward"), addr.get("district"), addr.get("city_province")]
        addr_str = ", ".join(str(part).strip() for part in parts if part and str(part).strip())
    else:
        addr_str = str(addr)

    items = order.get("items", [])
    total_qty = sum(int(it.get("quantity", 1)) for it in items)
    has_embroidery = any(it.get("is_embroidered") for it in items)

    notes = []
    if has_embroidery:
        notes.append("LƯU Ý: ĐƠN CÓ HÀNG THÊU TÊN RIÊNG - KIỂM TRA CHÍNH XÁC TỪNG CHỮ VÕ PHỤC TRƯỚC KHI ĐÓNG GÓI")
    if order.get("channel") == "club":
        notes.append("ĐƠN GOM VÕ ĐƯỜNG - ĐÓNG GÓI CHUNG THEO LÔ")

    tracking = order.get("tracking_code") or f"VN-MOCK-{order_code.split('-')[-1]}"

    slip_data = PackingSlipResponse(
        order_code=order_code,
        created_at=order.get("created_at", datetime.now(timezone.utc)),
        customer_name=order.get("customer_name", ""),
        customer_phone=order.get("customer_phone", ""),
        shipping_address=addr_str,
        tracking_code=tracking,
        carrier="MockShipping",
        items=items,
        total_quantity=total_qty,
        notes="; ".join(notes) if notes else None,
    )

    return APIResponse(
        success=True,
        message="Lấy dữ liệu phiếu đóng gói thành công",
        data=slip_data,
    )


# ==============================================================================
# F22: Báo cáo Doanh thu & Thống kê Kinh doanh (ADMIN ONLY - Chặn Staff 403)
# ==============================================================================

@router.get("/reports/revenue", response_model=APIResponse[RevenueReportResponse])
async def get_revenue_report(
    current_user: dict = Depends(require_role(["admin"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F22: Báo cáo doanh thu chi tiết (Chỉ dành cho Admin, Staff truy cập bị chặn 403).
    - Doanh thu theo kênh: Bán lẻ vs Gom đơn Võ đường.
    - Doanh thu theo ngày, theo tháng.
    - Top sản phẩm bán chạy nhất.
    - Tỷ lệ đổi trả.
    """
    orders_col = db["orders"]
    returns_col = db["return_requests"]
    products_col = db["products"]

    all_orders = await orders_col.find({}).to_list(length=2000)
    total_orders = len(all_orders)

    # Lọc đơn có doanh thu thực tế
    paid_orders = [
        o for o in all_orders
        if o.get("status") in ["paid", "processing", "shipping", "delivered", "completed"]
    ]

    total_rev = sum(int(o.get("total_amount", 0)) for o in paid_orders)
    retail_rev = sum(int(o.get("total_amount", 0)) for o in paid_orders if o.get("channel") != "club")
    club_rev = sum(int(o.get("total_amount", 0)) for o in paid_orders if o.get("channel") == "club")

    total_returns = await returns_col.count_documents({})
    return_rate = f"{(total_returns / total_orders * 100):.1f}%" if total_orders > 0 else "0.0%"

    # Nhóm theo ngày và theo tháng
    daily_rev: Dict[str, Dict[str, int]] = {}
    monthly_rev: Dict[str, Dict[str, int]] = {}
    product_sales: Dict[str, Dict[str, Any]] = {}

    for o in paid_orders:
        created = o.get("created_at") or datetime.now(timezone.utc)
        day_str = created.strftime("%Y-%m-%d")
        month_str = created.strftime("%Y-%m")
        amt = int(o.get("total_amount", 0))

        # Ngày
        if day_str not in daily_rev:
            daily_rev[day_str] = {"revenue": 0, "orders_count": 0}
        daily_rev[day_str]["revenue"] += amt
        daily_rev[day_str]["orders_count"] += 1

        # Tháng
        if month_str not in monthly_rev:
            monthly_rev[month_str] = {"revenue": 0, "orders_count": 0}
        monthly_rev[month_str]["revenue"] += amt
        monthly_rev[month_str]["orders_count"] += 1

        # Top sản phẩm
        for it in o.get("items", []):
            p_id = it.get("product_id") or it.get("sku")
            p_name = it.get("product_name", "Võ phục")
            qty = int(it.get("quantity", 1))
            line_total = int(it.get("price", 0)) * qty
            if p_id not in product_sales:
                product_sales[p_id] = {
                    "product_id": p_id,
                    "product_name": p_name,
                    "quantity_sold": 0,
                    "revenue": 0,
                }
            product_sales[p_id]["quantity_sold"] += qty
            product_sales[p_id]["revenue"] += line_total

    # Format lists
    revenue_by_day = [
        {"date": k, "revenue": v["revenue"], "orders_count": v["orders_count"]}
        for k, v in sorted(daily_rev.items())
    ]
    revenue_by_month = [
        {"month": k, "revenue": v["revenue"], "orders_count": v["orders_count"]}
        for k, v in sorted(monthly_rev.items())
    ]
    top_products = sorted(
        product_sales.values(),
        key=lambda x: x["revenue"],
        reverse=True,
    )[:5]

    # Số lượng cảnh báo tồn kho thấp
    all_prods = await products_col.find({"is_active": True}).to_list(length=200)
    low_stock_count = 0
    for p in all_prods:
        for v in p.get("variants", []):
            if v.get("stock", 0) <= v.get("low_stock_threshold", 5):
                low_stock_count += 1

    report = RevenueReportResponse(
        total_revenue=total_rev,
        retail_revenue=retail_rev,
        club_revenue=club_rev,
        total_orders=total_orders,
        return_rate=return_rate,
        revenue_by_day=revenue_by_day,
        revenue_by_month=revenue_by_month,
        top_selling_products=top_products,
        low_stock_count=low_stock_count,
    )

    return APIResponse(
        success=True,
        message="Lấy báo cáo doanh thu thành công",
        data=report,
    )


@router.get("/reports/export-csv")
async def export_revenue_csv(
    current_user: dict = Depends(require_role(["admin"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F22: Xuất báo cáo đơn hàng & doanh thu ra file CSV chuẩn UTF-8 BOM.
    (Chỉ dành cho Admin, Staff truy cập bị chặn 403).
    """
    return await _generate_revenue_csv(db)


@router.get("/revenue-report/csv", include_in_schema=False)
async def export_revenue_csv_public_link(
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Hỗ trợ xuất CSV từ liên kết trực tiếp trên trang Admin UI (bắt buộc đăng nhập Admin)."""
    if not token_payload or token_payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Quản trị viên (Admin) mới có quyền xuất báo cáo doanh thu.",
        )
    return await _generate_revenue_csv(db)


async def _generate_revenue_csv(db: AsyncIOMotorDatabase) -> Response:
    orders_col = db["orders"]
    cursor = orders_col.find({}).sort("created_at", -1)
    orders = await cursor.to_list(length=2000)

    # Sử dụng UTF-8 BOM để Excel hiển thị đúng tiếng Việt có dấu
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Header
    writer.writerow([
        "Mã đơn hàng",
        "Kênh bán",
        "Khách hàng",
        "Số điện thoại",
        "Phương thức thanh toán",
        "Trạng thái thanh toán",
        "Trạng thái đơn hàng",
        "Tổng tiền (VND)",
        "Ngày tạo đơn",
    ])

    for o in orders:
        created = o.get("created_at")
        date_str = created.strftime("%Y-%m-%d %H:%M:%S") if created else ""
        writer.writerow([
            o.get("order_code", ""),
            o.get("channel", "retail"),
            o.get("customer_name", ""),
            o.get("customer_phone", ""),
            o.get("payment_method", ""),
            o.get("payment_status", ""),
            o.get("status", ""),
            o.get("total_amount", 0),
            date_str,
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data.encode("utf-8"),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=bao_cao_doanh_thu_dai_trang.csv"
        },
    )


# ==============================================================================
# F23: Phân quyền RBAC, Quản lý Người dùng & Audit Logging (ADMIN ONLY)
# ==============================================================================

@router.get("/activity-logs", response_model=APIResponse[List[ActivityLogEntry]])
async def list_activity_logs(
    action: Optional[str] = Query(None, description="Lọc theo hành động"),
    target_type: Optional[str] = Query(None, description="Lọc theo loại đối tượng"),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_role(["admin"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F23: Xem danh sách nhật ký hoạt động hệ thống (Chỉ Admin, Staff 403)."""
    logs_col = db["activity_logs"]
    query = {}
    if action:
        query["action"] = action
    if target_type:
        query["target_type"] = target_type

    cursor = logs_col.find(query).sort("timestamp", -1).limit(limit)
    docs = await cursor.to_list(length=limit)

    results = []
    for d in docs:
        results.append(
            ActivityLogEntry(
                id=d.get("id", str(d.get("_id", ""))),
                actor=d.get("actor", ""),
                actor_role=d.get("actor_role", "admin"),
                action=d.get("action", ""),
                target_type=d.get("target_type", ""),
                target_id=d.get("target_id"),
                details=d.get("details"),
                timestamp=d.get("timestamp", datetime.now(timezone.utc)),
            )
        )

    return APIResponse(
        success=True,
        message="Lấy danh sách nhật ký hoạt động thành công",
        data=results,
    )


@router.get("/users", response_model=APIResponse[List[dict]])
async def list_all_users(
    role: Optional[str] = Query(None, description="Lọc theo vai trò"),
    current_user: dict = Depends(require_role(["admin"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F23: Quản lý danh sách người dùng trong hệ thống (Chỉ Admin)."""
    users_col = db["users"]
    query = {}
    if role:
        query["role"] = role

    cursor = users_col.find(query, {"hashed_password": 0}).sort("created_at", -1)
    docs = await cursor.to_list(length=100)
    for d in docs:
        d["_id"] = str(d["_id"])

    return APIResponse(
        success=True,
        message="Lấy danh sách tài khoản thành công",
        data=docs,
    )


@router.patch("/users/{user_id}/role", response_model=APIResponse[dict])
async def update_user_role(
    user_id: str,
    new_role: str = Query(..., pattern="^(admin|staff|dojo_coach|customer)$"),
    current_user: dict = Depends(require_role(["admin"])),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F23: Phân quyền vai trò người dùng (Chỉ Admin)."""
    users_col = db["users"]
    user = await users_col.find_one({"id": user_id})
    if not user:
        # Thử tìm theo phone
        user = await users_col.find_one({"phone": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    old_role = user.get("role", "customer")
    await users_col.update_one(
        {"_id": user["_id"]},
        {"$set": {"role": new_role, "updated_at": datetime.now(timezone.utc)}},
    )

    # Ghi nhận Audit Log F23
    await record_activity(
        db=db,
        actor=current_user.get("phone", current_user.get("sub", "admin")),
        actor_role=current_user.get("role", "admin"),
        action="CHANGE_USER_ROLE",
        target_type="auth",
        target_id=user["id"],
        details={"old_role": old_role, "new_role": new_role, "phone": user.get("phone")},
    )

    return APIResponse(
        success=True,
        message=f"Đã cập nhật vai trò người dùng thành '{new_role}'",
        data={"user_id": user["id"], "old_role": old_role, "new_role": new_role},
    )
