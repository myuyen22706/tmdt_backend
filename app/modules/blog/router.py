from typing import List
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_db
from app.core.responses import APIResponse

router = APIRouter(prefix="/blog", tags=["Blog & SEO Guides"])


@router.get("")
async def list_posts(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lấy danh sách bài viết blog cẩm nang võ thuật từ database MongoDB."""
    posts_col = db["blog_posts"]
    cursor = posts_col.find({}).sort("created_at", -1)
    posts = await cursor.to_list(length=50)
    data = [
        {
            "id": p.get("id", str(p.get("_id", ""))),
            "title": p.get("title", ""),
            "slug": p.get("slug", ""),
            "summary": p.get("summary", ""),
            "content": p.get("content", ""),
            "thumbnail": p.get("thumbnail", "/vovi.jpg"),
            "category": p.get("category", "Kỹ thuật"),
            "created_at": p.get("created_at"),
        }
        for p in posts
    ]
    return APIResponse(
        success=True,
        message="Lấy danh sách bài viết thành công",
        data=data,
    )

