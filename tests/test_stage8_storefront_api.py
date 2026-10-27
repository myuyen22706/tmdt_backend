from datetime import datetime, timezone
import pytest
from httpx import AsyncClient


def _product(pid: str, sku: str, price: int, stock: int = 10, **extra) -> dict:
    doc = {
        "id": pid,
        "name": f"Sản phẩm {pid}",
        "slug": pid,
        "martial_art_id": "vovinam",
        "category_id": "vo_phuc",
        "price": price,
        "is_customizable": True,
        "is_active": True,
        "rating": 4.8,
        "review_count": 10,
        "discount_percent": 0,
        "variants": [{"sku": sku, "size": "Size 1", "color": "Xanh", "price": price, "stock": stock}],
        "created_at": datetime.now(timezone.utc),
    }
    doc.update(extra)
    return doc


SHIPPING = {
    "recipient_name": "Lê Thị Hạnh",
    "phone": "0903111222",
    "street_address": "18 Nguyễn Trãi",
    "city_province": "Hồ Chí Minh",
}


@pytest.mark.asyncio
async def test_order_ignores_client_price_and_uses_db_price(client: AsyncClient, mock_mongo_db):
    """Đặt hàng: đơn giá và tên sản phẩm luôn lấy từ CSDL, giá client sửa tay bị bỏ qua."""
    await mock_mongo_db["products"].insert_one(_product("prod-price", "PRICE-S1", 250000))

    res = await client.post("/api/v1/orders", json={
        "shipping_address": SHIPPING,
        "payment_method": "COD",
        "items": [{"product_id": "prod-price", "sku": "PRICE-S1", "price": 1000, "product_name": "Giả mạo", "quantity": 2}],
    })
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["subtotal"] == 500000
    assert data["items"][0]["price"] == 250000
    assert data["items"][0]["product_name"] == "Sản phẩm prod-price"
    assert data["shipping_fee"] == 0  # Freeship từ 500.000₫
    assert data["total_amount"] == 500000


@pytest.mark.asyncio
async def test_order_rejects_unknown_sku(client: AsyncClient, mock_mongo_db):
    await mock_mongo_db["products"].insert_one(_product("prod-sku", "SKU-S1", 200000))
    res = await client.post("/api/v1/orders", json={
        "shipping_address": SHIPPING,
        "payment_method": "COD",
        "items": [{"product_id": "prod-sku", "sku": "KHONG-CO", "quantity": 1}],
    })
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_order_applies_voucher_server_side(client: AsyncClient, mock_mongo_db):
    """Mã giảm giá được kiểm tra và trừ tiền phía máy chủ, tăng số lượt đã dùng."""
    await mock_mongo_db["products"].insert_one(_product("prod-vou", "VOU-S1", 300000))
    await mock_mongo_db["vouchers"].insert_one({
        "id": "vouc-test", "code": "VOVINAM10", "discount_type": "PERCENT", "discount_value": 10,
        "min_order_amount": 300000, "usage_limit": 1, "used_count": 0, "is_active": True,
    })

    payload = {
        "shipping_address": SHIPPING,
        "payment_method": "COD",
        "voucher_code": "vovinam10",
        "items": [{"product_id": "prod-vou", "sku": "VOU-S1", "quantity": 1}],
    }
    res = await client.post("/api/v1/orders", json=payload)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["discount_amount"] == 30000
    assert data["voucher_code"] == "VOVINAM10"
    assert data["total_amount"] == data["subtotal"] + data["shipping_fee"] - 30000  # tiền hàng + ship - giảm giá

    voucher = await mock_mongo_db["vouchers"].find_one({"id": "vouc-test"})
    assert voucher["used_count"] == 1

    # Hết lượt sử dụng -> từ chối
    res_again = await client.post("/api/v1/orders", json=payload)
    assert res_again.status_code == 400
    assert "hết lượt" in res_again.json()["detail"]


