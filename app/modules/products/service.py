from typing import List, Optional
from app.modules.products.schemas import ProductFilterParams, ProductResponse, ProductVariant


MOCK_PRODUCTS: List[dict] = [
    {
        "id": "prod-vovinam-standard",
        "name": "Võ Phục Vovinam Tiêu Chuẩn Việt Võ Đạo",
        "slug": "vo-phuc-vovinam-tieu-chuan",
        "martial_art": "vovinam",
        "category": "vo_phuc",
        "belt_rank": "lam_dai",
        "price": 240000,
        "original_price": 280000,
        "thumbnail": "https://placehold.co/400x400?text=Vovinam+Uniform",
        "images": ["https://placehold.co/600x600?text=Vovinam+1", "https://placehold.co/600x600?text=Vovinam+2"],
        "material": "Vải Kaki 100% Cotton dệt chéo, co giãn tốt",
        "description": "Võ phục Vovinam chuẩn quy cách liên đoàn Việt Võ Đạo, đường chỉ may dằn chắc chắn, form chuẩn tôn dáng tấn.",
        "is_customizable": True,
        "rating": 4.9,
        "review_count": 58,
        "variants": [
            {"id": "var-vov-s1", "size": "Size 1", "stock": 15, "price_adjustment": 0},
            {"id": "var-vov-s2", "size": "Size 2", "stock": 20, "price_adjustment": 0},
            {"id": "var-vov-s3", "size": "Size 3 (S)", "stock": 12, "price_adjustment": 0},
            {"id": "var-vov-s4", "size": "Size 4 (M)", "stock": 25, "price_adjustment": 10000},
            {"id": "var-vov-s5", "size": "Size 5 (L)", "stock": 8, "price_adjustment": 15000},
        ],
    },
    {
        "id": "prod-taekwondo-dobok",
        "name": "Võ Phục Taekwondo Cổ Đen (WTF)",
        "slug": "vo-phuc-taekwondo-co-den-wtf",
        "martial_art": "taekwondo",
        "category": "vo_phuc",
        "belt_rank": "dai_den",
        "price": 320000,
        "original_price": 370000,
        "thumbnail": "https://placehold.co/400x400?text=Taekwondo+Dobok",
        "images": ["https://placehold.co/600x600?text=TKD+Dobok+1"],
        "material": "Poly-Cotton dập gân kim cương thông hơi siêu nhẹ",
        "description": "Võ phục Dobok Taekwondo cổ đen tiêu chuẩn thi đấu quốc tế WTF, thoát mồ hôi cực nhanh.",
        "is_customizable": True,
        "rating": 4.8,
        "review_count": 42,
        "variants": [
            {"id": "var-tkd-s3", "size": "Size 3 (S)", "stock": 10, "price_adjustment": 0},
            {"id": "var-tkd-s4", "size": "Size 4 (M)", "stock": 18, "price_adjustment": 0},
            {"id": "var-tkd-s5", "size": "Size 5 (L)", "stock": 14, "price_adjustment": 15000},
        ],
    },
    {
        "id": "prod-karate-gi",
        "name": "Võ Phục Karate Kata / Kumite Chuyên Dụng",
        "slug": "vo-phuc-karate-chuyen-dung",
        "martial_art": "karate",
        "category": "vo_phuc",
        "belt_rank": "dai_trang",
        "price": 290000,
        "original_price": 330000,
        "thumbnail": "https://placehold.co/400x400?text=Karate+Gi",
        "images": ["https://placehold.co/600x600?text=Karate+Gi+1"],
        "material": "Vải Canvas 12oz tạo tiếng vút đòn giòn giã",
        "description": "Võ phục Karate gi chất lượng cao dành cho thi đấu quyền Kata và đối kháng Kumite.",
        "is_customizable": True,
        "rating": 5.0,
        "review_count": 31,
        "variants": [
            {"id": "var-kar-s3", "size": "Size 3 (S)", "stock": 8, "price_adjustment": 0},
            {"id": "var-kar-s4", "size": "Size 4 (M)", "stock": 15, "price_adjustment": 0},
            {"id": "var-kar-s5", "size": "Size 5 (L)", "stock": 11, "price_adjustment": 10000},
        ],
    },
    {
        "id": "prod-voco-truyen-den",
        "name": "Võ Phục Võ Cổ Truyền Màu Đen Cúc Bấm",
        "slug": "vo-phuc-vo-co-truyen-mau-den",
        "martial_art": "vo_co_truyen",
        "category": "vo_phuc",
        "belt_rank": "dai_den",
        "price": 230000,
        "original_price": 260000,
        "thumbnail": "https://placehold.co/400x400?text=Vo+Co+Truyen",
        "images": ["https://placehold.co/600x600?text=Vo+Co+Truyen+1"],
        "material": "Vải Kaki dệt thoi nhuộm đen tuyền",
        "description": "Võ phục cổ truyền truyền thống Việt Nam áo nút thắt bện thủ công hoặc nút bấm kim loại bền bỉ.",
        "is_customizable": True,
        "rating": 4.7,
        "review_count": 29,
        "variants": [
            {"id": "var-vct-s2", "size": "Size 2", "stock": 14, "price_adjustment": 0},
            {"id": "var-vct-s3", "size": "Size 3 (S)", "stock": 20, "price_adjustment": 0},
            {"id": "var-vct-s4", "size": "Size 4 (M)", "stock": 16, "price_adjustment": 0},
        ],
    },
    {
        "id": "prod-belt-vovinam-blue",
        "name": "Đai Vovinam Lam Đai Tiêu Chuẩn Thêu Chữ",
        "slug": "dai-vovinam-lam-dai-tieu-chuan",
        "martial_art": "vovinam",
        "category": "dai",
        "belt_rank": "lam_dai",
        "price": 45000,
        "original_price": 55000,
        "thumbnail": "https://placehold.co/400x400?text=Vovinam+Blue+Belt",
        "images": ["https://placehold.co/600x600?text=Blue+Belt"],
        "material": "Vải đai nhiều lớp may 8 đường chỉ thẳng tắp",
        "description": "Đai xanh lam Vovinam bản 4.5cm, thêu logo liên đoàn sắc nét, đủ chiều dài từ 2m đến 2.8m.",
        "is_customizable": True,
        "rating": 4.9,
        "review_count": 87,
        "variants": [
            {"id": "var-belt-2m2", "size": "2.2m", "stock": 50, "price_adjustment": 0},
            {"id": "var-belt-2m5", "size": "2.5m", "stock": 40, "price_adjustment": 5000},
        ],
    },
]


class ProductService:
    @classmethod
    def get_list(cls, filters: ProductFilterParams) -> List[dict]:
        items = MOCK_PRODUCTS
        if filters.martial_art:
            items = [p for p in items if p["martial_art"] == filters.martial_art]
        if filters.category:
            items = [p for p in items if p["category"] == filters.category]
        if filters.belt_rank:
            items = [p for p in items if p["belt_rank"] == filters.belt_rank]
        if filters.min_price is not None:
            items = [p for p in items if p["price"] >= filters.min_price]
        if filters.max_price is not None:
            items = [p for p in items if p["price"] <= filters.max_price]
        if filters.search:
            q = filters.search.lower()
            items = [p for p in items if q in p["name"].lower() or q in p["description"].lower()]
        return items

    @classmethod
    def get_by_id_or_slug(cls, id_or_slug: str) -> Optional[dict]:
        for p in MOCK_PRODUCTS:
            if p["id"] == id_or_slug or p["slug"] == id_or_slug:
                return p
        return None
