from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "VÕ - Nền tảng TMĐT Võ phục & Phụ kiện"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

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

    # Security Policies (Mục 9)
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
