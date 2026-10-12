from typing import List
from fastapi import APIRouter, HTTPException, status
from app.core.responses import APIResponse
from app.modules.orders.schemas import (
    OrderCreate,
    OrderResponse,
    SizeExchangeRequest,
)
from app.modules.orders.service import OrderService

router = APIRouter(prefix="/orders", tags=["Orders & Checkout"])


@router.post("", response_model=APIResponse[OrderResponse])
async def create_order(order_data: OrderCreate):
    """Đặt hàng (Hỗ trợ Guest checkout và tài khoản thành viên)."""
    order = OrderService.create_order(order_data)
    return APIResponse(
        success=True,
        message="Đặt hàng thành công",
        data=order,
    )


@router.get("", response_model=APIResponse[List[OrderResponse]])
async def list_orders():
    """Lấy danh sách đơn hàng."""
    return APIResponse(
        success=True,
        message="Lấy danh sách đơn hàng thành công",
        data=OrderService.list_orders(),
    )


@router.get("/{id_or_code}", response_model=APIResponse[OrderResponse])
async def get_order_detail(id_or_code: str):
    """Tra cứu trạng thái đơn hàng & mã vận đơn tracking."""
    order = OrderService.get_by_id_or_code(id_or_code)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đơn hàng",
        )
    return APIResponse(
        success=True,
        message="Lấy thông tin đơn hàng thành công",
        data=order,
    )


@router.post("/exchange-size", response_model=APIResponse[dict])
async def request_size_exchange(req: SizeExchangeRequest):
    """Gửi yêu cầu đổi size miễn phí (Cam kết đổi size 1 lần)."""
    exchange = OrderService.create_size_exchange(req)
    return APIResponse(
        success=True,
        message="Đã tiếp nhận yêu cầu đổi size. CSKH sẽ liên hệ xác nhận trong vòng 24h.",
        data=exchange,
    )
