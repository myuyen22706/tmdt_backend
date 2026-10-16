import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token


@pytest.fixture
def admin_headers():
    token = create_access_token(subject="usr-admin-01", role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def staff_headers():
    token = create_access_token(subject="usr-staff-01", role="staff")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def customer_headers():
    token = create_access_token(subject="usr-customer-01", role="customer")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_f10_return_request_success_and_restrictions(client: AsyncClient, mock_mongo_db):
    """F10: Kiểm thử yêu cầu đổi size:
    - Thành công trong vòng 7 ngày khi đơn đã 'delivered'.
    - Chặn từ chối nếu sản phẩm có thêu tên (is_embroidered=True).
    - Chặn từ chối nếu đơn chưa giao (chưa 'delivered').
    - Chặn từ chối nếu quá thời hạn 7 ngày.
    """
    now = datetime.now(timezone.utc)

    # 1. Tạo đơn hàng mẫu hợp lệ (đã delivered cách đây 2 ngày)
    delivered_2days_ago = now - timedelta(days=2)
    order_delivered = {
        "order_code": "DT-20261016-RET1",
        "user_id": "usr-customer-01",
        "customer_name": "Trần Văn Nam",
        "customer_phone": "0912345678",
        "status": "delivered",
        "total_amount": 350000,
        "items": [
            {
                "product_id": "prod-vovinam-01",
                "product_name": "Võ phục Vovinam Tiêu Chuẩn",
                "sku": "VOV-STD-S",
                "size": "S",
                "price": 350000,
                "quantity": 1,
                "is_embroidered": False,
            }
        ],
        "status_history": [
            {"old_status": "shipping", "new_status": "delivered", "timestamp": delivered_2days_ago}
        ],
        "created_at": now - timedelta(days=5),
        "updated_at": delivered_2days_ago,
    }
    await mock_mongo_db["orders"].insert_one(order_delivered)

    # 1a. Gửi yêu cầu đổi size thành công
    req_payload = {
        "order_code": "DT-20261016-RET1",
        "product_id": "prod-vovinam-01",
        "sku": "VOV-STD-S",
        "desired_size": "M",
        "reason": "Mặc bị kích vai, cần đổi lên size M rộng hơn",
    }
    res_req = await client.post("/api/v1/admin/returns/request", json=req_payload)
    assert res_req.status_code == 200
    ret_data = res_req.json()["data"]
    assert ret_data["status"] == "pending"
    assert ret_data["desired_size"] == "M"

    # Kiểm tra đơn hàng được chuyển sang 'return_requested'
    updated_order = await mock_mongo_db["orders"].find_one({"order_code": "DT-20261016-RET1"})
    assert updated_order["status"] == "return_requested"

    # 1b. Chặn đổi trả đơn có hàng thêu tên
    order_embroidered = {
        "order_code": "DT-20261016-EMB1",
        "status": "delivered",
        "total_amount": 380000,
        "items": [
            {
                "product_id": "prod-vovinam-01",
                "sku": "VOV-STD-M",
                "size": "M",
                "price": 350000,
                "quantity": 1,
                "is_embroidered": True,
                "embroidery_text": "NGUYEN VAN A",
            }
        ],
        "status_history": [
            {"old_status": "shipping", "new_status": "delivered", "timestamp": delivered_2days_ago}
        ],
        "created_at": now - timedelta(days=3),
    }
    await mock_mongo_db["orders"].insert_one(order_embroidered)

    res_emb = await client.post("/api/v1/admin/returns/request", json={
        "order_code": "DT-20261016-EMB1",
        "product_id": "prod-vovinam-01",
        "sku": "VOV-STD-M",
        "desired_size": "L",
        "reason": "Đổi size do mặc hơi chật",
    })
    assert res_emb.status_code == 400
    assert "thêu tên" in res_emb.json()["detail"].lower()

    # 1c. Chặn đổi trả khi đơn chưa delivered (đang shipping)
    order_shipping = {
        "order_code": "DT-20261016-SHIP1",
        "status": "shipping",
        "total_amount": 350000,
        "items": [
            {"product_id": "prod-vovinam-01", "sku": "VOV-STD-L", "size": "L", "quantity": 1, "is_embroidered": False}
        ],
    }
    await mock_mongo_db["orders"].insert_one(order_shipping)

    res_ship = await client.post("/api/v1/admin/returns/request", json={
        "order_code": "DT-20261016-SHIP1",
        "product_id": "prod-vovinam-01",
        "sku": "VOV-STD-L",
        "desired_size": "XL",
        "reason": "Muốn đổi size khác",
    })
    assert res_ship.status_code == 400
    assert "delivered" in res_ship.json()["detail"].lower()

    # 1d. Chặn đổi trả khi đơn đã quá 7 ngày
    delivered_10days_ago = now - timedelta(days=10)
    order_expired = {
        "order_code": "DT-20261016-OLD1",
        "status": "delivered",
        "total_amount": 350000,
        "items": [
            {"product_id": "prod-vovinam-01", "sku": "VOV-STD-XL", "size": "XL", "quantity": 1, "is_embroidered": False}
        ],
        "status_history": [
            {"old_status": "shipping", "new_status": "delivered", "timestamp": delivered_10days_ago}
        ],
        "updated_at": delivered_10days_ago,
    }
    await mock_mongo_db["orders"].insert_one(order_expired)

    res_old = await client.post("/api/v1/admin/returns/request", json={
        "order_code": "DT-20261016-OLD1",
        "product_id": "prod-vovinam-01",
        "sku": "VOV-STD-XL",
        "desired_size": "2XL",
        "reason": "Mặc chật muốn đổi",
    })
    assert res_old.status_code == 400
    assert "quá thời hạn 7 ngày" in res_old.json()["detail"].lower()


@pytest.mark.asyncio
async def test_f20_admin_review_and_receive_return(client: AsyncClient, staff_headers, mock_mongo_db):
    """F20: Staff/Admin duyệt đổi trả, xác nhận nhận hàng và tự động cộng hoàn tồn kho."""
    now = datetime.now(timezone.utc)

    # Chuẩn bị sản phẩm và tồn kho ban đầu (size S có tồn kho 5)
    await mock_mongo_db["products"].insert_one({
        "id": "prod-karate-01",
        "name": "Võ phục Karate Kumite",
        "variants": [
            {"sku": "KAR-KUM-S", "size": "S", "stock": 5},
            {"sku": "KAR-KUM-M", "size": "M", "stock": 8},
        ],
    })

    # Tạo 1 yêu cầu đổi trả đang pending
    return_id = f"ret-{uuid.uuid4().hex[:8]}"
    await mock_mongo_db["return_requests"].insert_one({
        "id": return_id,
        "order_code": "DT-20261016-KAR1",
        "product_id": "prod-karate-01",
        "sku": "KAR-KUM-S",
        "current_size": "S",
        "desired_size": "M",
        "reason": "Chật bắp tay",
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    })

    # 1. Staff duyệt yêu cầu (Approve) -> Sinh mã đơn đổi EX-...
    res_rev = await client.patch(
        f"/api/v1/admin/returns/{return_id}/review",
        json={"action": "approve", "note": "Đủ điều kiện đổi size, vui lòng gửi hàng về kho"},
        headers=staff_headers,
    )
    assert res_rev.status_code == 200
    approved_data = res_rev.json()["data"]
    assert approved_data["status"] == "approved"
    assert approved_data["exchange_order_code"].startswith("EX-")

    # 2. Staff xác nhận đã nhận hàng hoàn về kho
    res_rec = await client.post(
        f"/api/v1/admin/returns/{return_id}/receive",
        headers=staff_headers,
    )
    assert res_rec.status_code == 200
    assert res_rec.json()["data"]["status"] == "completed"

    # Kiểm tra tồn kho của SKU size cũ (KAR-KUM-S) đã được cộng thêm 1 (từ 5 lên 6)
    prod_updated = await mock_mongo_db["products"].find_one({"id": "prod-karate-01"})
    v_s = next(v for v in prod_updated["variants"] if v["sku"] == "KAR-KUM-S")
    assert v_s["stock"] == 6

    # Kiểm tra bản ghi StockMovement đã được ghi nhận
    movement = await mock_mongo_db["stock_movements"].find_one({"sku": "KAR-KUM-S", "quantity_change": 1})
    assert movement is not None


@pytest.mark.asyncio
async def test_f18_packing_slip_generation(client: AsyncClient, staff_headers, mock_mongo_db):
    """F18: Tạo và in phiếu đóng gói (Packing Slip) cho đơn hàng."""
    now = datetime.now(timezone.utc)
    order_doc = {
        "order_code": "DT-20261016-SLIP1",
        "customer_name": "Lê Hoàng Quân",
        "customer_phone": "0987654321",
        "shipping_address": {
            "street_address": "123 Đường 3/2",
            "ward": "Phường 11",
            "district": "Quận 10",
            "city_province": "TP. Hồ Chí Minh",
        },
        "carrier": "MockShipping",
        "tracking_code": "VN-MOCK-998877",
        "status": "processing",
        "items": [
            {
                "product_name": "Võ phục Taekwondo Poomsae",
                "sku": "TAE-POOM-L",
                "size": "L",
                "quantity": 2,
                "is_embroidered": True,
                "embroidery_text": "LE HOANG QUAN",
                "embroidery_position": "Ngực trái",
            }
        ],
        "created_at": now,
    }
    await mock_mongo_db["orders"].insert_one(order_doc)

    res_slip = await client.get(
        "/api/v1/admin/orders/DT-20261016-SLIP1/packing-slip",
        headers=staff_headers,
    )
    assert res_slip.status_code == 200
    slip = res_slip.json()["data"]
    assert slip["order_code"] == "DT-20261016-SLIP1"
    assert slip["customer_name"] == "Lê Hoàng Quân"
    assert slip["total_quantity"] == 2
    assert "THÊU TÊN RIÊNG" in slip["notes"]


@pytest.mark.asyncio
async def test_f22_f23_revenue_report_and_rbac_staff_blocking(
    client: AsyncClient, admin_headers, staff_headers, mock_mongo_db
):
    """F22 & F23: Báo cáo Doanh thu & Phân quyền RBAC nghiêm ngặt:
    - Admin truy cập báo cáo doanh thu thành công.
    - Staff truy cập báo cáo doanh thu BẮT BUỘC BỊ CHẶN (403 Forbidden).
    - Staff xuất CSV báo cáo doanh thu BẮT BUỘC BỊ CHẶN (403 Forbidden).
    - Xuất CSV của Admin có UTF-8 BOM.
    """
    now = datetime.now(timezone.utc)

    # Tạo đơn lẻ và đơn võ đường
    await mock_mongo_db["orders"].insert_many([
        {
            "order_code": "DT-20261016-REV1",
            "channel": "retail",
            "status": "completed",
            "total_amount": 500000,
            "created_at": now,
            "items": [{"product_id": "prod-vovinam-01", "product_name": "Võ phục Vovinam", "quantity": 1, "price": 500000}],
        },
        {
            "order_code": "DT-20261016-REV2",
            "channel": "club",
            "status": "delivered",
            "total_amount": 2500000,
            "created_at": now,
            "items": [{"product_id": "prod-vovinam-01", "product_name": "Võ phục Vovinam", "quantity": 5, "price": 500000}],
        },
    ])

    # 1. Admin xem báo cáo doanh thu thành công
    res_admin = await client.get("/api/v1/admin/reports/revenue", headers=admin_headers)
    assert res_admin.status_code == 200
    rep = res_admin.json()["data"]
    assert rep["total_revenue"] == 3000000
    assert rep["retail_revenue"] == 500000
    assert rep["club_revenue"] == 2500000

    # 2. Staff xem báo cáo doanh thu -> BẮT BUỘC 403 Forbidden (RBAC F23)
    res_staff = await client.get("/api/v1/admin/reports/revenue", headers=staff_headers)
    assert res_staff.status_code == 403

    # 3. Staff xuất CSV -> BẮT BUỘC 403 Forbidden
    res_staff_csv = await client.get("/api/v1/admin/reports/export-csv", headers=staff_headers)
    assert res_staff_csv.status_code == 403

    # 4. Admin xuất CSV thành công với UTF-8 BOM
    res_admin_csv = await client.get("/api/v1/admin/reports/export-csv", headers=admin_headers)
    assert res_admin_csv.status_code == 200
    assert res_admin_csv.headers["content-type"].startswith("text/csv")
    assert res_admin_csv.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM bytes


@pytest.mark.asyncio
async def test_f23_activity_logs_and_user_role_management(
    client: AsyncClient, admin_headers, staff_headers, mock_mongo_db
):
    """F23: Xem Activity Logs và Phân quyền tài khoản người dùng:
    - Admin xem được Activity Logs.
    - Staff xem Activity Logs bị chặn 403.
    - Admin cập nhật vai trò người dùng (Customer -> Staff).
    """
    now = datetime.now(timezone.utc)

    # Thêm sẵn một số log hoạt động
    await mock_mongo_db["activity_logs"].insert_one({
        "id": "act-test-01",
        "actor": "0988000001",
        "actor_role": "admin",
        "action": "ADMIN_LOGIN",
        "target_type": "auth",
        "target_id": "usr-admin-01",
        "timestamp": now,
    })

    # 1. Admin xem nhật ký hoạt động
    res_logs = await client.get("/api/v1/admin/activity-logs", headers=admin_headers)
    assert res_logs.status_code == 200
    logs = res_logs.json()["data"]
    assert len(logs) >= 1
    assert any(l["action"] == "ADMIN_LOGIN" for l in logs)

    # 2. Staff xem nhật ký hoạt động -> BỊ CHẶN 403
    res_staff_logs = await client.get("/api/v1/admin/activity-logs", headers=staff_headers)
    assert res_staff_logs.status_code == 403

    # 3. Quản lý phân quyền người dùng
    await mock_mongo_db["users"].insert_one({
        "id": "usr-demo-99",
        "phone": "0919999999",
        "full_name": "Nhân Viên Mới",
        "role": "customer",
        "is_active": True,
    })

    res_role = await client.patch(
        "/api/v1/admin/users/usr-demo-99/role?new_role=staff",
        headers=admin_headers,
    )
    assert res_role.status_code == 200
    assert res_role.json()["data"]["new_role"] == "staff"

    # Kiểm tra database đã cập nhật role = staff
    usr_in_db = await mock_mongo_db["users"].find_one({"id": "usr-demo-99"})
    assert usr_in_db["role"] == "staff"

    # Kiểm tra đã tự động ghi log CHANGE_USER_ROLE vào activity_logs
    act_log = await mock_mongo_db["activity_logs"].find_one({"action": "CHANGE_USER_ROLE", "target_id": "usr-demo-99"})
    assert act_log is not None
