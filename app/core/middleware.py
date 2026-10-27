import time
from collections import defaultdict
from typing import Dict, List, Tuple
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Mục 9: Thêm các Security Headers theo tiêu chuẩn OWASP để phòng chống Clickjacking, MIME-sniffing, XSS."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # 1. Ngăn trình duyệt tự ý đoán định dạng MIME (MIME-type sniffing)
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 2. Ngăn website bị nhúng vào iframe (Chống tấn công Clickjacking)
        response.headers["X-Frame-Options"] = "DENY"

        # 3. Kích hoạt bộ lọc XSS sẵn có của trình duyệt
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 4. Ép buộc giao tiếp qua kết nối bảo mật HTTPS (HSTS)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # 5. Chính sách bảo mật nội dung (CSP)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:;"
        )

        # 6. Kiểm soát thông tin Referrer khi chuyển hướng
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 7. Giới hạn các tính năng phần cứng nhạy cảm
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Mục 9: Giới hạn tần suất yêu cầu (Rate Limiting) để phòng chống tấn công từ chối dịch vụ (DDoS) và Brute-force mật khẩu.
    - Sliding window 60 giây theo IP client.
    - Cấu hình nghiêm ngặt hơn cho các endpoint nhạy cảm (/auth/login, /auth/register, /auth/forgot-password).
    """

    ip_request_history: Dict[str, List[float]] = defaultdict(list)
    auth_request_history: Dict[str, List[float]] = defaultdict(list)

    @classmethod
    def reset(cls):
        """Reset bộ đếm rate limit (dùng cho cô lập môi trường test giữa các test cases)."""
        cls.ip_request_history.clear()
        cls.auth_request_history.clear()

    def __init__(self, app, requests_per_minute: int = 120, auth_requests_per_minute: int = 15):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.auth_requests_per_minute = auth_requests_per_minute

    def _cleanup_old_requests(self, history: List[float], window_seconds: float = 60.0) -> List[float]:
        now = time.time()
        return [ts for ts in history if now - ts < window_seconds]

    async def dispatch(self, request: Request, call_next) -> Response:
        # Bỏ qua rate limit cho OPTIONS (preflight CORS) và khi có cờ test
        if request.method == "OPTIONS":
            return await call_next(request)

        # Cờ bỏ qua chỉ dành cho môi trường phát triển; production ai cũng gửi được header này
        if settings.DEBUG and request.headers.get("X-Bypass-Rate-Limit") == "true":
            return await call_next(request)

        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        path = request.url.path

        # Kiểm tra endpoint xác thực nhạy cảm
        is_sensitive_auth = any(
            p in path for p in ["/auth/login", "/auth/register", "/auth/forgot-password", "/auth/reset-password"]
        )

        if is_sensitive_auth:
            history = self._cleanup_old_requests(self.auth_request_history[client_ip])
            if len(history) >= self.auth_requests_per_minute:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "success": False,
                        "message": "Quá nhiều yêu cầu xác thực trong thời gian ngắn. Vui lòng thử lại sau 1 phút.",
                        "error_code": "AUTH_RATE_LIMIT_EXCEEDED",
                    },
                    headers={"Retry-After": "60"},
                )
            history.append(now)
            self.auth_request_history[client_ip] = history

        # Kiểm tra rate limit chung cho toàn bộ API
        general_history = self._cleanup_old_requests(self.ip_request_history[client_ip])
        if len(general_history) >= self.requests_per_minute:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "message": "Bạn đã gửi quá nhiều yêu cầu. Vui lòng chờ giây lát.",
                    "error_code": "GENERAL_RATE_LIMIT_EXCEEDED",
                },
                headers={"Retry-After": "60"},
            )
        general_history.append(now)
        self.ip_request_history[client_ip] = general_history

        response = await call_next(request)
        return response
