from datetime import datetime, timedelta, timezone
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


@pytest.mark.asyncio
async def test_f02_list_and_filter_products(client: AsyncClient, mock_mongo_db):
    """F02: Xem danh mục, lọc theo môn võ, khoảng giá và tìm kiếm tên."""
    now = datetime.now(timezone.utc)
    await mock_mongo_db["products"].insert_many([
        {
            "id": "prod-vov-1",
            "name": "Võ Phục Vovinam Chuẩn",
            "slug": "vo-phuc-vovinam-chuan",
            "martial_art_id": "vovinam",
            "category_id": "vo_phuc",
            "price": 250000,
            "is_active": True,
            "variants": [{"sku": "VOV-S1", "size": "Size 1", "color": "Xanh", "price": 250000, "stock": 10}],
            "created_at": now,
        },
        {
            "id": "prod-tkd-1",
            "name": "Võ Phục Taekwondo Thi Đấu",
            "slug": "vo-phuc-taekwondo-thi-dau",
            "martial_art_id": "taekwondo",
            "category_id": "vo_phuc",
            "price": 400000,
            "is_active": True,
            "variants": [{"sku": "TKD-S2", "size": "Size 2", "color": "Trắng", "price": 400000, "stock": 5}],
            "created_at": now + timedelta(minutes=1),
        },
        {
            "id": "prod-vov-dai",
            "name": "Đai Vovinam Lam Đai",
            "slug": "dai-vovinam-lam-dai",
            "martial_art_id": "vovinam",
            "category_id": "dai",
            "price": 50000,
            "is_active": True,
            "variants": [{"sku": "DAI-VOV", "size": "Freesize", "color": "Xanh", "price": 50000, "stock": 20}],
            "created_at": now + timedelta(minutes=2),
        },
    ])

    # 1. Lọc theo môn võ
    res_vov = await client.get("/api/v1/products?martial_art=vovinam")
    assert res_vov.status_code == 200
    assert res_vov.json()["data"]["total"] == 2

    # 2. Lọc theo loại sản phẩm
    res_cat = await client.get("/api/v1/products?category=dai")
    assert res_cat.status_code == 200
    assert res_cat.json()["data"]["total"] == 1

    # 3. Lọc theo khoảng giá (>= 300,000 VND)
    res_price = await client.get("/api/v1/products?min_price=300000")
    assert res_price.status_code == 200
    assert res_price.json()["data"]["total"] == 1
    assert res_price.json()["data"]["items"][0]["id"] == "prod-tkd-1"

    # 4. Tìm kiếm theo tên
    res_search = await client.get("/api/v1/products?search=Taekwondo")
    assert res_search.status_code == 200
    assert res_search.json()["data"]["total"] == 1

    # 5. Sắp xếp theo giá tăng dần
    res_sort = await client.get("/api/v1/products?sort_by=price_asc")
    assert res_sort.status_code == 200
    items = res_sort.json()["data"]["items"]
    assert items[0]["price"] <= items[1]["price"] <= items[2]["price"]


@pytest.mark.asyncio
async def test_f03_product_detail_and_size_chart(client: AsyncClient, mock_mongo_db):
    """F03: Chi tiết sản phẩm, báo còn/hết hàng và bảng size môn phái."""
    now = datetime.now(timezone.utc)
    await mock_mongo_db["products"].insert_one({
        "id": "prod-karate-test",
        "name": "Võ Phục Karate Kaki",
        "slug": "vo-phuc-karate-kaki",
        "martial_art_id": "karate",
        "category_id": "vo_phuc",
        "price": 320000,
        "is_active": True,
        "variants": [
            {"sku": "KAR-S1", "size": "Size 1", "color": "Trắng", "price": 320000, "stock": 10, "low_stock_threshold": 5},
            {"sku": "KAR-S2", "size": "Size 2", "color": "Trắng", "price": 320000, "stock": 0, "low_stock_threshold": 5},
        ],
        "created_at": now,
    })

    # Nạp 1 mốc size chart cho môn karate
    await mock_mongo_db["size_charts"].insert_one({
        "id": "chart-karate-s1",
        "martial_art_id": "karate",
        "size_name": "Size 1",
        "height_min_cm": 125,
        "height_max_cm": 135,
        "weight_min_kg": 26,
        "weight_max_kg": 35,
        "fit_note": "Trẻ 8-9 tuổi",
    })

    res = await client.get("/api/v1/products/vo-phuc-karate-kaki")
    assert res.status_code == 200
    data = res.json()["data"]

    # Kiểm tra sản phẩm
    prod = data["product"]
    assert prod["slug"] == "vo-phuc-karate-kaki"
    assert len(prod["variants"]) == 2
    assert prod["variants"][0]["in_stock"] is True
    assert prod["variants"][1]["in_stock"] is False  # Hết hàng

    # Kiểm tra bảng size đính kèm
    assert len(data["size_chart"]) >= 1
    assert data["size_chart"][0]["size"] == "Size 1"


