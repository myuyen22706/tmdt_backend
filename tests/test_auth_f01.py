import pytest
from httpx import AsyncClient
from app.core.config import settings


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """F01: Đăng ký tài khoản khách hàng thành công."""
    payload = {
        "phone": "0912345678",
        "full_name": "Nguyễn Văn Võ",
        "password": "Password123@",
        "email": "vanvo@example.com",
        "role": "customer",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "access_token" in data["data"]
    assert data["data"]["full_name"] == "Nguyễn Văn Võ"
    assert data["data"]["role"] == "customer"


@pytest.mark.asyncio
async def test_register_duplicate_phone(client: AsyncClient):
    """F01: Chặn đăng ký khi số điện thoại đã tồn tại."""
    payload = {
        "phone": "0988888888",
        "full_name": "Lê Văn Đai",
        "password": "Password123@",
        "email": "dai@example.com",
    }
    # Lần 1 thành công
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 200

    # Lần 2 bị từ chối
    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert "đã được đăng ký" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    """Mục 9: Bắt buộc mật khẩu tối thiểu 8 ký tự."""
    payload = {
        "phone": "0977777777",
        "full_name": "Trần Thị Bé",
        "password": "123",  # Quá ngắn
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_login_success_and_me(client: AsyncClient):
    """F01: Đăng nhập thành công và truy vấn thông tin tài khoản /me."""
    register_payload = {
        "phone": "0901234567",
        "full_name": "Võ Sĩ Vovinam",
        "password": "Mypassword123",
        "email": "vovinam@example.com",
    }
    await client.post("/api/v1/auth/register", json=register_payload)

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"phone": "0901234567", "password": "Mypassword123"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["data"]["access_token"]

    # Gọi endpoint /me
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()["data"]
    assert me_data["phone"] == "0901234567"
    assert me_data["full_name"] == "Võ Sĩ Vovinam"


@pytest.mark.asyncio
async def test_login_failed_lockout_after_5_attempts(client: AsyncClient):
    """Mục 9: Khóa tạm sau 5 lần đăng nhập sai trong 15 phút."""
    phone = "0933333333"
    register_payload = {
        "phone": phone,
        "full_name": "Người Thử Nghiệm",
        "password": "CorrectPassword123",
    }
    await client.post("/api/v1/auth/register", json=register_payload)

    # 4 lần đầu nhập sai: trả về 401
    for i in range(1, 5):
        res = await client.post(
            "/api/v1/auth/login",
            json={"phone": phone, "password": "WrongPassword"},
        )
        assert res.status_code == 401
        assert "lần thử" in res.json()["detail"]

    # Lần thứ 5 nhập sai: tài khoản bị khóa 15 phút
    res_lock = await client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "password": "WrongPassword"},
    )
    assert res_lock.status_code == 400
    assert "tạm khóa" in res_lock.json()["detail"]

    # Ngay cả khi lần thứ 6 nhập đúng mật khẩu, vẫn bị từ chối vì đang bị khóa
    res_correct_while_locked = await client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "password": "CorrectPassword123"},
    )
    assert res_correct_while_locked.status_code == 400
    assert "tạm khóa" in res_correct_while_locked.json()["detail"]


@pytest.mark.asyncio
async def test_forgot_and_reset_password_flow(client: AsyncClient, monkeypatch):
    """F01: Quên mật khẩu in console và đặt lại mật khẩu mới."""
    phone = "0944444444"
    email = "quenmatkhau@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "phone": phone,
            "full_name": "Võ Sinh Taekwondo",
            "password": "OldPassword123",
            "email": email,
        },
    )

    # Yêu cầu quên mật khẩu (dev_token chỉ trả về khi DEBUG=True)
    monkeypatch.setattr(settings, "DEBUG", True)
    forgot_res = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": email},
    )
    assert forgot_res.status_code == 200
    dev_token = forgot_res.json()["data"]["dev_token"]
    assert dev_token is not None

    # Đặt lại mật khẩu mới
    reset_res = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": dev_token, "new_password": "BrandNewPassword456"},
    )
    assert reset_res.status_code == 200

    # Đăng nhập bằng mật khẩu cũ phải thất bại
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "password": "OldPassword123"},
    )
    assert old_login.status_code == 401

    # Đăng nhập bằng mật khẩu mới phải thành công
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "password": "BrandNewPassword456"},
    )
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()["data"]


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    """F01: Đăng xuất."""
    res = await client.post("/api/v1/auth/logout")
    assert res.status_code == 200
    assert res.json()["data"]["logged_out"] is True
