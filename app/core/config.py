from typing import List, Union
import json
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "VÕ - Nền tảng TMĐT Võ phục & Phụ kiện"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    # Mặc định tắt: DEBUG=True trả token đặt lại mật khẩu trong response và cho phép bỏ qua rate limit.
    # Chỉ bật trong .env khi chạy local.
    DEBUG: bool = False

    # URLs cho Frontend & Backend (phục vụ tạo link chia sẻ, SEO, Redirect)
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    # CORS
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    BACKEND_CORS_ORIGIN_REGEX: str = r"https://.*\.vercel\.app"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return ["*"]
            if v.startswith("["):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]


    # JWT Security
    SECRET_KEY: str = "dev-insecure-secret-key-change-in-prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Database (MongoDB Atlas)
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "vo_ecommerce_atlas"
    DATABASE_URL: str = "sqlite:///./vo_ecommerce.db"  # Legacy fallback if needed

    # MoMo Payment Gateway (Mục 7)
    MOMO_MOCK: bool = True
    MOMO_PARTNER_CODE: str = "MOMOBKUN20180529"
    MOMO_ACCESS_KEY: str = "klm05TvNBzhg7hSr"
    MOMO_SECRET_KEY: str = "at67qH6mk8w5Y1nAyMoYKMWACiEi2Aca"
    MOMO_ENDPOINT: str = "https://test-payment.momo.vn/v2/gateway/api/create"
    MOMO_REDIRECT_URL: str = "http://localhost:3000/orders/payment-result"
    MOMO_IPN_URL: str = "http://localhost:8000/api/v1/payments/momo/ipn"

    # Email giao dịch qua Resend (xác nhận đơn, quên mật khẩu). Để trống thì bỏ qua gửi mail.
    RESEND_API_KEY: str = ""
    MAIL_FROM: str = "VÕ <noreply@localhost>"

    # Phí thêu tên võ sinh (F07), dùng chung cho giỏ hàng và đặt hàng
    EMBROIDERY_FEE: int = 30000

    # Cache-Control cho các endpoint catalog công khai (giây)
    PUBLIC_CACHE_MAX_AGE: int = 60

    # Security Policies (Mục 9)
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    def insecure_secret_key(self) -> bool:
        """SECRET_KEY còn là giá trị mặc định/ví dụ hoặc quá ngắn thì JWT có thể bị giả mạo."""
        return (
            len(self.SECRET_KEY) < 32
            or self.SECRET_KEY.startswith(("dev-insecure", "super-secret-key-change"))
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
