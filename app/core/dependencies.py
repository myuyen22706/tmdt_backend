from typing import Optional
from fastapi import Header, HTTPException, status
from app.core.security import decode_token


async def get_current_user_token(
    authorization: Optional[str] = Header(None),
) -> Optional[dict]:
    """Dependency to extract and verify JWT token from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
        )
    return payload


def require_role(allowed_roles: list[str]):
    """Role-based access control dependency."""
    async def role_checker(token_payload: Optional[dict] = Header(None)) -> dict:
        if not token_payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Cần đăng nhập để thực hiện hành động này",
            )
        user_role = token_payload.get("role", "customer")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền truy cập",
            )
        return token_payload

    return role_checker
