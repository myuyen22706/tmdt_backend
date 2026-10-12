import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

logger = logging.getLogger("vo_ecommerce.database")

Base = declarative_base()

def get_engine():
    db_url = settings.DATABASE_URL
    connect_args = {}
    
    # Check if SQL Server
    if "mssql" in db_url:
        # MSSQL connection configuration
        connect_args = {
            "timeout": 15,
        }
        try:
            engine = create_engine(
                db_url,
                connect_args=connect_args,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
            # Test ping
            with engine.connect() as conn:
                logger.info("Connected to Microsoft SQL Server successfully!")
            return engine
        except Exception as e:
            logger.warning(
                f"SQL Server chưa kết nối được ({e}). Tạm thời sử dụng SQLite cục bộ để server hoạt động. "
                "Sau khi bạn bật SQL Server, cấu hình lại DATABASE_URL trong file .env."
            )
            fallback_url = "sqlite:///./vo_ecommerce_dev.db"
            return create_engine(fallback_url, connect_args={"check_same_thread": False})
    elif "sqlite" in db_url:
        return create_engine(db_url, connect_args={"check_same_thread": False})
    else:
        return create_engine(db_url, pool_pre_ping=True)

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """FastAPI Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Tạo toàn bộ bảng trong SQL Server / Database theo models đã khai báo."""
    Base.metadata.create_all(bind=engine)
