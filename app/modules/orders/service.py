from datetime import datetime, timezone
from typing import List, Optional
import uuid
from app.modules.orders.schemas import OrderCreate, SizeExchangeRequest

MOCK_ORDERS: List[dict] = [
    {
        "id": "ord-demo-001",
        "order_code": "VO-20261012-001",
        "status": "CONFIRMED",
        "customer_name": "Nguyễn Văn Tuấn",
        "phone": "0987654321",
        "shipping_address_full": "123 Đường Võ Văn Tần, Phường Võ Thị Sáu, Quận 3, TP.HCM",
        "payment_method": "VietQR",
        "payment_status": "PAID",
        "items": [
            {
                "product_id": "prod-vovinam-standard",
                "product_name": "Võ Phục Vovinam Tiêu Chuẩn Việt Võ Đạo",
                "price": 240000,
                "size": "Size 4 (M)",
                "quantity": 1,
                "thumbnail": "https://placehold.co/400x400?text=Vovinam",
                "is_embroidered": True,
                "embroidered_text": "Văn Tuấn",
                "embroidery_fee": 20000,
            }
        ],
        "subtotal": 260000,
        "shipping_fee": 30000,
        "discount_amount": 0,
        "total_amount": 290000,
        "tracking_code": "GHTK88273919",
        "shipping_carrier": "GHTK",
        "vietqr_url": "https://img.vietqr.io/image/970422-0987654321-compact2.png?amount=290000&addInfo=VO-001",
        "created_at": datetime.now(timezone.utc),
    }
]

MOCK_EXCHANGES: List[dict] = []


class OrderService:
    @classmethod
    def list_orders(cls) -> List[dict]:
        return MOCK_ORDERS

    @classmethod
    def get_by_id_or_code(cls, id_or_code: str) -> Optional[dict]:
        for ord in MOCK_ORDERS:
            if ord["id"] == id_or_code or ord["order_code"] == id_or_code:
                return ord
        return None

    @classmethod
    def create_order(cls, req: OrderCreate) -> dict:
        code = f"VO-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        subtotal = sum((item.price + item.embroidery_fee) * item.quantity for item in req.items)
        shipping_fee = 0 if subtotal >= 500000 else 30000
        total = subtotal + shipping_fee

        full_address = (
            f"{req.shipping_address.street_address}, {req.shipping_address.ward}, "
            f"{req.shipping_address.district}, {req.shipping_address.city_province}"
        )

        # Generate mock VietQR payment link if method is VietQR
        vietqr_url = None
        if req.payment_method == "VietQR":
            vietqr_url = f"https://img.vietqr.io/image/970422-0987654321-compact2.png?amount={int(total)}&addInfo={code}"

        new_order = {
            "id": f"ord-{uuid.uuid4().hex[:8]}",
            "order_code": code,
            "status": "PENDING",
            "customer_name": req.shipping_address.full_name,
            "phone": req.shipping_address.phone,
            "shipping_address_full": full_address,
            "payment_method": req.payment_method,
            "payment_status": "PAID" if req.payment_method == "VietQR" else "UNPAID",
            "items": [item.model_dump() for item in req.items],
            "subtotal": subtotal,
            "shipping_fee": shipping_fee,
            "discount_amount": 0,
            "total_amount": total,
            "tracking_code": f"GHTK{uuid.uuid4().hex[:8].upper()}",
            "shipping_carrier": "GHTK",
            "vietqr_url": vietqr_url,
            "created_at": datetime.now(timezone.utc),
        }
        MOCK_ORDERS.append(new_order)
        return new_order

    @classmethod
    def create_size_exchange(cls, req: SizeExchangeRequest) -> dict:
        exchange = {
            "id": f"ex-{uuid.uuid4().hex[:8]}",
            "order_id": req.order_id,
            "product_id": req.product_id,
            "current_size": req.current_size,
            "desired_size": req.desired_size,
            "reason": req.reason,
            "customer_note": req.customer_note,
            "status": "REQUESTED",
            "policy": "Miễn phí đổi size 1 lần trong 7 ngày",
            "created_at": datetime.now(timezone.utc),
        }
        MOCK_EXCHANGES.append(exchange)
        return exchange
