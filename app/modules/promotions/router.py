from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.database import get_db
from app.core.responses import APIResponse

router = APIRouter(prefix="/promotions", tags=["Promotions & Vouchers"])


class VoucherValidateRequest(BaseModel):
    code: str
    order_amount: float


@router.get("/active")
async def list_active_vouchers(response: Response, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Danh sách mã giảm giá đang hiệu lực (còn lượt) để hiển thị ở khu "Ưu đãi hôm nay"."""
    vouchers = await db["vouchers"].find({"is_active": True}, {"_id": 0}).sort("discount_value", -1).to_list(length=20)
    data = [
        {
            "code": v.get("code"),
            "discount_type": v.get("discount_type"),
            "discount_value": int(v.get("discount_value", 0)),
            "min_order_amount": int(v.get("min_order_amount", 0)),
        }
        for v in vouchers
        if v.get("usage_limit") is None or int(v.get("used_count", 0)) < int(v.get("usage_limit"))
    ]
    response.headers["Cache-Control"] = f"public, max-age={settings.PUBLIC_CACHE_MAX_AGE}"
    return APIResponse(success=True, message="Mã giảm giá đang hiệu lực", data=data)


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
            message=f"Đơn hàng phải từ {int(min_order):,}₫ để sử dụng mã này".replace(",", "."),
            data={"is_valid": False, "discount_amount": 0},
        )

    usage_limit = voucher.get("usage_limit")
    if usage_limit is not None and int(voucher.get("used_count", 0)) >= int(usage_limit):
        return APIResponse(
            success=False,
            message="Mã giảm giá đã hết lượt sử dụng",
            data={"is_valid": False, "discount_amount": 0},
        )

    discount_val = float(voucher.get("discount_value", 0))
    if voucher.get("discount_type") == "PERCENT":
        discount = int(req.order_amount * (discount_val / 100))
    else:
        discount = int(discount_val)
    discount = min(discount, int(req.order_amount))

    return APIResponse(
        success=True,
        message="Áp dụng mã giảm giá thành công",
        data={
            "code": voucher.get("code"),
            "discount_amount": discount,
            "is_valid": True,
        },
    )

