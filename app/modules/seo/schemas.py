from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class BreadcrumbItem(BaseModel):
    name: str
    url: str


class ProductSEOMeta(BaseModel):
    title: str
    description: str
    canonical_url: str
    og_title: str
    og_description: str
    og_image: Optional[str] = None
    og_type: str = "product"
    twitter_card: str = "summary_large_image"
    structured_data: Dict[str, Any]
    breadcrumbs: List[BreadcrumbItem]


class OrganizationSEOMeta(BaseModel):
    name: str = "Đai Trắng"
    legal_name: str = "Công Ty TNHH Võ Phục & Dụng Cụ Võ Thuật Đai Trắng"
    url: str = "https://daitrang.vn"
    logo: str = "https://daitrang.vn/logo.png"
    description: str = "Thương hiệu cung cấp võ phục và phụ kiện võ thuật chuyên nghiệp hàng đầu Việt Nam"
    telephone: str = "0988000001"
    email: str = "cskh@daitrang.vn"
    address: Dict[str, str] = {
        "streetAddress": "Số 123 Đường Ba Tháng Hai, Phường 11",
        "addressLocality": "Quận 10",
        "addressRegion": "TP. Hồ Chí Minh",
        "addressCountry": "VN",
    }
    same_as: List[str] = [
        "https://facebook.com/daitrang.vophuc",
        "https://youtube.com/@daitrangvophuc",
        "https://tiktok.com/@daitrang.vn",
    ]
    structured_data: Dict[str, Any]
