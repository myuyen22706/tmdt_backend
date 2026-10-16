from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token


@pytest.fixture
def admin_headers():
    token = create_access_token(subject="usr-admin-01", role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def customer_headers():
    token = create_access_token(subject="usr-cust-01", role="customer")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_customer_headers():
    token = create_access_token(subject="usr-cust-02", role="customer")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_f06_cart_crud_and_merge(client: AsyncClient, customer_headers, mock_mongo_db):
    """F06: Thêm, sửa, xóa giỏ hàng và gộp giỏ khách vãng lai vào tài khoản."""
    now = datetime.now(timezone.utc)
    # Tạo sản phẩm mẫu có 10 sản phẩm tồn kho
    await mock_mongo_db["products"].insert_one({
        "id": "prod-vovinam-cart",
        "name": "Võ Phục Vovinam Kaki",
        "slug": "vo-phuc-vovinam-kaki",
        "martial_art_id": "vovinam",
        "category_id": "vo_phuc",
        "price": 250000,
        "is_customizable": True,
        "is_active": True,
        "variants": [{"sku": "VOV-CART-S1", "size": "Size 1", "color": "Xanh", "price": 250000, "stock": 10}],
        "created_at": now,
    })

    # 1. Khách vãng lai (session_id = sess-123) thêm sản phẩm vào giỏ
    guest_headers = {"X-Session-ID": "sess-123"}
    res_add = await client.post(
        "/api/v1/cart/items",
        headers=guest_headers,
        json={"product_id": "prod-vovinam-cart", "sku": "VOV-CART-S1", "quantity": 2},
    )
    assert res_add.status_code == 200
    cart_data = res_add.json()["data"]
    assert cart_data["total_items"] == 2
    assert cart_data["subtotal"] == 500000

    # 2. Thêm quá tồn kho (> 10) -> Báo lỗi 400
    res_exceed = await client.post(
        "/api/v1/cart/items",
        headers=guest_headers,
        json={"product_id": "prod-vovinam-cart", "sku": "VOV-CART-S1", "quantity": 15},
    )
    assert res_exceed.status_code == 400
    assert "tồn kho không đủ" in res_exceed.json()["detail"].lower()

    # 3. Cập nhật số lượng
    res_update = await client.put(
        "/api/v1/cart/items/VOV-CART-S1",
        headers=guest_headers,
        json={"quantity": 3},
    )
    assert res_update.status_code == 200
    assert res_update.json()["data"]["total_items"] == 3

    # 4. Đăng nhập và gộp giỏ hàng khách vãng lai vào tài khoản
    res_merge = await client.post(
        "/api/v1/cart/merge",
        headers=customer_headers,
        json={"session_id": "sess-123"},
    )
    assert res_merge.status_code == 200
    merged_cart = res_merge.json()["data"]
    assert merged_cart["total_items"] == 3

    # Giỏ khách vãng lai phải được làm sạch sau khi gộp
    res_guest_after = await client.get("/api/v1/cart", headers=guest_headers)
    assert res_guest_after.json()["data"]["total_items"] == 0


@pytest.mark.asyncio
async def test_f07_embroidery_validation_and_cod_rejection(client: AsyncClient, mock_mongo_db):
    """F07: Tùy chọn thêu tên và chặn hình thức COD khi đơn có sản phẩm thêu."""
    now = datetime.now(timezone.utc)
    await mock_mongo_db["products"].insert_one({
        "id": "prod-custom-emb",
        "name": "Võ Phục Thêu Tên",
        "slug": "vo-phuc-theu-ten",
        "price": 300000,
        "is_customizable": True,
        "is_active": True,
        "variants": [{"sku": "EMB-S1", "size": "Size 1", "color": "Trắng", "price": 300000, "stock": 20}],
        "created_at": now,
    })

    # 1. Thêu tên quá 20 ký tự -> Báo lỗi
    long_name = "Nguyễn Hoàng Minh Khang Đỗ Gia Bảo"  # > 20 ký tự
    res_long = await client.post(
        "/api/v1/cart/items",
        json={
            "product_id": "prod-custom-emb",
            "sku": "EMB-S1",
            "quantity": 1,
            "is_embroidered": True,
            "embroidery_name": long_name,
        },
    )
    assert res_long.status_code == 422 or res_long.status_code == 400

    # 2. Thêu tên hợp lệ (<= 20 ký tự, có dấu tiếng Việt) -> Thành công
    res_valid = await client.post(
        "/api/v1/cart/items",
        json={
            "product_id": "prod-custom-emb",
            "sku": "EMB-S1",
            "quantity": 1,
            "is_embroidered": True,
            "embroidery_name": "Nguyễn Văn Võ",
        },
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["data"]["has_embroidery"] is True
    assert res_valid.json()["data"]["embroidery_total"] == 30000

    # 3. Đặt hàng: Đơn có hàng thêu nếu chọn thanh toán COD -> Bị từ chối ngay (Mục 2 & F07)
    order_payload = {
        "shipping_address": {
            "recipient_name": "Nguyễn Văn Võ",
            "phone": "0912345678",
            "street_address": "123 Võ Văn Kiệt",
            "city_province": "Hồ Chí Minh",
        },
        "payment_method": "COD",  # Bị cấm vì có thêu tên
        "items": [
            {
                "product_id": "prod-custom-emb",
                "sku": "EMB-S1",
                "product_name": "Võ Phục Thêu Tên",
                "size": "Size 1",
                "price": 300000,
                "quantity": 1,
                "is_embroidered": True,
                "embroidery_name": "Nguyễn Văn Võ",
                "embroidery_fee": 30000,
            }
        ],
    }
    res_order_cod = await client.post("/api/v1/orders", json=order_payload)
    assert res_order_cod.status_code == 400
    assert "thêu tên riêng yêu cầu thanh toán trước" in res_order_cod.json()["detail"]


@pytest.mark.asyncio
async def test_f08_cod_checkout_and_atomic_stock_deduction(client: AsyncClient, mock_mongo_db):
    """F08: Đặt đơn COD thành công, trừ tồn kho chính xác và chống oversell."""
    now = datetime.now(timezone.utc)
    # Sản phẩm chỉ còn đúng 2 cái tồn kho
    await mock_mongo_db["products"].insert_one({
        "id": "prod-stock-test",
        "name": "Áo Giáp Thi Đấu",
        "slug": "ao-giap-thi-dau",
        "price": 350000,
        "is_customizable": False,
        "is_active": True,
        "variants": [{"sku": "GIAP-S2", "size": "Size 2", "color": "Đỏ", "price": 350000, "stock": 2}],
        "created_at": now,
    })

    order_payload = {
        "shipping_address": {
            "recipient_name": "Trần Thị Lan",
            "phone": "0987654321",
            "street_address": "456 Lê Lợi",
            "city_province": "Hồ Chí Minh",
        },
        "payment_method": "COD",
        "items": [
            {
                "product_id": "prod-stock-test",
                "sku": "GIAP-S2",
                "product_name": "Áo Giáp Thi Đấu",
                "size": "Size 2",
                "price": 350000,
                "quantity": 2,  # Mua hết 2 cái
            }
        ],
    }

    # Đơn 1 mua 2 cái -> Thành công
    res1 = await client.post("/api/v1/orders", json=order_payload)
    assert res1.status_code == 200
    order1 = res1.json()["data"]
    assert order1["status"] == "confirmed"
    assert order1["order_code"].startswith("DT-")  # Định dạng DT-YYYYMMDD-XXXX
    assert order1["tracking_code"] is not None

    # Kiểm tra tồn kho trong MongoDB: stock phải giảm về 0
    updated_prod = await mock_mongo_db["products"].find_one({"id": "prod-stock-test"})
    assert updated_prod["variants"][0]["stock"] == 0

    # Kiểm tra lịch sử biến động kho StockMovement
    movement = await mock_mongo_db["stock_movements"].find_one({"sku": "GIAP-S2"})
    assert movement is not None
    assert movement["quantity_change"] == -2

    # Đơn 2 cố tình đặt tiếp khi tồn kho đã về 0 -> Bị từ chối (Oversell prevented)
    res2 = await client.post("/api/v1/orders", json=order_payload)
    assert res2.status_code == 400
    assert "không đủ số lượng tồn kho" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_section6_order_status_transitions_and_cancel_restore_stock(
    client: AsyncClient, admin_headers, customer_headers, mock_mongo_db
):
    """Mục 6: Luồng chuyển trạng thái đơn hàng và hủy đơn hoàn tồn kho."""
    now = datetime.now(timezone.utc)
    await mock_mongo_db["products"].insert_one({
        "id": "prod-cancel-test",
        "name": "Đai Vovinam Đen",
        "slug": "dai-vovinam-den",
        "price": 100000,
        "is_active": True,
        "variants": [{"sku": "DAI-DEN", "size": "Freesize", "color": "Đen", "price": 100000, "stock": 10}],
        "created_at": now,
    })

    # Tạo đơn COD (tồn kho từ 10 -> 8)
    order_res = await client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json={
            "shipping_address": {
                "recipient_name": "Võ Sinh Nam",
                "phone": "0911222333",
                "street_address": "12 Hai Bà Trưng",
                "city_province": "Hà Nội",
            },
            "payment_method": "COD",
            "items": [
                {
                    "product_id": "prod-cancel-test",
                    "sku": "DAI-DEN",
                    "product_name": "Đai Vovinam Đen",
                    "size": "Freesize",
                    "price": 100000,
                    "quantity": 2,
                }
            ],
        },
    )
    assert order_res.status_code == 200
    order_code = order_res.json()["data"]["order_code"]

    # Tồn kho hiện tại = 8
    p = await mock_mongo_db["products"].find_one({"id": "prod-cancel-test"})
    assert p["variants"][0]["stock"] == 8

    # 1. Admin chuyển trạng thái sai luồng: confirmed nhảy sang delivered -> Lỗi 400
    res_invalid = await client.patch(
        f"/api/v1/orders/{order_code}/status",
        headers=admin_headers,
        json={"new_status": "delivered"},
    )
    assert res_invalid.status_code == 400
    assert "không hợp lệ" in res_invalid.json()["detail"]

    # 2. Admin chuyển trạng thái đúng: confirmed -> processing
    res_valid = await client.patch(
        f"/api/v1/orders/{order_code}/status",
        headers=admin_headers,
        json={"new_status": "processing", "note": "Đang đóng gói kiện hàng"},
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["data"]["status"] == "processing"

    # 3. Khách hàng hủy đơn khi đang processing -> Được phép và tồn kho được hoàn lại
    cancel_res = await client.post(f"/api/v1/orders/{order_code}/cancel", headers=customer_headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["data"]["status"] == "cancelled"

    # Tồn kho trong MongoDB phải được hoàn lại (8 + 2 = 10)
    p_after_cancel = await mock_mongo_db["products"].find_one({"id": "prod-cancel-test"})
    assert p_after_cancel["variants"][0]["stock"] == 10


@pytest.mark.asyncio
async def test_f09_order_tracking_and_idor_protection(
    client: AsyncClient, customer_headers, other_customer_headers, mock_mongo_db
):
    """F09 & Mục 9: Khách hàng chỉ xem được đơn hàng của mình (chống lỗ hổng IDOR)."""
    now = datetime.now(timezone.utc)
    # Tạo đơn của customer 1 (sub = usr-cust-01)
    await mock_mongo_db["orders"].insert_one({
        "id": "ord-cust-01",
        "order_code": "DT-20261016-CUST1",
        "user_id": "usr-cust-01",
        "customer_name": "Khách Hàng 1",
        "customer_phone": "0901111111",
        "shipping_address": "TP.HCM",
        "subtotal": 200000,
        "shipping_fee": 25000,
        "total_amount": 225000,
        "payment_method": "COD",
        "status": "confirmed",
        "items": [],
        "created_at": now,
    })

    # Customer 1 xem đơn của mình -> 200 OK
    res_owner = await client.get("/api/v1/orders/DT-20261016-CUST1", headers=customer_headers)
    assert res_owner.status_code == 200
    assert res_owner.json()["data"]["order_code"] == "DT-20261016-CUST1"

    # Customer 2 (sub = usr-cust-02) cố tình truy cập đơn của Customer 1 -> 403 Forbidden (IDOR Blocked)
    res_other = await client.get("/api/v1/orders/DT-20261016-CUST1", headers=other_customer_headers)
    assert res_other.status_code == 403


@pytest.mark.asyncio
async def test_f17_inventory_adjust_and_low_stock_alert(client: AsyncClient, admin_headers, mock_mongo_db):
    """F17: Quản lý tồn kho: điều chỉnh thủ công và cảnh báo tồn thấp."""
    now = datetime.now(timezone.utc)
    await mock_mongo_db["products"].insert_one({
        "id": "prod-inv-test",
        "name": "Võ Phục Vovinam Trẻ Em",
        "slug": "vo-phuc-vovinam-tre-em",
        "price": 220000,
        "is_active": True,
        "variants": [
            {"sku": "VOV-LOW-S0", "size": "Size 0", "color": "Xanh", "price": 220000, "stock": 3, "low_stock_threshold": 5},
            {"sku": "VOV-NORM-S1", "size": "Size 1", "color": "Xanh", "price": 220000, "stock": 15, "low_stock_threshold": 5},
        ],
        "created_at": now,
    })

    # 1. Truy vấn danh sách cảnh báo tồn thấp -> Phải có SKU VOV-LOW-S0 (tồn 3 <= ngưỡng 5)
    res_low = await client.get("/api/v1/orders/inventory/low-stock", headers=admin_headers)
    assert res_low.status_code == 200
    low_items = res_low.json()["data"]
    assert any(it["sku"] == "VOV-LOW-S0" for it in low_items)

    # 2. Admin nhập kho thêm 10 bộ cho SKU VOV-LOW-S0
    res_adjust = await client.post(
        "/api/v1/orders/inventory/adjust?product_id=prod-inv-test&sku=VOV-LOW-S0&quantity_change=10&reason=Nhap_hang_bo_sung",
        headers=admin_headers,
    )
    assert res_adjust.status_code == 200

    # Tồn kho sau nhập: 3 + 10 = 13
    p_updated = await mock_mongo_db["products"].find_one({"id": "prod-inv-test"})
    assert p_updated["variants"][0]["stock"] == 13
