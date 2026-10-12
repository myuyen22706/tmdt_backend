from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.responses import APIResponse
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.schemas import TokenResponse, UserLogin, UserRegister
from app.modules.users.models import User


router = APIRouter(prefix="/auth", tags=["Authentication & Accounts"])


@router.post("/register", response_model=APIResponse[TokenResponse])
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Đăng ký tài khoản (khách hàng hoặc HLV võ đường) lưu vào database."""
    # Kiểm tra số điện thoại tồn tại
    existing = db.query(User).filter(User.phone == user_data.phone).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Số điện thoại này đã được đăng ký")

    new_user = User(
        phone=user_data.phone,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
        role=user_data.role,
        email=str(user_data.email) if user_data.email else None,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(subject=new_user.phone, role=new_user.role)
    return APIResponse(
        success=True,
        message="Đăng ký tài khoản thành công",
        data=TokenResponse(
            access_token=token,
            user_id=new_user.id,
            full_name=new_user.full_name,
            role=new_user.role,
        ),
    )


@router.post("/login", response_model=APIResponse[TokenResponse])
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Đăng nhập bằng số điện thoại và mật khẩu."""
    user = db.query(User).filter(User.phone == credentials.phone).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Số điện thoại hoặc mật khẩu không chính xác",
        )

    token = create_access_token(subject=user.phone, role=user.role)
    return APIResponse(
        success=True,
        message="Đăng nhập thành công",
        data=TokenResponse(
            access_token=token,
            user_id=user.id,
            full_name=user.full_name,
            role=user.role,
        ),
    )
