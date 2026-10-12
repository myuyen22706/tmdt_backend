from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Text, DateTime
from app.core.database import Base


class BlogPost(Base):
    """Bài viết hướng dẫn, SEO, thắt đai, cẩm nang bảo quản."""
    __tablename__ = "blog_posts"

    id = Column(String(50), primary_key=True, default=lambda: f"post-{uuid.uuid4().hex[:8]}")
    title = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    summary = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    thumbnail = Column(String(500), nullable=True)
    category = Column(String(100), default="Kỹ thuật")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