@pytest.mark.asyncio
async def test_f04_size_advisor_logic(client: AsyncClient, mock_mongo_db):
    """F04: Tư vấn size thông minh: chuẩn mốc, nằm giữa 2 size và ngoài bảng size."""
    # Nạp bảng size chuẩn cho môn vovinam
    await mock_mongo_db["size_charts"].insert_many([
        {"id": "c1", "martial_art_id": "vovinam", "size_name": "Size 0", "height_min_cm": 115, "height_max_cm": 125, "weight_min_kg": 20, "weight_max_kg": 28},
        {"id": "c2", "martial_art_id": "vovinam", "size_name": "Size 1", "height_min_cm": 125, "height_max_cm": 135, "weight_min_kg": 26, "weight_max_kg": 35},
        {"id": "c3", "martial_art_id": "vovinam", "size_name": "Size 2", "height_min_cm": 135, "height_max_cm": 145, "weight_min_kg": 33, "weight_max_kg": 42},
    ])

    # 1. Trường hợp khớp chuẩn Size 1
    res1 = await client.post("/api/v1/size-advisor/recommend", json={
        "martial_art": "vovinam",
        "height_cm": 130,
        "weight_kg": 30,
    })
    assert res1.status_code == 200
    assert res1.json()["data"]["recommended_size"] == "Size 1"
    assert res1.json()["data"]["is_out_of_range"] is False

    # 2. Trường hợp nằm giữa hai size: Chiều cao ở Size 1 (130cm) nhưng cân nặng ở Size 2 (38kg)
    # Đặc tả F04: "Nằm giữa hai size thì gợi ý size lớn hơn kèm ghi chú"
    res2 = await client.post("/api/v1/size-advisor/recommend", json={
        "martial_art": "vovinam",
        "height_cm": 130,
        "weight_kg": 38,
    })
    assert res2.status_code == 200
    assert res2.json()["data"]["recommended_size"] == "Size 2"
    assert "size lớn hơn" in res2.json()["data"]["fit_note"]

    # 3. Trường hợp ngoài bảng size: Chiều cao quá thấp (90cm)
    res3 = await client.post("/api/v1/size-advisor/recommend", json={
        "martial_art": "vovinam",
        "height_cm": 90,
        "weight_kg": 14,
    })
    assert res3.status_code == 200
    assert res3.json()["data"]["is_out_of_range"] is True
    assert res3.json()["data"]["recommended_size"] == "Size 0"