@pytest.mark.asyncio
async def test_order_voucher_min_amount(client: AsyncClient, mock_mongo_db):
    await mock_mongo_db["products"].insert_one(_product("prod-min", "MIN-S1", 100000))
    await mock_mongo_db["vouchers"].insert_one({
        "id": "vouc-min", "code": "TANBINH20", "discount_type": "FIXED", "discount_value": 20000,
        "min_order_amount": 200000, "usage_limit": 100, "used_count": 0, "is_active": True,
    })
    res = await client.post("/api/v1/orders", json={
        "shipping_address": SHIPPING,
        "payment_method": "COD",
        "voucher_code": "TANBINH20",
        "items": [{"product_id": "prod-min", "sku": "MIN-S1", "quantity": 1}],
    })
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_catalog_facets_and_sorting(client: AsyncClient, mock_mongo_db):
    await mock_mongo_db["martial_arts"].insert_many([
        {"id": "vovinam", "name": "Vovinam"},
        {"id": "karate", "name": "Karatedo"},
    ])
    await mock_mongo_db["categories"].insert_many([
        {"id": "vo_phuc", "name": "Võ phục"},
        {"id": "dai", "name": "Đai"},
    ])
    await mock_mongo_db["products"].insert_many([
        _product("p1", "P1", 240000, discount_percent=14, review_count=5),
        _product("p2", "P2", 45000, category_id="dai", discount_percent=25, review_count=50),
        _product("p3", "P3", 460000, martial_art_id="karate", discount_percent=16, review_count=20),
        _product("p4", "P4", 99000, is_active=False),
    ])

    res = await client.get("/api/v1/products/meta/facets")
    assert res.status_code == 200
    facets = res.json()["data"]
    assert facets["total"] == 3
    counts = {m["id"]: m["count"] for m in facets["martial_arts"]}
    assert counts == {"vovinam": 2, "karate": 1}
    assert {c["id"]: c["count"] for c in facets["categories"]} == {"vo_phuc": 2, "dai": 1}
    assert facets["price_min"] == 45000 and facets["price_max"] == 460000
    assert "max-age" in res.headers.get("cache-control", "")

    res_discount = await client.get("/api/v1/products?sort_by=discount")
    assert [p["id"] for p in res_discount.json()["data"]["items"]] == ["p2", "p3", "p1"]

    res_popular = await client.get("/api/v1/products?sort_by=popular&exclude_id=p2")
    assert [p["id"] for p in res_popular.json()["data"]["items"]] == ["p3", "p1"]


@pytest.mark.asyncio
async def test_blog_detail_by_slug(client: AsyncClient, mock_mongo_db):
    await mock_mongo_db["blog_posts"].insert_many([
        {"id": "post-a", "slug": "cach-that-dai", "title": "Cách thắt đai", "content": "Nội dung", "is_published": True},
        {"id": "post-b", "slug": "nhap", "title": "Bản nháp", "content": "", "is_published": False},
    ])
    res = await client.get("/api/v1/blog/cach-that-dai")
    assert res.status_code == 200
    assert res.json()["data"]["title"] == "Cách thắt đai"

    assert (await client.get("/api/v1/blog/nhap")).status_code == 404
    listing = (await client.get("/api/v1/blog")).json()["data"]
    assert [p["slug"] for p in listing] == ["cach-that-dai"]


