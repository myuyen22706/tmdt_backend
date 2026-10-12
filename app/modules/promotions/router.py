from fastapi import APIRouter
from pydantic import BaseModel
from app.core.responses import APIResponse

router = APIRouter(prefix="/promotions", tags=["Promotions & Vouchers"])


class VoucherValidateRequest(BaseModel):
    code: str
    order_amount: float


@router.post("/validate")
async def validate_voucher(req: VoucherValidateRequest):
    """Kiểm tra mã giảm giá."""
    if req.code.upper() in ["VOVINAM10", "TANBINH20"]:
        discount = 20000 if req.code.upper() == "TANBINH20" else req.order_amount * 0.1
        return APIResponse(
            success=True,
            message="Áp dụng mã giảm giá thành công",
            data={
                "code": req.code.upper(),
                "discount_amount": discount,
                "is_valid": True,
            },
        )
    return APIResponse(
        success=False,
        message="Mã giảm giá không hợp lệ hoặc đã hết lượt",
        data={"is_valid": False, "discount_amount": 0},
    )
