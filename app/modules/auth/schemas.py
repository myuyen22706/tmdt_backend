from typing import Optional
from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    phone: str
    full_name: str
    password: str
    email: Optional[EmailStr] = None
    role: str = "customer"  # customer, coach, admin


class UserLogin(BaseModel):
    phone: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str
    role: str
