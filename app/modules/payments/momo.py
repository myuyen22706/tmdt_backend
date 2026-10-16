import hashlib
import hmac
import time
import uuid
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings


def generate_signature(raw_data: str, secret_key: str) -> str:
    """Tạo chữ ký HMAC-SHA256 theo chuẩn MoMo API v2."""
    return hmac.new(
        secret_key.encode("utf-8"),
        raw_data.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_create_signature(
    access_key: str,
    amount: int,
    extra_data: str,
    ipn_url: str,
    order_id: str,
    order_info: str,
    partner_code: str,
    redirect_url: str,
    request_id: str,
    request_type: str,
    secret_key: str,
) -> str:
    """Tạo chữ ký số cho yêu cầu tạo giao dịch MoMo:
    Format: accessKey=$accessKey&amount=$amount&extraData=$extraData&ipnUrl=$ipnUrl&orderId=$orderId&orderInfo=$orderInfo&partnerCode=$partnerCode&redirectUrl=$redirectUrl&requestId=$requestId&requestType=$requestType
    """
    raw_signature = (
        f"accessKey={access_key}"
        f"&amount={amount}"
        f"&extraData={extra_data}"
        f"&ipnUrl={ipn_url}"
        f"&orderId={order_id}"
        f"&orderInfo={order_info}"
        f"&partnerCode={partner_code}"
        f"&redirectUrl={redirect_url}"
        f"&requestId={request_id}"
        f"&requestType={request_type}"
    )
    return generate_signature(raw_signature, secret_key)


def build_ipn_signature(data: Dict[str, Any], secret_key: str, access_key: str) -> str:
    """Tạo chữ ký số chuẩn cho MoMo IPN để đối soát và xác minh tính toàn vẹn:
    Format: accessKey=$accessKey&amount=$amount&extraData=$extraData&message=$message&orderId=$orderId&orderInfo=$orderInfo&orderType=$orderType&partnerCode=$partnerCode&payType=$payType&requestId=$requestId&responseTime=$responseTime&resultCode=$resultCode&transId=$transId
    """
    raw_signature = (
        f"accessKey={access_key}"
        f"&amount={data.get('amount')}"
        f"&extraData={data.get('extraData', '')}"
        f"&message={data.get('message', '')}"
        f"&orderId={data.get('orderId')}"
        f"&orderInfo={data.get('orderInfo', '')}"
        f"&orderType={data.get('orderType', 'momo_wallet')}"
        f"&partnerCode={data.get('partnerCode', settings.MOMO_PARTNER_CODE)}"
        f"&payType={data.get('payType', 'qr')}"
        f"&requestId={data.get('requestId')}"
        f"&responseTime={data.get('responseTime')}"
        f"&resultCode={data.get('resultCode')}"
        f"&transId={data.get('transId')}"
    )
    return generate_signature(raw_signature, secret_key)


def verify_ipn_signature(data: Dict[str, Any]) -> bool:
    """Xác minh chữ ký số IPN gửi từ MoMo (Mục 7)."""
    incoming_sig = data.get("signature", "")
    if not incoming_sig:
        return False

    expected_sig = build_ipn_signature(
        data=data,
        secret_key=settings.MOMO_SECRET_KEY,
        access_key=settings.MOMO_ACCESS_KEY,
    )
    return hmac.compare_digest(incoming_sig, expected_sig)


async def create_momo_payment(order_id: str, amount: int, order_info: str) -> Dict[str, Any]:
    """Tạo yêu cầu thanh toán sang MoMo (Hỗ trợ cả môi trường thử thật và chế độ MOMO_MOCK)."""
    request_id = str(uuid.uuid4())
    partner_code = settings.MOMO_PARTNER_CODE
    access_key = settings.MOMO_ACCESS_KEY
    secret_key = settings.MOMO_SECRET_KEY
    redirect_url = settings.MOMO_REDIRECT_URL
    ipn_url = settings.MOMO_IPN_URL
    request_type = "captureWallet"
    extra_data = ""

    signature = build_create_signature(
        access_key=access_key,
        amount=amount,
        extra_data=extra_data,
        ipn_url=ipn_url,
        order_id=order_id,
        order_info=order_info,
        partner_code=partner_code,
        redirect_url=redirect_url,
        request_id=request_id,
        request_type=request_type,
        secret_key=secret_key,
    )

    request_payload = {
        "partnerCode": partner_code,
        "partnerName": "Website Võ Phục Đai Trắng",
        "storeId": "DaiTrangStore",
        "requestId": request_id,
        "amount": amount,
        "orderId": order_id,
        "orderInfo": order_info,
        "redirectUrl": redirect_url,
        "ipnUrl": ipn_url,
        "lang": "vi",
        "extraData": extra_data,
        "requestType": request_type,
        "signature": signature,
    }

    # Chế độ MOMO_MOCK=True để demo khi chưa có khóa thử thực tế (Mục 7)
    if settings.MOMO_MOCK:
        mock_pay_url = f"{redirect_url}?orderId={order_id}&amount={amount}&requestId={request_id}&resultCode=0&message=Success"
        mock_qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={mock_pay_url}"
        return {
            "partnerCode": partner_code,
            "orderId": order_id,
            "requestId": request_id,
            "amount": amount,
            "responseTime": int(time.time() * 1000),
            "message": "Thành công (MOMO_MOCK=True)",
            "resultCode": 0,
            "payUrl": mock_pay_url,
            "deeplink": f"momo://app?action=pay&orderId={order_id}",
            "qrCodeUrl": mock_qr_url,
        }

    # Gửi yêu cầu thực tế tới MoMo Gateway API
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(settings.MOMO_ENDPOINT, json=request_payload)
            return resp.json()
        except Exception as e:
            return {
                "resultCode": 99,
                "message": f"Không thể kết nối tới MoMo API: {str(e)}",
                "payUrl": None,
            }


def generate_mock_ipn_payload(
    order_id: str,
    amount: int,
    result_code: int = 0,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Tạo payload IPN hợp lệ có kèm chữ ký số HMAC-SHA256 chuẩn để phục vụ kiểm thử và demo."""
    req_id = request_id or str(uuid.uuid4())
    trans_id = random_trans_id = int(time.time() * 100)
    response_time = int(time.time() * 1000)
    message = "Giao dịch thành công." if result_code == 0 else "Giao dịch bị hủy hoặc thất bại."

    data = {
        "partnerCode": settings.MOMO_PARTNER_CODE,
        "orderId": order_id,
        "requestId": req_id,
        "amount": amount,
        "orderInfo": f"Thanh toan don hang {order_id}",
        "orderType": "momo_wallet",
        "transId": trans_id,
        "resultCode": result_code,
        "message": message,
        "payType": "qr",
        "responseTime": response_time,
        "extraData": "",
    }
    data["signature"] = build_ipn_signature(data, settings.MOMO_SECRET_KEY, settings.MOMO_ACCESS_KEY)
    return data