@pytest.mark.asyncio
async def test_cart_targets_embroidered_line(client: AsyncClient, mock_mongo_db):
    """Hai dòng cùng SKU nhưng khác tên thêu: sửa/xóa đúng dòng được chỉ định."""
    await mock_mongo_db["products"].insert_one(_product("prod-line", "LINE-S1", 200000, stock=5))
    headers = {"X-Session-ID": "sess-line"}

    await client.post("/api/v1/cart/items", headers=headers, json={"product_id": "prod-line", "sku": "LINE-S1", "quantity": 1})
    res = await client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": "prod-line", "sku": "LINE-S1", "quantity": 1, "is_embroidered": True, "embroidery_name": "Minh Quân",
    })
    assert len(res.json()["data"]["items"]) == 2

    # Tổng hai dòng không được vượt tồn kho (5)
    res_over = await client.put("/api/v1/cart/items/LINE-S1?embroidery_name=Minh Quân", headers=headers, json={"quantity": 5})
    assert res_over.status_code == 400

    res_put = await client.put("/api/v1/cart/items/LINE-S1?embroidery_name=Minh Quân", headers=headers, json={"quantity": 3})
    items = {it["embroidery_name"]: it["quantity"] for it in res_put.json()["data"]["items"]}
    assert items == {None: 1, "Minh Quân": 3}

    res_del = await client.delete("/api/v1/cart/items/LINE-S1?embroidery_name=", headers=headers)
    remaining = res_del.json()["data"]["items"]
    assert [it["embroidery_name"] for it in remaining] == ["Minh Quân"]


@pytest.mark.asyncio
async def test_shipping_quote_matches_checkout_rules(client: AsyncClient):
    hcm = (await client.get("/api/v1/orders/shipping-quote?city_province=TP. Hồ Chí Minh&subtotal=300000")).json()["data"]
    other = (await client.get("/api/v1/orders/shipping-quote?city_province=Đà Nẵng&subtotal=300000")).json()["data"]
    free = (await client.get("/api/v1/orders/shipping-quote?city_province=Đà Nẵng&subtotal=520000")).json()["data"]
    assert hcm["shipping_fee"] == 25000
    assert other["shipping_fee"] == 40000
    assert free["shipping_fee"] == 0
    assert hcm["freeship_threshold"] == 500000


@pytest.mark.asyncio
async def test_self_register_cannot_grant_admin(client: AsyncClient, mock_mongo_db):
    res = await client.post("/api/v1/auth/register", json={
        "phone": "0977000111", "full_name": "Người Lạ", "password": "MatKhau123@", "role": "admin",
    })
    assert res.status_code == 403
    assert await mock_mongo_db["users"].find_one({"phone": "0977000111"}) is None

    res_coach = await client.post("/api/v1/auth/register", json={
        "phone": "0977000222", "full_name": "HLV Trần Minh", "password": "MatKhau123@", "role": "coach",
    })
    assert res_coach.status_code == 200
    assert res_coach.json()["data"]["phone"] == "0977000222"


@pytest.mark.asyncio
async def test_revenue_csv_link_requires_admin(client: AsyncClient):
    from app.core.security import create_access_token

    assert (await client.get("/api/v1/admin/revenue-report/csv")).status_code == 403
    admin = {"Authorization": f"Bearer {create_access_token(subject='usr-admin-01', role='admin')}"}
    assert (await client.get("/api/v1/admin/revenue-report/csv", headers=admin)).status_code == 200


@pytest.mark.asyncio
async def test_guest_order_requires_matching_phone(client: AsyncClient, mock_mongo_db):
    """Khách vãng lai chỉ xem/hủy được đơn khi nhập đúng SĐT đặt hàng (chống dò mã đơn)."""
    await mock_mongo_db["products"].insert_one(_product("prod-guest", "GUEST-S1", 150000))
    res = await client.post("/api/v1/orders", json={
        "shipping_address": SHIPPING,
        "payment_method": "COD",
        "items": [{"product_id": "prod-guest", "sku": "GUEST-S1", "quantity": 1}],
    })
    code = res.json()["data"]["order_code"]

    assert (await client.get(f"/api/v1/orders/{code}")).status_code == 401
    assert (await client.get(f"/api/v1/orders/{code}?phone=0900000000")).status_code == 403
    assert (await client.post(f"/api/v1/orders/{code}/cancel")).status_code == 401

    ok = await client.get(f"/api/v1/orders/{code}?phone=0903 111 222")
    assert ok.status_code == 200
    assert ok.json()["data"]["shipping_address_full"] == "18 Nguyễn Trãi, Hồ Chí Minh"

    cancelled = await client.post(f"/api/v1/orders/{code}/cancel?phone=0903111222")
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_active_vouchers_hide_exhausted(client: AsyncClient, mock_mongo_db):
    await mock_mongo_db["vouchers"].insert_many([
        {"id": "v1", "code": "VOVINAM10", "discount_type": "PERCENT", "discount_value": 10, "min_order_amount": 300000, "usage_limit": 100, "used_count": 3, "is_active": True},
        {"id": "v2", "code": "HETLUOT", "discount_type": "FIXED", "discount_value": 50000, "min_order_amount": 0, "usage_limit": 1, "used_count": 1, "is_active": True},
        {"id": "v3", "code": "TAT", "discount_type": "FIXED", "discount_value": 9000, "min_order_amount": 0, "is_active": False},
    ])
    data = (await client.get("/api/v1/promotions/active")).json()["data"]
    assert [v["code"] for v in data] == ["VOVINAM10"]


