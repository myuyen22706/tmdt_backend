from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token


@pytest.fixture
def admin_headers():
    token = create_access_token(subject="usr-admin-01", role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def coach_headers():
    token = create_access_token(subject="usr-coach-01", role="coach")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_f11_club_registration_and_approval(client: AsyncClient, admin_headers, mock_mongo_db):
    """F11: Đăng ký CLB/Võ đường và Quản trị viên duyệt kích hoạt."""
    # 1. Đăng ký võ đường mới
    reg_payload = {
        "club_name": "CLB Vovinam Lam Sơn",
        "martial_art_id": "vovinam",
        "address": "Số 10 Lý Thường Kiệt, Quận 10, TP.HCM",
        "coach_name": "Nguyễn Văn Hùng",
        "coach_phone": "0905123456",
        "coach_email": "hung.vovinam@example.com",
    }
    res_reg = await client.post("/api/v1/dojos/clubs", json=reg_payload)
    assert res_reg.status_code == 200
    club = res_reg.json()["data"]
    assert club["status"] == "pending"  # Chờ duyệt
    club_id = club["id"]

    # 2. Admin duyệt kích hoạt võ đường
    res_app = await client.patch(
        f"/api/v1/dojos/clubs/{club_id}/approve?action=approve",
        headers=admin_headers,
    )
    assert res_app.status_code == 200
    assert res_app.json()["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_f12_create_campaign_and_discount_tier(client: AsyncClient, coach_headers, mock_mongo_db):
    """F12: Tạo đợt đặt hàng chung, tự động tính bậc giá sỉ và sinh link/QR."""
    now = datetime.now(timezone.utc)
    # Tạo CLB active trong DB
    await mock_mongo_db["clubs"].insert_one({
        "id": "club-active-01",
        "club_name": "Võ Đường Karate Thăng Long",
        "martial_art_id": "karate",
        "status": "active",
        "created_at": now,
    })

    # Tạo đợt hàng với số lượng dự kiến 50 bộ -> Bậc giá sỉ giảm 20%
    deadline = (now + timedelta(days=14)).isoformat()
    campaign_payload = {
        "club_id": "club-active-01",
        "campaign_title": "Đợt Đặt Đồng Phục Khóa Hè 2026",
        "applicable_product_ids": ["prod-kar-01"],
        "target_quantity": 50,  # 50 bộ -> giảm 20%
        "deadline": deadline,
        "has_custom_logo": True,
        "allow_club_consolidated_payment": True,
    }

    res = await client.post("/api/v1/dojos/campaigns", headers=coach_headers, json=campaign_payload)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["discount_percent"] == 20  # Bậc sỉ 20%
    assert data["campaign_code"].startswith("CP-")
    assert "campaign_url" in data
    assert "qr_code_url" in data
    assert data["status"] == "open"


@pytest.mark.asyncio
async def test_f13_parent_order_in_campaign(client: AsyncClient, mock_mongo_db):
    """F13: Phụ huynh đặt hàng theo đợt, áp dụng giá sỉ và chọn thanh toán gộp."""
    now = datetime.now(timezone.utc)
    # Tạo sản phẩm giá gốc 300.000 VND
    await mock_mongo_db["products"].insert_one({
        "id": "prod-vov-camp",
        "name": "Võ Phục Vovinam Đồng Phục",
        "price": 300000,
        "is_active": True,
        "variants": [{"sku": "VOV-CAMP-S2", "size": "Size 2", "stock": 100}],
    })

    # Tạo chiến dịch chiết khấu 15% (30-49 bộ)
    await mock_mongo_db["club_campaigns"].insert_one({
        "id": "cmp-test-01",
        "campaign_code": "CP-VOV-2026-TEST",
        "club_id": "club-01",
        "campaign_title": "Đồng phục CLB",
        "discount_percent": 15,
        "status": "open",
        "total_ordered": 0,
        "total_amount": 0,
        "created_at": now,
    })

    # Phụ huynh đặt 1 bộ cho võ sinh, chọn võ đường thanh toán gộp
    order_payload = {
        "student_name": "Bé Hoàng Nam",
        "parent_phone": "0934567890",
        "product_id": "prod-vov-camp",
        "sku": "VOV-CAMP-S2",
        "size": "Size 2",
        "color": "Xanh dương",
        "is_embroidered": True,
        "embroidery_name": "Hoàng Nam",
        "club_consolidated_payment": True,
    }

    res = await client.post("/api/v1/dojos/campaigns/CP-VOV-2026-TEST/orders", json=order_payload)
    assert res.status_code == 200
    data = res.json()["data"]

    # Giá sau giảm 15%: 300.000 * 85% = 255.000 VND
    assert data["price"] == 255000
    assert data["embroidery_fee"] == 30000
    assert data["total_amount"] == 285000
    assert data["payment_method"] == "CLUB_CONSOLIDATED"
    assert data["is_paid"] is False

    # Kiểm tra campaign cập nhật số lượng và tổng tiền
    camp_updated = await mock_mongo_db["club_campaigns"].find_one({"campaign_code": "CP-VOV-2026-TEST"})
    assert camp_updated["total_ordered"] == 1
    assert camp_updated["total_amount"] == 285000


@pytest.mark.asyncio
async def test_f14_campaign_orders_and_export_csv(client: AsyncClient, mock_mongo_db):
    """F14: Theo dõi danh sách đơn của đợt và xuất file CSV UTF-8 BOM."""
    now = datetime.now(timezone.utc)
    await mock_mongo_db["club_campaigns"].insert_one({
        "id": "cmp-csv-01",
        "campaign_code": "CP-CSV-EXPORT",
        "status": "open",
        "created_at": now,
    })

    # Nạp 2 đơn của học viên
    await mock_mongo_db["student_orders"].insert_many([
        {
            "campaign_id": "cmp-csv-01",
            "campaign_code": "CP-CSV-EXPORT",
            "order_code": "SO-001",
            "student_name": "Nguyễn Văn Võ",
            "parent_phone": "0901234567",
            "product_name": "Võ Phục Vovinam",
            "size": "Size 1",
            "price": 240000,
            "total_amount": 240000,
            "is_embroidered": False,
            "payment_method": "MOMO",
            "is_paid": True,
            "created_at": now,
        },
        {
            "campaign_id": "cmp-csv-01",
            "campaign_code": "CP-CSV-EXPORT",
            "order_code": "SO-002",
            "student_name": "Trần Thị Lan",
            "parent_phone": "0909888777",
            "product_name": "Võ Phục Vovinam",
            "size": "Size 2",
            "price": 270000,
            "total_amount": 270000,
            "is_embroidered": True,
            "embroidery_name": "Trần Lan",
            "payment_method": "CLUB_CONSOLIDATED",
            "is_paid": False,
            "created_at": now,
        },
    ])

    # 1. HLV xem danh sách đơn
    res_list = await client.get("/api/v1/dojos/campaigns/CP-CSV-EXPORT/orders")
    assert res_list.status_code == 200
    assert len(res_list.json()["data"]) == 2

    # 2. Xuất CSV
    res_csv = await client.get("/api/v1/dojos/campaigns/CP-CSV-EXPORT/export-csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "attachment; filename=" in res_csv.headers["content-disposition"]

    # Kiểm tra nội dung CSV
    csv_text = res_csv.content.decode("utf-8-sig")
    assert "Nguyễn Văn Võ" in csv_text
    assert "Trần Thị Lan" in csv_text
    assert "SO-001" in csv_text
    assert "SO-002" in csv_text


@pytest.mark.asyncio
async def test_f14_and_f15_close_campaign_consignment_and_deposit_flow(
    client: AsyncClient, admin_headers, mock_mongo_db
):
    """F14 & F15: Đóng đợt gom lô chung, võ đường đặt cọc 50% qua MoMo và thanh toán 50% còn lại khi giao."""
    now = datetime.now(timezone.utc)
    await mock_mongo_db["clubs"].insert_one({
        "id": "club-02",
        "club_name": "Võ Đường Taekwondo Bạch Đằng",
        "address": "78 Bạch Đằng, Bình Thạnh, TP.HCM",
        "coach_name": "Lê Tuấn",
    })

    # Tổng giá trị các đơn trong đợt = 10.000.000 VND
    await mock_mongo_db["club_campaigns"].insert_one({
        "id": "cmp-close-01",
        "campaign_code": "CP-CLOSE-TEST",
        "club_id": "club-02",
        "total_ordered": 40,
        "total_amount": 10000000,
        "status": "open",
        "deposit_paid": False,
        "created_at": now,
    })

    # 1. Đóng đợt và gom thành 1 lô giao chung về võ đường (F14)
    res_close = await client.post("/api/v1/dojos/campaigns/CP-CLOSE-TEST/close")
    assert res_close.status_code == 200
    close_data = res_close.json()["data"]
    assert close_data["status"] == "closed"
    assert close_data["deposit_amount"] == 5000000  # 50% của 10 triệu
    assert "batch_tracking" in close_data

    # 2. Võ đường tạo yêu cầu đặt cọc 50% qua MoMo (F15)
    res_dep_momo = await client.post("/api/v1/dojos/campaigns/CP-CLOSE-TEST/deposit-momo")
    assert res_dep_momo.status_code == 200
    dep_momo_data = res_dep_momo.json()["data"]
    assert dep_momo_data["deposit_amount"] == 5000000
    assert "pay_url" in dep_momo_data

    # 3. Xác nhận đặt cọc thành công
    res_confirm_dep = await client.post("/api/v1/dojos/campaigns/CP-CLOSE-TEST/confirm-deposit")
    assert res_confirm_dep.status_code == 200
    assert res_confirm_dep.json()["data"]["deposit_paid"] is True

    # 4. Quản trị viên/Nhân viên giao lô hàng tới võ đường và ghi nhận thanh toán 50% còn lại
    res_final = await client.post(
        "/api/v1/dojos/campaigns/CP-CLOSE-TEST/record-final-payment",
        headers=admin_headers,
    )
    assert res_final.status_code == 200
    assert res_final.json()["data"]["status"] == "delivered"
    assert res_final.json()["data"]["remaining_amount_paid"] is True