@pytest.mark.asyncio
async def test_f05_student_profiles_and_6_months_alert(client: AsyncClient, customer_headers, mock_mongo_db):
    """F05: Quản lý hồ sơ size: thêm, sửa, xóa và cảnh báo nhắc đo lại sau 6 tháng."""
    # Tạo user trong database
    await mock_mongo_db["users"].insert_one({
        "id": "usr-cust-01",
        "phone": "0909000003",
        "full_name": "Phụ Huynh Nam",
        "role": "customer",
        "is_active": True,
    })

    # 1. Thêm hồ sơ con 1
    create_res = await client.post(
        "/api/v1/size-advisor/profiles",
        headers=customer_headers,
        json={
            "student_name": "Bé Nam",
            "birth_year": 2018,
            "martial_art": "vovinam",
            "height_cm": 120,
            "weight_kg": 22,
            "recommended_size": "Size 0",
        },
    )
    assert create_res.status_code == 200
    prof_id = create_res.json()["data"]["id"]

    # 2. Truy vấn danh sách hồ sơ (mới tạo -> chưa cần nhắc đo lại)
    list_res = await client.get("/api/v1/size-advisor/profiles", headers=customer_headers)
    assert list_res.status_code == 200
    profiles = list_res.json()["data"]
    assert len(profiles) == 1
    assert profiles[0]["needs_remeasure"] is False

    # 3. Giả lập hồ sơ đã đo cách đây 200 ngày (> 180 ngày / 6 tháng)
    past_date = datetime.now(timezone.utc) - timedelta(days=200)
    await mock_mongo_db["student_profiles"].update_one(
        {"id": prof_id},
        {"$set": {"measured_date": past_date}}
    )

    # Truy vấn lại: phải xuất hiện cảnh báo nhắc đo lại
    list_res_old = await client.get("/api/v1/size-advisor/profiles", headers=customer_headers)
    old_prof = list_res_old.json()["data"][0]
    assert old_prof["needs_remeasure"] is True
    assert "quá 6 tháng" in old_prof["remeasure_alert"]

    # 4. Cập nhật hồ sơ (đo lại số đo mới)
    update_res = await client.put(
        f"/api/v1/size-advisor/profiles/{prof_id}",
        headers=customer_headers,
        json={"height_cm": 128, "weight_kg": 27},
    )
    assert update_res.status_code == 200

    # Sau khi cập nhật, cờ needs_remeasure phải trở về False
    list_res_updated = await client.get("/api/v1/size-advisor/profiles", headers=customer_headers)
    assert list_res_updated.json()["data"][0]["needs_remeasure"] is False
    assert list_res_updated.json()["data"][0]["height_cm"] == 128

    # 5. Khách xóa hồ sơ
    del_res = await client.delete(f"/api/v1/size-advisor/profiles/{prof_id}", headers=customer_headers)
    assert del_res.status_code == 200

    # Danh sách trống
    list_res_empty = await client.get("/api/v1/size-advisor/profiles", headers=customer_headers)
    assert len(list_res_empty.json()["data"]) == 0


@pytest.mark.asyncio
async def test_f16_admin_product_management_and_rbac(client: AsyncClient, admin_headers, customer_headers):
    """F16: Quản lý sản phẩm (CRUD) dành cho Admin/Staff; chặn Customer (403)."""
    payload = {
        "name": "Võ Phục Mới Thử Nghiệm",
        "slug": "vo-phuc-moi-thu-nghiem",
        "martial_art_id": "vovinam",
        "category_id": "vo_phuc",
        "price": 280000,
        "thumbnail": "/thumb.jpg",
        "material": "Kaki Cotton",
        "description": "Mô tả thử nghiệm",
        "is_customizable": True,
        "variants": [{"sku": "TEST-S1", "size": "Size 1", "color": "Trắng", "price": 280000, "stock": 10}],
    }

    # 1. Customer cố tình tạo sản phẩm -> 403 Forbidden
    res_denied = await client.post("/api/v1/products", headers=customer_headers, json=payload)
    assert res_denied.status_code == 403

    # 2. Admin tạo sản phẩm -> 200 OK
    res_admin = await client.post("/api/v1/products", headers=admin_headers, json=payload)
    assert res_admin.status_code == 200
    prod_id = res_admin.json()["data"]["id"]

    # 3. Admin cập nhật giá sản phẩm
    res_update = await client.put(
        f"/api/v1/products/{prod_id}",
        headers=admin_headers,
        json={"price": 310000},
    )
    assert res_update.status_code == 200
    assert res_update.json()["data"]["price"] == 310000

    # 4. Admin xóa sản phẩm
    res_delete = await client.delete(f"/api/v1/products/{prod_id}", headers=admin_headers)
    assert res_delete.status_code == 200
