from fastapi import APIRouter, HTTPException, status
from app.core.responses import APIResponse
from app.core.security import create_access_token
from app.modules.auth.schemas import TokenResponse, UserLogin, UserRegister

router = APIRouter(prefix="/auth", tags=["Authentication & Accounts"])


@router.post("/register", response_model=APIResponse[TokenResponse])
async def register(user: UserRegister):
    """Đăng ký tài khoản (khách hàng hoặc HLV võ đường)."""
    token = create_access_token(subject=user.phone, role=user.role)
    return APIResponse(
        success=True,
        message="Đăng ký tài khoản thành công",
        data=TokenResponse(
            access_token=token,
            user_id="usr-" + user.phone[-4:],
            full_name=user.full_name,
            role=user.role,
        ),
    )


@router.post("/login", response_model=APIResponse[TokenResponse])
async def login(credentials: UserLogin):
    """Đăng nhập bằng số điện thoại / mật khẩu."""
    # For demo purposes, allow demo accounts
    role = "admin" if credentials.phone == "0999999999" else "customer"
    name = "Quản trị viên" if role == "admin" else "Võ sinh Demo"

    token = create_access_token(subject=credentials.phone, role=role)
    return APIResponse(
        success=True,
        message="Đăng nhập thành công",
        data=TokenResponse(
            access_token=token,
            user_id="usr-demo",
            full_name=name,
            role=role,
        ),
    )
