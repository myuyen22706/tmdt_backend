from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    phone: str = Field(..., min_length=9, max_length=15, description="Số điện thoại")
    full_name: str = Field(..., min_length=2, max_length=100, description="Họ và tên")
    password: str = Field(..., min_length=8, description="Mật khẩu tối thiểu 8 ký tự (Mục 9)")
    email: Optional[EmailStr] = None
    role: str = Field(default="customer", description="Vai trò: customer, coach, staff, admin")


class UserLogin(BaseModel):
    phone: str = Field(..., description="Số điện thoại hoặc Email đăng nhập")
    password: str = Field(..., description="Mật khẩu")


class ForgotPasswordRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Mã xác nhận hoặc token đặt lại mật khẩu")
    new_password: str = Field(..., min_length=8, description="Mật khẩu mới tối thiểu 8 ký tự")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str
    role: str
    phone: Optional[str] = None
    email: Optional[str] = None
