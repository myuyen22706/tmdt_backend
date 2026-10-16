from typing import Optional, List
from fastapi import Header, HTTPException, status, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_db
from app.core.security import decode_token


async def get_current_user_token(
    authorization: Optional[str] = Header(None),
) -> Optional[dict]:
    """Dependency trích xuất và xác minh JWT token từ header Authorization."""
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


async def get_current_user(
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    """Dependency lấy thông tin User hiện tại từ database MongoDB."""
    if not token_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu đăng nhập để tiếp tục",
        )
    user_id = token_payload.get("sub")
    user = await db["users"].find_one({"id": user_id})
    if not user:
        # Thử tìm theo phone nếu sub là số điện thoại
        user = await db["users"].find_one({"phone": user_id})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Người dùng không tồn tại trong hệ thống",
        )
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa",
        )
    return user


def require_role(allowed_roles: List[str]):
    """Kiểm tra quyền truy cập dựa trên vai trò người dùng (RBAC)."""
    async def role_checker(
        token_payload: Optional[dict] = Depends(get_current_user_token)
    ) -> dict:
        if not token_payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Cần đăng nhập để thực hiện hành động này",
            )
        user_role = token_payload.get("role", "customer")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Không có quyền truy cập. Vai trò yêu cầu: {allowed_roles}",
            )
        return token_payload

    return role_checker
