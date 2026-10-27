from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.database import get_db
from app.core.responses import APIResponse

router = APIRouter(prefix="/blog", tags=["Blog & SEO Guides"])


def _format_post(p: dict, include_content: bool = True) -> dict:
    post = {
        "id": p.get("id", str(p.get("_id", ""))),
        "title": p.get("title", ""),
        "slug": p.get("slug", ""),
        "summary": p.get("summary", ""),
        "thumbnail": p.get("thumbnail", "/vovi.jpg"),
        "category": p.get("category", "Kỹ thuật"),
        "created_at": p.get("created_at"),
    }
    if include_content:
        post["content"] = p.get("content", "")
    return post


def _set_public_cache(response: Response) -> None:
    max_age = settings.PUBLIC_CACHE_MAX_AGE
    response.headers["Cache-Control"] = f"public, max-age={max_age}, stale-while-revalidate={max_age * 5}"


@router.get("")
async def list_posts(response: Response, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Lấy danh sách bài viết blog cẩm nang võ thuật từ database MongoDB."""
    posts_col = db["blog_posts"]
    cursor = posts_col.find({"is_published": {"$ne": False}}, {"_id": 0}).sort("created_at", -1)
    posts = await cursor.to_list(length=50)
    _set_public_cache(response)
    return APIResponse(
        success=True,
        message="Lấy danh sách bài viết thành công",
        data=[_format_post(p) for p in posts],
    )


@router.get("/{slug}")
async def get_post(slug: str, response: Response, db: AsyncIOMotorDatabase = Depends(get_db)):
    """Chi tiết một bài viết cẩm nang theo slug (dùng cho trang /blog/{slug} và sitemap)."""
    post = await db["blog_posts"].find_one(
        {"$or": [{"slug": slug}, {"id": slug}], "is_published": {"$ne": False}},
        {"_id": 0},
    )
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết")
    _set_public_cache(response)
    return APIResponse(success=True, message="Lấy bài viết thành công", data=_format_post(post))
