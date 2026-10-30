from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from app.core.config import settings
from app.core.security import create_access_token
from app.modules.payments.momo import build_ipn_signature, generate_mock_ipn_payload


@pytest.fixture
def admin_headers():
    token = create_access_token(subject="usr-admin-01", role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def customer_headers():
    token = create_access_token(subject="usr-cust-01", role="customer")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_momo_create_payment_request(client: AsyncClient, customer_headers, mock_mongo_db):
    """Mục 7: Tạo yêu cầu thanh toán MoMo, sinh payUrl và QR code."""
    now = datetime.now(timezone.utc)
    await mock_mongo_db["orders"].insert_one({
        "order_code": "DT-20261016-MOMO1",
        "user_id": "usr-cust-01",
        "total_amount": 350000,
        "status": "pending_payment",
        "payment_method": "MOMO",
        "created_at": now,
    })

    res = await client.post(
        "/api/v1/payments/momo/create",
        headers=customer_headers,
        json={"order_code": "DT-20261016-MOMO1"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["order_code"] == "DT-20261016-MOMO1"
    assert data["amount"] == 350000
    assert "pay_url" in data
    assert data["pay_url"] is not None
    # MOMO_MOCK: phải mở trang thanh toán giả lập, không được nhảy thẳng tới kết quả thành công
    assert "/payments/momo?" in data["pay_url"]
    assert "resultCode" not in data["pay_url"]


@pytest.mark.asyncio
async def test_momo_ipn_invalid_signature_rejected(client: AsyncClient, mock_mongo_db):
    """Mục 7 & 10: Chặn thông báo IPN có chữ ký số sai."""
    now = datetime.now(timezone.utc)
    await mock_mongo_db["orders"].insert_one({
        "order_code": "DT-20261016-MOMO2",
        "total_amount": 200000,
        "status": "pending_payment",
        "created_at": now,
    })

    bad_ipn = generate_mock_ipn_payload(order_id="DT-20261016-MOMO2", amount=200000, result_code=0)
    bad_ipn["signature"] = "tampered_fake_signature_123456"

    res = await client.post("/api/v1/payments/momo/ipn", json=bad_ipn)
    assert res.status_code == 400
    assert "chữ ký" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_momo_ipn_amount_mismatch_rejected(client: AsyncClient, mock_mongo_db):
    """Mục 7 & 10: Chặn thông báo IPN có số tiền không khớp với đơn hàng."""
    now = datetime.now(timezone.utc)
    # Đơn hàng giá trị 500.000 VND
    await mock_mongo_db["orders"].insert_one({
        "order_code": "DT-20261016-MOMO3",
        "total_amount": 500000,
        "status": "pending_payment",
        "created_at": now,
    })

    # MoMo IPN gửi số tiền chỉ 200.000 VND (gian lận thanh toán)
    mismatch_ipn = generate_mock_ipn_payload(order_id="DT-20261016-MOMO3", amount=200000, result_code=0)

    res = await client.post("/api/v1/payments/momo/ipn", json=mismatch_ipn)
    assert res.status_code == 400
    assert "không khớp" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_momo_ipn_success_deducts_stock_and_records_payment(client: AsyncClient, mock_mongo_db):
    """Mục 7 & 10: Thanh toán MoMo thành công, trừ tồn kho và ghi nhận thanh toán."""
    now = datetime.now(timezone.utc)
    # Sản phẩm có 10 cái tồn kho
    await mock_mongo_db["products"].insert_one({
        "id": "prod-momo-stock",
        "name": "Võ Phục Vovinam MoMo",
        "slug": "vo-phuc-vovinam-momo",
        "is_active": True,
        "variants": [{"sku": "VOV-MOMO-S1", "size": "Size 1", "stock": 10, "price": 300000}],
        "created_at": now,
    })

    # Đơn hàng đang ở trạng thái pending_payment (giữ chỗ 2 cái)
    await mock_mongo_db["orders"].insert_one({
        "order_code": "DT-20261016-MOMO4",
        "total_amount": 600000,
        "status": "pending_payment",
        "items": [
            {
                "product_id": "prod-momo-stock",
                "sku": "VOV-MOMO-S1",
                "product_name": "Võ Phục Vovinam MoMo",
                "price": 300000,
                "quantity": 2,
            }
        ],
        "created_at": now,
    })

    # Giả lập IPN thanh toán thành công (resultCode = 0)
    valid_ipn = generate_mock_ipn_payload(order_id="DT-20261016-MOMO4", amount=600000, result_code=0)
    res = await client.post("/api/v1/payments/momo/ipn", json=valid_ipn)
    assert res.status_code == 200

    # 1. Kiểm tra đơn hàng: Chuyển sang paid
    updated_order = await mock_mongo_db["orders"].find_one({"order_code": "DT-20261016-MOMO4"})
    assert updated_order["status"] == "paid"
    assert updated_order["payment_status"] == "paid"

    # 2. Tồn kho trong MongoDB: Bị trừ hẳn (10 - 2 = 8)
    updated_prod = await mock_mongo_db["products"].find_one({"id": "prod-momo-stock"})
    assert updated_prod["variants"][0]["stock"] == 8

    # 3. Bản ghi thanh toán được lưu vào collection 'payments' (F19)
    payment_rec = await mock_mongo_db["payments"].find_one({"order_code": "DT-20261016-MOMO4"})
    assert payment_rec is not None
    assert payment_rec["status"] == "success"
    assert payment_rec["amount"] == 600000


@pytest.mark.asyncio
async def test_momo_ipn_idempotency_safe_replay(client: AsyncClient, mock_mongo_db):
    """Mục 7: Xử lý lặp an toàn (Idempotency) - IPN gửi lặp nhiều lần chỉ xử lý 1 lần duy nhất."""
    now = datetime.now(timezone.utc)
    await mock_mongo_db["products"].insert_one({
        "id": "prod-idem",
        "is_active": True,
        "variants": [{"sku": "IDEM-S1", "stock": 10}],
    })

    await mock_mongo_db["orders"].insert_one({
        "order_code": "DT-20261016-IDEM",
        "total_amount": 100000,
        "status": "pending_payment",
        "items": [{"product_id": "prod-idem", "sku": "IDEM-S1", "quantity": 1}],
        "created_at": now,
    })

    valid_ipn = generate_mock_ipn_payload(order_id="DT-20261016-IDEM", amount=100000, result_code=0)

    # Gửi IPN lần 1 -> Thành công, trừ 1 tồn kho (10 -> 9)
    res1 = await client.post("/api/v1/payments/momo/ipn", json=valid_ipn)
    assert res1.status_code == 200

    prod_after_1 = await mock_mongo_db["products"].find_one({"id": "prod-idem"})
    assert prod_after_1["variants"][0]["stock"] == 9

    # MoMo gửi IPN lần 2 (lặp lại mạng) -> Phải xử lý lặp an toàn, không được trừ kho lần 2 (vẫn là 9)
    res2 = await client.post("/api/v1/payments/momo/ipn", json=valid_ipn)
    assert res2.status_code == 200
    assert "Idempotent" in res2.json()["message"]

    prod_after_2 = await mock_mongo_db["products"].find_one({"id": "prod-idem"})
    assert prod_after_2["variants"][0]["stock"] == 9  # Vẫn là 9, không bị trừ thành 8!


@pytest.mark.asyncio
async def test_momo_ipn_failed_cancels_order(client: AsyncClient, mock_mongo_db):
    """Mục 7: Khách hủy thanh toán hoặc giao dịch thất bại (resultCode != 0)."""
    now = datetime.now(timezone.utc)
    await mock_mongo_db["orders"].insert_one({
        "order_code": "DT-20261016-FAILED",
        "total_amount": 250000,
        "status": "pending_payment",
        "items": [],
        "created_at": now,
    })

    # MoMo gửi IPN với mã lỗi 1006 (Giao dịch bị người dùng từ chối)
    failed_ipn = generate_mock_ipn_payload(order_id="DT-20261016-FAILED", amount=250000, result_code=1006)
    res = await client.post("/api/v1/payments/momo/ipn", json=failed_ipn)
    assert res.status_code == 200

    order_after = await mock_mongo_db["orders"].find_one({"order_code": "DT-20261016-FAILED"})
    assert order_after["status"] == "cancelled"

    payment_after = await mock_mongo_db["payments"].find_one({"order_code": "DT-20261016-FAILED"})
    assert payment_after["status"] == "failed"


@pytest.mark.asyncio
async def test_momo_auto_cancel_15_minutes_expired(client: AsyncClient, mock_mongo_db):
    """F08: Đơn MoMo giữ chỗ 15 phút, quá hạn tự động hoàn tồn kho và hủy đơn."""
    past_time = datetime.now(timezone.utc) - timedelta(minutes=20)  # Tạo cách đây 20 phút
    await mock_mongo_db["products"].insert_one({
        "id": "prod-timeout",
        "is_active": True,
        "variants": [{"sku": "TIME-S1", "stock": 5}],
    })

    await mock_mongo_db["orders"].insert_one({
        "order_code": "DT-20261016-TIMEOUT",
        "total_amount": 300000,
        "status": "pending_payment",
        "payment_method": "MOMO",
        "items": [{"product_id": "prod-timeout", "sku": "TIME-S1", "quantity": 2}],
        "created_at": past_time,
    })

    # Gọi kiểm tra đơn quá hạn
    res = await client.post("/api/v1/payments/momo/check-expired")
    assert res.status_code == 200
    assert res.json()["cancelled_count"] >= 1

    # Đơn hàng phải chuyển sang cancelled
    cancelled_order = await mock_mongo_db["orders"].find_one({"order_code": "DT-20261016-TIMEOUT"})
    assert cancelled_order["status"] == "cancelled"

    # Tồn kho phải được hoàn lại (5 + 2 = 7)
    prod_after = await mock_mongo_db["products"].find_one({"id": "prod-timeout"})
    assert prod_after["variants"][0]["stock"] == 7


@pytest.mark.asyncio
async def test_f19_payment_transactions_and_manual_refund(client: AsyncClient, admin_headers, mock_mongo_db):
    """F19: Xem giao dịch MoMo, đối soát đơn và đánh dấu hoàn tiền thủ công."""
    now = datetime.now(timezone.utc)
    await mock_mongo_db["payments"].insert_one({
        "id": "pay-sample-01",
        "order_code": "DT-20261016-REFUND",
        "amount": 400000,
        "request_id": "req-123",
        "momo_trans_id": "2837492817",
        "result_code": 0,
        "status": "success",
        "created_at": now,
    })

    # 1. Admin xem danh sách giao dịch
    res_list = await client.get("/api/v1/payments/momo/transactions", headers=admin_headers)
    assert res_list.status_code == 200
    transactions = res_list.json()["data"]
    assert any(t["id"] == "pay-sample-01" for t in transactions)

    # 2. Admin đánh dấu hoàn tiền thủ công
    res_refund = await client.post(
        "/api/v1/payments/momo/transactions/pay-sample-01/refund",
        headers=admin_headers,
        json={"reason": "Khách hàng đổi size không còn mẫu, hoàn tiền lại theo yêu cầu"},
    )
    assert res_refund.status_code == 200
    assert res_refund.json()["data"]["status"] == "refunded"

    # Kiểm tra trong DB: Trạng thái là refunded
    pay_doc = await mock_mongo_db["payments"].find_one({"id": "pay-sample-01"})
    assert pay_doc["status"] == "refunded"
