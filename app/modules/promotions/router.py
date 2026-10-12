from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.responses import APIResponse
from app.modules.promotions.models import Voucher

router = APIRouter(prefix="/promotions", tags=["Promotions & Vouchers"])


class VoucherValidateRequest(BaseModel):
    code: str
    order_amount: float


@router.post("/validate")
async def validate_voucher(req: VoucherValidateRequest, db: Session = Depends(get_db)):
    """Kiểm tra mã giảm giá từ database."""
    voucher = db.query(Voucher).filter(
        Voucher.code == req.code.upper(),
        Voucher.is_active == True,
    ).first()

    if not voucher:
        return APIResponse(
            success=False,
            message="Mã giảm giá không tồn tại hoặc đã hết hạn",
            data={"is_valid": False, "discount_amount": 0},
        )

    if req.order_amount < float(voucher.min_order_amount):
        return APIResponse(
            success=False,
            message=f"Đơn hàng phải từ {int(voucher.min_order_amount):,}₫ để sử dụng mã này",
            data={"is_valid": False, "discount_amount": 0},
        )

    discount = 0
    if voucher.discount_type == "PERCENT":
        discount = req.order_amount * (float(voucher.discount_value) / 100)
    else:
        discount = float(voucher.discount_value)

    return APIResponse(
        success=True,
        message="Áp dụng mã giảm giá thành công",
        data={
            "code": voucher.code,
            "discount_amount": discount,
            "is_valid": True,
        },
    )
