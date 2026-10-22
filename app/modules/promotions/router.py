from fastapi import APIRouter, Depends
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_db
from app.core.responses import APIResponse

router = APIRouter(prefix="/promotions", tags=["Promotions & Vouchers"])


class VoucherValidateRequest(BaseModel):
    code: str
    order_amount: float


@router.post("/validate")
async def validate_voucher(req: VoucherValidateRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Kiểm tra mã giảm giá từ database MongoDB."""
    vouchers_col = db["vouchers"]
    voucher = await vouchers_col.find_one({
        "code": req.code.upper(),
        "is_active": True,
    })

    if not voucher:
        return APIResponse(
            success=False,
            message="Mã giảm giá không tồn tại hoặc đã hết hạn",
            data={"is_valid": False, "discount_amount": 0},
        )

    min_order = float(voucher.get("min_order_amount", 0))
    if req.order_amount < min_order:
        return APIResponse(
            success=False,
            message=f"Đơn hàng phải từ {int(min_order):,}₫ để sử dụng mã này",
            data={"is_valid": False, "discount_amount": 0},
        )

    discount = 0.0
    discount_val = float(voucher.get("discount_value", 0))
    if voucher.get("discount_type") == "PERCENT":
        discount = req.order_amount * (discount_val / 100)
    else:
        discount = discount_val

    return APIResponse(
        success=True,
        message="Áp dụng mã giảm giá thành công",
        data={
            "code": voucher.get("code"),
            "discount_amount": discount,
            "is_valid": True,
        },
    )

