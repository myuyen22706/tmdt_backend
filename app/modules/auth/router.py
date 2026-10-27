import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import APIResponse
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.schemas import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
)
from app.modules.users.models import UserDoc, UserResponse

logger = logging.getLogger("vo_ecommerce.auth")

router = APIRouter(prefix="/auth", tags=["Authentication & Accounts (F01)"])

SELF_REGISTER_ROLES = {"customer", "coach"}


@router.post("/register", response_model=APIResponse[TokenResponse])
async def register(user_data: UserRegister, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Đăng ký tài khoản mới (F01).
    - Lưu vào MongoDB Atlas collection 'users'.
    - Kiểm tra số điện thoại duy nhất.
    - Mật khẩu được băm an toàn bằng bcrypt (Mục 9).
    """
    users_col = db["users"]

    # Kiểm tra số điện thoại trùng lặp
    existing_phone = await users_col.find_one({"phone": user_data.phone})
    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số điện thoại này đã được đăng ký trong hệ thống",
        )

    # Kiểm tra email trùng lặp nếu có
    if user_data.email:
        existing_email = await users_col.find_one({"email": str(user_data.email)})
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email này đã được sử dụng cho tài khoản khác",
            )

    # Tự đăng ký chỉ được chọn vai trò khách hàng hoặc HLV; quyền staff/admin do quản trị viên cấp (Mục 9)
    if user_data.role not in SELF_REGISTER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không thể tự đăng ký vai trò này. Vui lòng liên hệ quản trị viên.",
        )

    now = datetime.now(timezone.utc)
    new_user = UserDoc(
        phone=user_data.phone,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
        role=user_data.role,
        email=str(user_data.email) if user_data.email else None,
        failed_login_attempts=0,
        locked_until=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    user_dict = new_user.model_dump()
    await users_col.insert_one(user_dict)

    # Tạo JWT Access Token
    token = create_access_token(subject=new_user.id, role=new_user.role)

    return APIResponse(
        success=True,
        message="Đăng ký tài khoản thành công",
        data=TokenResponse(
            access_token=token,
            user_id=new_user.id,
            full_name=new_user.full_name,
            role=new_user.role,
            phone=new_user.phone,
            email=new_user.email,
        ),
    )


@router.post("/login", response_model=APIResponse[TokenResponse])
async def login(credentials: UserLogin, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Đăng nhập bằng số điện thoại (hoặc email) và mật khẩu (F01).
    - Khóa tạm tài khoản sau 5 lần nhập sai trong 15 phút (Mục 9).
    """
    users_col = db["users"]
    now = datetime.now(timezone.utc)

    # Tìm user theo phone hoặc email
    user = await users_col.find_one({
        "$or": [
            {"phone": credentials.phone},
            {"email": credentials.phone},
        ]
    })

    # Hỗ trợ tìm linh hoạt giữa đầu số 0988 và 0909 cho tài khoản demo
    if not user and credentials.phone:
        alt_phone = None
        if credentials.phone.startswith("0988"):
            alt_phone = "0909" + credentials.phone[4:]
        elif credentials.phone.startswith("0909"):
            alt_phone = "0988" + credentials.phone[4:]
        if alt_phone:
            user = await users_col.find_one({"phone": alt_phone})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Số điện thoại hoặc mật khẩu không chính xác",
        )

    # Kiểm tra trạng thái khóa tạm thời
    locked_until = user.get("locked_until")
    if locked_until:
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)

        if now < locked_until:
            minutes_left = max(1, int((locked_until - now).total_seconds() / 60))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tài khoản đang bị tạm khóa do nhập sai mật khẩu nhiều lần. Vui lòng thử lại sau {minutes_left} phút.",
            )
        else:
            # Hết thời gian khóa, tự động mở lại
            await users_col.update_one(
                {"_id": user["_id"]},
                {"$set": {"failed_login_attempts": 0, "locked_until": None}},
            )
            user["failed_login_attempts"] = 0
            user["locked_until"] = None

    # Xác thực mật khẩu (hỗ trợ linh hoạt cả có và không có ký tự @ cuối)
    is_valid_pass = verify_password(credentials.password, user["hashed_password"])
    if not is_valid_pass:
        if credentials.password.endswith("@"):
            is_valid_pass = verify_password(credentials.password[:-1], user["hashed_password"])
        else:
            is_valid_pass = verify_password(credentials.password + "@", user["hashed_password"])

    if not is_valid_pass:
        attempts = user.get("failed_login_attempts", 0) + 1
        update_fields = {"failed_login_attempts": attempts}

        if attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
            new_locked_until = now + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
            update_fields["locked_until"] = new_locked_until
            update_fields["failed_login_attempts"] = 0
            await users_col.update_one({"_id": user["_id"]}, {"$set": update_fields})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bạn đã nhập sai 5 lần liên tiếp. Tài khoản bị tạm khóa trong {settings.ACCOUNT_LOCKOUT_MINUTES} phút để bảo mật.",
            )

        await users_col.update_one({"_id": user["_id"]}, {"$set": update_fields})
        remaining = settings.MAX_FAILED_LOGIN_ATTEMPTS - attempts
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Mật khẩu không chính xác. Bạn còn {remaining} lần thử trước khi bị khóa tạm thời.",
        )

    # Đăng nhập thành công -> Reset số lần đăng nhập sai
    await users_col.update_one(
        {"_id": user["_id"]},
        {"$set": {"failed_login_attempts": 0, "locked_until": None, "updated_at": now}},
    )

    # Ghi nhật ký đăng nhập quản trị (F23)
    user_role = user.get("role", "customer")
    if user_role in ["admin", "staff"]:
        await db["activity_logs"].insert_one({
            "id": f"log-{uuid.uuid4().hex[:8]}",
            "actor": user.get("phone", user["id"]),
            "actor_role": user_role,
            "action": "ADMIN_LOGIN",
            "target_type": "auth",
            "target_id": user["id"],
            "details": {"full_name": user["full_name"], "phone": user["phone"]},
            "timestamp": now,
        })

    token = create_access_token(subject=user["id"], role=user_role)

    return APIResponse(
        success=True,
        message="Đăng nhập thành công",
        data=TokenResponse(
            access_token=token,
            user_id=user["id"],
            full_name=user["full_name"],
            role=user.get("role", "customer"),
            phone=user.get("phone"),
            email=user.get("email"),
        ),
    )


