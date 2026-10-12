from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.responses import APIResponse
from app.modules.blog.models import BlogPost

router = APIRouter(prefix="/blog", tags=["Blog & SEO Guides"])


@router.get("")
async def list_posts(db: Session = Depends(get_db)):
    """Lấy danh sách bài viết blog cẩm nang võ thuật từ database."""
    posts = db.query(BlogPost).order_by(BlogPost.created_at.desc()).all()
    data = [
        {
            "id": p.id,
            "title": p.title,
            "slug": p.slug,
            "summary": p.summary,
            "content": p.content,
            "thumbnail": p.thumbnail,
            "category": p.category,
            "created_at": p.created_at,
        }
        for p in posts
    ]
    return APIResponse(
        success=True,
        message="Lấy danh sách bài viết thành công",
        data=data,
    )
