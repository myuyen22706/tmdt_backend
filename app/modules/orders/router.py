from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timezone
from app.core.database import get_db
from app.core.responses import APIResponse
from app.modules.orders.schemas import OrderCreate, SizeExchangeRequest
from app.modules.orders.models import Order, OrderItem, SizeExchangeRequest as DBSizeExchange


router = APIRouter(prefix="/orders", tags=["Orders & Checkout"])


@router.post("")
async def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    """Đặt hàng (Hỗ trợ Guest checkout và lưu trực tiếp vào cơ sở dữ liệu)."""
    code = f"VO-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    subtotal = sum((item.price + item.embroidery_fee) * item.quantity for item in order_data.items)
    shipping_fee = 0 if subtotal >= 500000 else 30000
    total = subtotal + shipping_fee

    full_address = (
        f"{order_data.shipping_address.street_address}, {order_data.shipping_address.ward}, "
        f"{order_data.shipping_address.district}, {order_data.shipping_address.city_province}"
    )

    vietqr_url = None
    if order_data.payment_method == "VietQR":
        vietqr_url = f"https://img.vietqr.io/image/970422-0987654321-compact2.png?amount={int(total)}&addInfo={code}"

    # Tạo đơn hàng trong DB
    new_order = Order(
        order_code=code,
        customer_name=order_data.shipping_address.full_name,
        customer_phone=order_data.shipping_address.phone,
        customer_email=order_data.customer_email,
        shipping_address=full_address,
        payment_method=order_data.payment_method,
        payment_status="PAID" if order_data.payment_method == "VietQR" else "UNPAID",
        order_status="PENDING",
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        discount_amount=0,
        total_amount=total,
        tracking_code=f"GHTK{uuid.uuid4().hex[:8].upper()}",
        shipping_carrier="GHTK",
        vietqr_url=vietqr_url,
        notes=order_data.note,
    )
    db.add(new_order)
    db.flush()

    # Thêm các item của đơn
    for item in order_data.items:
        db_item = OrderItem(
            order_id=new_order.id,
            product_id=item.product_id,
            product_name=item.product_name,
            size=item.size,
            quantity=item.quantity,
            unit_price=item.price,
            is_embroidered=item.is_embroidered,
            embroidery_fee=item.embroidery_fee,
            embroidered_text=item.embroidered_text,
        )
        db.add(db_item)

    db.commit()
    db.refresh(new_order)

    return APIResponse(
        success=True,
        message="Đặt hàng thành công",
        data={
            "id": new_order.id,
            "order_code": new_order.order_code,
            "status": new_order.order_status,
            "customer_name": new_order.customer_name,
            "total_amount": float(new_order.total_amount),
            "tracking_code": new_order.tracking_code,
            "vietqr_url": new_order.vietqr_url,
        },
    )


@router.get("")
async def list_orders(db: Session = Depends(get_db)):
    """Lấy danh sách đơn hàng từ database."""
    orders = db.query(Order).order_by(Order.created_at.desc()).all()
    result = []
    for ord in orders:
        result.append({
            "id": ord.id,
            "order_code": ord.order_code,
            "status": ord.order_status,
            "customer_name": ord.customer_name,
            "phone": ord.customer_phone,
            "shipping_address_full": ord.shipping_address,
            "payment_method": ord.payment_method,
            "payment_status": ord.payment_status,
            "subtotal": float(ord.subtotal),
            "shipping_fee": float(ord.shipping_fee),
            "total_amount": float(ord.total_amount),
            "tracking_code": ord.tracking_code,
            "vietqr_url": ord.vietqr_url,
            "created_at": ord.created_at,
        })

    return APIResponse(
        success=True,
        message="Lấy danh sách đơn hàng thành công",
        data=result,
    )


@router.get("/{id_or_code}")
async def get_order_detail(id_or_code: str, db: Session = Depends(get_db)):
    """Tra cứu trạng thái đơn hàng & mã vận đơn tracking."""
    ord = db.query(Order).filter(
        (Order.id == id_or_code) | (Order.order_code == id_or_code)
    ).first()

    if not ord:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn hàng")

    data = {
        "id": ord.id,
        "order_code": ord.order_code,
        "status": ord.order_status,
        "customer_name": ord.customer_name,
        "phone": ord.customer_phone,
        "shipping_address_full": ord.shipping_address,
        "payment_method": ord.payment_method,
        "payment_status": ord.payment_status,
        "subtotal": float(ord.subtotal),
        "shipping_fee": float(ord.shipping_fee),
        "total_amount": float(ord.total_amount),
        "tracking_code": ord.tracking_code,
        "shipping_carrier": ord.shipping_carrier,
        "vietqr_url": ord.vietqr_url,
        "items": [
            {
                "id": it.id,
                "product_name": it.product_name,
                "size": it.size,
                "quantity": it.quantity,
                "unit_price": float(it.unit_price),
                "is_embroidered": it.is_embroidered,
                "embroidered_text": it.embroidered_text,
            }
            for it in ord.items
        ],
        "created_at": ord.created_at,
    }

    return APIResponse(
        success=True,
        message="Lấy thông tin đơn hàng thành công",
        data=data,
    )


@router.post("/exchange-size")
async def request_size_exchange(req: SizeExchangeRequest, db: Session = Depends(get_db)):
    """Gửi yêu cầu đổi size miễn phí (Cam kết đổi size 1 lần)."""
    exchange = DBSizeExchange(
        order_id=req.order_id,
        product_id=req.product_id,
        current_size=req.current_size,
        desired_size=req.desired_size,
        reason=req.reason,
        customer_note=req.customer_note,
        status="PENDING",
    )
    db.add(exchange)
    db.commit()
    db.refresh(exchange)

    return APIResponse(
        success=True,
        message="Đã tiếp nhận yêu cầu đổi size. CSKH sẽ liên hệ xác nhận trong vòng 24h.",
        data={
            "id": exchange.id,
            "order_id": exchange.order_id,
            "desired_size": exchange.desired_size,
            "status": exchange.status,
            "policy": "Miễn phí đổi size 1 lần trong 7 ngày",
        },
    )