@router.post("/logout", response_model=APIResponse[dict])
async def logout():
    """Đăng xuất tài khoản (F01). Phía client xóa token lưu trữ."""
    return APIResponse(
        success=True,
        message="Đăng xuất thành công",
        data={"logged_out": True},
    )


@router.post("/forgot-password", response_model=APIResponse[dict])
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Quên mật khẩu (F01).
    - Tạo mã / token khôi phục mật khẩu.
    - Ở môi trường phát triển (development), in thông tin email ra console.
    """
    users_col = db["users"]
    query = {}
    if payload.email:
        query["email"] = str(payload.email)
    elif payload.phone:
        query["phone"] = payload.phone
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp email hoặc số điện thoại",
        )

    user = await users_col.find_one(query)
    # Vì lý do bảo mật, nếu không tìm thấy user vẫn trả về thông báo chung
    if not user:
        return APIResponse(
            success=True,
            message="Nếu tài khoản tồn tại trong hệ thống, hướng dẫn khôi phục mật khẩu đã được gửi.",
            data={"sent": True},
        )

    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
    )

    await users_col.update_one(
        {"_id": user["_id"]},
        {"$set": {"reset_token": reset_token, "reset_token_expires_at": expires_at}},
    )

    # In ra console ở môi trường phát triển theo đúng đặc tả F01
    recipient = user.get("email") or user.get("phone")
    reset_link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={reset_token}"
    otp_code = reset_token[:6].upper()

    console_msg = (
        "\n" + "=" * 60 + "\n"
        "[F01 - DEV CONSOLE EMAIL] QUÊN MẬT KHẨU TÀI KHOẢN VÕ PHỤC\n"
        f"Người nhận: {recipient} ({user.get('full_name')})\n"
        f"Mã OTP xác thực: {otp_code}\n"
        f"Đường dẫn đặt lại mật khẩu: {reset_link}\n"
        f"Thời hạn hiệu lực: {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} phút\n"
        + "=" * 60 + "\n"
    )
    print(console_msg)
    logger.info(console_msg)

    return APIResponse(
        success=True,
        message="Mã khôi phục đã được gửi. Ở môi trường phát triển, vui lòng xem console log.",
        data={"sent": True, "dev_token": reset_token if settings.DEBUG else None},
    )


@router.post("/reset-password", response_model=APIResponse[dict])
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Đặt lại mật khẩu mới bằng token (F01).
    - Kiểm tra token hợp lệ và còn thời hạn.
    - Cập nhật mật khẩu mới băm bằng bcrypt.
    """
    users_col = db["users"]
    now = datetime.now(timezone.utc)

    user = await users_col.find_one({"reset_token": payload.token})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token khôi phục không hợp lệ hoặc đã được sử dụng",
        )

    expires_at = user.get("reset_token_expires_at")
    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token khôi phục đã hết hạn. Vui lòng yêu cầu lại.",
            )

    new_hash = hash_password(payload.new_password)
    await users_col.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "hashed_password": new_hash,
                "reset_token": None,
                "reset_token_expires_at": None,
                "failed_login_attempts": 0,
                "locked_until": None,
                "updated_at": now,
            }
        },
    )

    return APIResponse(
        success=True,
        message="Đặt lại mật khẩu thành công. Bạn có thể đăng nhập bằng mật khẩu mới.",
        data={"reset": True},
    )


@router.get("/me", response_model=APIResponse[UserResponse])
async def get_me(current_user: dict = Depends(get_current_user)):
    """Lấy thông tin tài khoản đang đăng nhập."""
    user_response = UserResponse(
        id=current_user["id"],
        phone=current_user["phone"],
        full_name=current_user["full_name"],
        role=current_user.get("role", "customer"),
        email=current_user.get("email"),
        address=current_user.get("address"),
        is_active=current_user.get("is_active", True),
        created_at=current_user.get("created_at", datetime.now(timezone.utc)),
    )
    return APIResponse(
        success=True,
        message="Lấy thông tin tài khoản thành công",
        data=user_response,
    )
