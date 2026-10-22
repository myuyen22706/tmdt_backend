import html
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Mục 9: Băm mật khẩu bằng thuật toán bcrypt an toàn."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Mục 9: Xác thực mật khẩu đã băm."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str,
    role: str = "customer",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Tạo JWT access token có thời hạn."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"sub": str(subject), "role": role, "exp": expire}
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """Giải mã và xác thực JWT token."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except Exception:
        return None


# ==============================================================================
# Mục 9: Phòng chống XSS & NoSQL Injection & Che giấu Dữ liệu nhạy cảm
# ==============================================================================

def sanitize_html(text: Optional[str]) -> Optional[str]:
    """Mục 9: Phòng chống XSS bằng cách khử hoặc mã hóa các thẻ/ký tự HTML độc hại."""
    if not text:
        return text

    # 1. Loại bỏ các khối thẻ script và iframe hoàn toàn
    clean_text = re.sub(r"<(script|iframe|style|object|embed)[^>]*>.*?</\1>", "", text, flags=re.IGNORECASE | re.DOTALL)
    clean_text = re.sub(r"<(script|iframe|style|object|embed)[^>]*>", "", clean_text, flags=re.IGNORECASE)

    # 2. Loại bỏ các thuộc tính bắt sự kiện (onerror=, onload=, onclick=...)
    clean_text = re.sub(r"\bon\w+\s*=\s*['\"][^'\"]*['\"]", "", clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r"\bon\w+\s*=\s*[^\s>]+", "", clean_text, flags=re.IGNORECASE)

    # 3. Loại bỏ pseudo-protocols nguy hiểm (javascript:, vbscript:, data:text/html)
    clean_text = re.sub(r"javascript:\s*", "", clean_text, flags=re.IGNORECASE)
    clean_text = re.sub(r"vbscript:\s*", "", clean_text, flags=re.IGNORECASE)

    # 4. Escape các ký tự đặc biệt còn lại
    return html.escape(clean_text)


def sanitize_nosql_input(value: Union[str, Any]) -> Union[str, Any]:
    """Mục 9: Phòng chống NoSQL Injection:
    - Loại bỏ ký tự bắt đầu bằng '$' ngăn chặn toán tử MongoDB Injection ($where, $gt, $ne, $regex...).
    - Escape các ký tự đặc biệt nếu là chuỗi tìm kiếm text/regex.
    """
    if not isinstance(value, str):
        return value

    # Loại bỏ null bytes
    val = value.replace("\x00", "")

    # Ngăn chặn cú pháp toán tử MongoDB ở đầu từ
    val = re.sub(r"^\$+", "", val)

    # Escape các ký tự đặc biệt của biểu thức chính quy (Regex injection)
    return re.escape(val)


def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mục 9: Che giấu các trường thông tin nhạy cảm trước khi log hoặc phản hồi."""
    sensitive_keys = {
        "password",
        "hashed_password",
        "secret_key",
        "access_token",
        "token",
        "card_number",
        "signature",
    }
    masked = {}
    for k, v in data.items():
        if k.lower() in sensitive_keys:
            masked[k] = "***MASKED***"
        elif isinstance(v, dict):
            masked[k] = mask_sensitive_data(v)
        else:
            masked[k] = v
    return masked
