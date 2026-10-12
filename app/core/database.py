"""Database setup and session manager.
Cấu hình sẵn sàng cho SQLAlchemy / SQLite / PostgreSQL khi nhóm bắt đầu cắm DB.
"""
from app.core.config import settings

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker

    connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
    engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()

    def get_db():
        """Dependency for getting DB session."""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

except ImportError:
    # Fallback khi chưa cài sqlalchemy
    Base = object
    get_db = None
