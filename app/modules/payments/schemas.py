from datetime import datetime
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field


class PaymentCreateRequest(BaseModel):
    order_code: str = Field(..., description="Mã đơn hàng cần thanh toán, ví dụ: DT-20261016-XXXX")


class PaymentCreateResponse(BaseModel):
    order_code: str
    amount: int
    request_id: str
    pay_url: str
    qr_code_url: Optional[str] = None
    message: str


class MoMoIPNPayload(BaseModel):
    partnerCode: str
    orderId: str
    requestId: str
    amount: int
    orderInfo: Optional[str] = ""
    orderType: Optional[str] = "momo_wallet"
    transId: Union[int, str]
    resultCode: int
    message: Optional[str] = ""
    payType: Optional[str] = "qr"
    responseTime: int
    extraData: Optional[str] = ""
    signature: str


class MockCallbackRequest(BaseModel):
    order_code: str
    result_code: int = Field(0, description="0 là thành công, khác 0 là thất bại/hủy")


class PaymentRecordResponse(BaseModel):
    id: str
    order_code: str
    amount: int
    request_id: str
    momo_trans_id: Optional[str] = None
    result_code: int
    status: str  # success, failed, refunded
    raw_response: Optional[Dict[str, Any]] = None
    created_at: datetime


class RefundRequest(BaseModel):
    reason: str = Field(..., description="Lý do hoàn tiền (đơn hủy, đổi trả...)")
    refund_amount: Optional[int] = Field(None, ge=0, description="Số tiền hoàn lại")