@pytest.mark.asyncio
async def test_order_and_password_reset_send_email(client: AsyncClient, mock_mongo_db, monkeypatch):
    """Email giao dịch (Resend): đơn có email nhận xác nhận, quên mật khẩu gửi link; dữ liệu khách được escape."""
    import importlib
    # Package có biến `router` trùng tên module, nên lấy module qua importlib
    auth_router = importlib.import_module("app.modules.auth.router")
    orders_router = importlib.import_module("app.modules.orders.router")

    sent = []

    async def fake_send(to, subject, html):
        sent.append((to, subject, html))
        return True

    monkeypatch.setattr(orders_router, "send_email", fake_send)
    monkeypatch.setattr(auth_router, "send_email", fake_send)

    await mock_mongo_db["products"].insert_one(_product("prod-mail", "MAIL-S1", 200000))
    res = await client.post("/api/v1/orders", json={
        "customer_name": "<script>x</script>An",
        "customer_email": "khach@example.com",
        "shipping_address": SHIPPING,
        "payment_method": "COD",
        "items": [{"product_id": "prod-mail", "sku": "MAIL-S1", "quantity": 1}],
    })
    assert res.status_code == 200
    code = res.json()["data"]["order_code"]
    to, subject, html = sent[-1]
    assert to == "khach@example.com" and code in subject
    assert "<script>" not in html and "&lt;script&gt;" in html

    # Đơn không có email thì không gửi
    before = len(sent)
    await client.post("/api/v1/orders", json={
        "shipping_address": SHIPPING, "payment_method": "COD",
        "items": [{"product_id": "prod-mail", "sku": "MAIL-S1", "quantity": 1}],
    })
    assert len(sent) == before

    await mock_mongo_db["users"].insert_one({"id": "usr-mail", "phone": "0911000111", "email": "user@example.com", "full_name": "Bình", "is_active": True})
    res = await client.post("/api/v1/auth/forgot-password", json={"phone": "0911000111"})
    assert res.status_code == 200
    to, subject, html = sent[-1]
    user = await mock_mongo_db["users"].find_one({"id": "usr-mail"})
    assert to == "user@example.com"
    assert f"/reset-password?token={user['reset_token']}" in html


@pytest.mark.asyncio
async def test_send_email_skips_without_key():
    """Chưa cấu hình RESEND_API_KEY thì bỏ qua, không gọi mạng, không ném lỗi."""
    from app.core.mail import send_email
    assert await send_email("a@example.com", "x", "<p>x</p>") is False


@pytest.mark.asyncio
async def test_send_email_skips_reserved_demo_domains(monkeypatch):
    """Tài khoản mẫu dùng example.com: không gọi Resend dù đã có key."""
    from app.core import mail
    from app.core.config import settings

    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test")
    assert mail.is_deliverable("khach@gmail.com")
    assert mail.is_deliverable("delivered@resend.dev")
    for addr in ("admin@example.com", "a@shop.test", "b@x.invalid", "khong-hop-le"):
        assert not mail.is_deliverable(addr)
    assert await mail.send_email("admin@example.com", "x", "<p>x</p>") is False
