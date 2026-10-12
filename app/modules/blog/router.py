from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel
from app.core.responses import APIResponse

router = APIRouter(prefix="/blog", tags=["Blog & SEO Guides"])


class BlogPost(BaseModel):
    id: str
    title: str
    slug: str
    summary: str
    content: str
    thumbnail: str
    category: str
    created_at: datetime


MOCK_POSTS = [
    {
        "id": "post-1",
        "title": "Hướng dẫn cách thắt đai Vovinam và Karate đúng chuẩn",
        "slug": "huong-dan-that-dai-vovinam-karate",
        "summary": "Chi tiết từng bước thắt đai võ thuật giúp đai chặt, cân xứng hai đầu và thẩm mỹ khi biểu diễn tấn pháp.",
        "content": "Nội dung bài viết hướng dẫn thắt đai...",
        "thumbnail": "https://placehold.co/600x400?text=Huong+Dan+That+Dai",
        "category": "Kỹ thuật",
        "created_at": datetime.now(timezone.utc),
    },
    {
        "id": "post-2",
        "title": "Cách chọn võ phục và bảo quản võ phục không bị ố vàng",
        "slug": "cach-chon-va-bao-quan-vo-phuc",
        "summary": "Mẹo giặt võ phục cotton, xử lý mồ hôi và phơi đồ giúp bộ võ phục luôn trắng sáng tinh tươm.",
        "content": "Nội dung mẹo giặt ủi...",
        "thumbnail": "https://placehold.co/600x400?text=Bao+Quan+Vo+Phuc",
        "category": "Cẩm nang",
        "created_at": datetime.now(timezone.utc),
    },
]


@router.get("", response_model=APIResponse[List[BlogPost]])
async def list_posts():
    """Lấy danh sách bài viết blog cẩm nang võ thuật."""
    return APIResponse(
        success=True,
        message="Lấy danh sách bài viết thành công",
        data=MOCK_POSTS,
    )
