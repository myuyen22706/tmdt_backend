"""Script nạp dữ liệu mẫu cho hệ thống Võ phục "Đai Trắng" trên MongoDB Atlas.
LƯU Ý QUAN TRỌNG: Toàn bộ dữ liệu (sản phẩm, giá bán, tồn kho, bảng size, tài khoản) 
dưới đây là DỮ LIỆU GIẢ ĐỊNH dùng cho mục đích chạy thử và minh chứng đồ án môn học.
"""
import asyncio
import sys
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.core.security import hash_password

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


async def seed_data(target_db=None):
    if target_db is not None:
        db = target_db
    else:
        uri = settings.MONGODB_URI
        db_name = settings.MONGODB_DB_NAME
        print(f"=== Đang kết nối tới MongoDB: {uri[:30]}... / {db_name} ===")

        try:
            client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=4000)
            await client.admin.command("ping")
            db = client[db_name]
            print(">>> Kết nối MongoDB Atlas thành công! <<<")
        except Exception as e:
            print(f"Không thể kết nối Atlas ({e}), khởi chạy Mongomock...")
            from mongomock_motor import AsyncMongoMockClient
            client = AsyncMongoMockClient()
            db = client[db_name]

    now = datetime.now(timezone.utc)

    # 1. Môn võ (Martial Arts)
    print("1. Nạp danh mục 4 môn võ chính...")
    await db["martial_arts"].delete_many({})
    martial_arts = [
        {"id": "vovinam", "name": "Vovinam (Việt Võ Đạo)", "description": "Võ thuật truyền thống Việt Nam, phát triển toàn diện đòn chân kẹp cổ và tấn pháp"},
        {"id": "taekwondo", "name": "Taekwondo (WTF)", "description": "Môn võ Olympic với hệ thống đòn đá nhanh, mạnh và chuẩn xác"},
        {"id": "karate", "name": "Karatedo", "description": "Môn võ truyền thống Nhật Bản rèn luyện sự cương nhu và tinh thần võ sĩ đạo"},
        {"id": "vo_co_truyen", "name": "Võ Cổ Truyền", "description": "Di sản võ học ngàn năm của các môn phái truyền thống Việt Nam"},
    ]
    await db["martial_arts"].insert_many(martial_arts)

    # 2. Loại sản phẩm (Categories)
    print("2. Nạp danh mục 5 loại sản phẩm...")
    await db["categories"].delete_many({})
    categories = [
        {"id": "vo_phuc", "name": "Võ phục"},
        {"id": "dai", "name": "Đai võ thuật"},
        {"id": "bao_ho", "name": "Đồ bảo hộ & Giáp"},
        {"id": "tui_dung", "name": "Túi đựng & Balo"},
        {"id": "phu_kien", "name": "Phụ kiện & Binh khí"},
    ]
    await db["categories"].insert_many(categories)

    # 3. Bảng size quy chuẩn theo nhân trắc học (Size Charts - F04)
    print("3. Nạp bảng size quy chuẩn cho các môn võ...")
    await db["size_charts"].delete_many({})
    base_size_template = [
        ("Size 00", 100, 115, 15, 22, 4, 5, "Trẻ mẫu giáo 4-5 tuổi"),
        ("Size 0", 115, 125, 20, 28, 6, 7, "Trẻ tiểu học 6-7 tuổi"),
        ("Size 1", 125, 135, 26, 35, 8, 9, "Trẻ tiểu học 8-9 tuổi"),
        ("Size 2", 135, 145, 33, 42, 10, 11, "Học sinh 10-11 tuổi"),
        ("Size 3", 145, 155, 40, 50, 12, 14, "Học sinh cấp 2, người nhỏ gọn (S)"),
        ("Size 4", 155, 165, 48, 60, 15, 18, "Người lớn thanh thiếu niên (M)"),
        ("Size 5", 165, 172, 58, 70, 18, 50, "Người lớn chuẩn (L)"),
        ("Size 6", 172, 180, 68, 82, 18, 50, "Dáng người cao đậm (XL)"),
        ("Size 7", 180, 195, 80, 105, 18, 50, "Thể hình cao lớn (XXL)"),
    ]

    size_chart_docs = []
    for ma in ["vovinam", "taekwondo", "karate", "vo_co_truyen"]:
        for name, h_min, h_max, w_min, w_max, a_min, a_max, note in base_size_template:
            size_chart_docs.append({
                "id": f"chart-{ma}-{name.lower().replace(' ', '-')}",
                "martial_art_id": ma,
                "size_name": name,
                "height_min_cm": float(h_min),
                "height_max_cm": float(h_max),
                "weight_min_kg": float(w_min),
                "weight_max_kg": float(w_max),
                "age_min": a_min,
                "age_max": a_max,
                "fit_note": note,
            })
    await db["size_charts"].insert_many(size_chart_docs)

    # 4. Tài khoản mẫu Demo (Admin, Staff, Customers, Coach)
    print("4. Nạp các tài khoản mẫu phân quyền (Cả đầu số 0909 và 0988)...")
    await db["users"].delete_many({})
    demo_users = [
        # Bộ tài khoản 0909...
        {
            "id": "usr-admin-01",
            "phone": "0909000001",
            "full_name": "Quản Trị Viên (Admin)",
            "hashed_password": hash_password("AdminPass123@"),
            "role": "admin",
            "email": "admin@daitrang.vn",
            "failed_login_attempts": 0,
            "locked_until": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "usr-staff-01",
            "phone": "0909000002",
            "full_name": "Nhân Viên Vận Hành (Staff)",
            "hashed_password": hash_password("StaffPass123@"),
            "role": "staff",
            "email": "staff@daitrang.vn",
            "failed_login_attempts": 0,
            "locked_until": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "usr-cust-01",
            "phone": "0909000003",
            "full_name": "Phụ Huynh Nguyễn Văn Nam",
            "hashed_password": hash_password("CustomerPass123@"),
            "role": "customer",
            "email": "nam.nguyen@example.com",
            "failed_login_attempts": 0,
            "locked_until": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "usr-cust-02",
            "phone": "0909000004",
            "full_name": "Võ Sinh Trần Thị Lan",
            "hashed_password": hash_password("CustomerPass123@"),
            "role": "customer",
            "email": "lan.tran@example.com",
            "failed_login_attempts": 0,
            "locked_until": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "usr-coach-01",
            "phone": "0909000005",
            "full_name": "HLV Võ Đường Lam Sơn",
            "hashed_password": hash_password("CoachPass123@"),
            "role": "coach",
            "email": "hlv.lamson@example.com",
            "failed_login_attempts": 0,
            "locked_until": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        # Bộ tài khoản 0988... (Khớp chính xác với các nút bấm 1-Click trên Frontend)
        {
            "id": "usr-admin-88",
            "phone": "0988000001",
            "full_name": "Tổng Quản Trị Hệ Thống (Admin)",
            "hashed_password": hash_password("AdminPass123"),
            "role": "admin",
            "email": "admin88@daitrang.vn",
            "failed_login_attempts": 0,
            "locked_until": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "usr-staff-88",
            "phone": "0988000002",
            "full_name": "Điều Phối Đơn Hàng (Staff)",
            "hashed_password": hash_password("StaffPass123"),
            "role": "staff",
            "email": "staff88@daitrang.vn",
            "failed_login_attempts": 0,
            "locked_until": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "usr-coach-88",
            "phone": "0988000003",
            "full_name": "HLV CLB Taekwondo Bạch Hổ",
            "hashed_password": hash_password("CoachPass123"),
            "role": "coach",
            "email": "hlv88@daitrang.vn",
            "failed_login_attempts": 0,
            "locked_until": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": "usr-cust-88",
            "phone": "0988000004",
            "full_name": "Khách Hàng Lê Minh Đức",
            "hashed_password": hash_password("UserPass123"),
            "role": "customer",
            "email": "duc.le@example.com",
            "failed_login_attempts": 0,
            "locked_until": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
    ]
    await db["users"].insert_many(demo_users)

    # 5. Nạp 24 sản phẩm mẫu có biến thể tồn kho
    print("5. Nạp 24 sản phẩm mẫu có biến thể size, màu, tồn kho...")
    await db["products"].delete_many({})

    raw_products = [
        # VOVINAM
        ("prod-vov-01", "Võ Phục Vovinam Tiêu Chuẩn Việt Võ Đạo", "vo-phuc-vovinam-tieu-chuan", "vovinam", "vo_phuc", "lam_dai", 240000, 280000, 14, True, "Xanh dương"),
        ("prod-vov-02", "Võ Phục Vovinam Cao Cấp Kaki 100% Cotton", "vo-phuc-vovinam-cao-cap-cotton", "vovinam", "vo_phuc", "hoang_dai", 380000, 450000, 15, True, "Xanh dương"),
        ("prod-vov-03", "Đai Vovinam Lam Đai Tiêu Chuẩn 4 Chỉ May", "dai-vovinam-lam-dai", "vovinam", "dai", "lam_dai", 45000, 60000, 25, False, "Xanh dương"),
        ("prod-vov-04", "Đai Vovinam Hoàng Đai Bản Rộng 5cm", "dai-vovinam-hoang-dai", "vovinam", "dai", "hoang_dai", 65000, 80000, 18, False, "Vàng"),
        ("prod-vov-05", "Giáp Thi Đấu Vovinam Bảo Vệ Ngực Hai Mặt", "giap-thi-dau-vovinam", "vovinam", "bao_ho", None, 320000, 390000, 18, False, "Đỏ/Xanh"),
        ("prod-vov-06", "Balo Thể Thao Đựng Võ Phục Vovinam Chống Nước", "balo-vovinam-chong-nuoc", "vovinam", "tui_dung", None, 180000, 220000, 18, False, "Xanh dương"),

        # TAEKWONDO
        ("prod-tkd-01", "Võ Phục Taekwondo Cổ Trắng Phong Trào", "vo-phuc-taekwondo-co-trang", "taekwondo", "vo_phuc", "dai_trang", 260000, 300000, 13, True, "Trắng"),
        ("prod-tkd-02", "Võ Phục Taekwondo Cổ Đen Thi Đấu Vải Kim Cương", "vo-phuc-taekwondo-co-den", "taekwondo", "vo_phuc", "dai_den", 420000, 500000, 16, True, "Trắng cổ đen"),
        ("prod-tkd-03", "Đai Taekwondo Đai Đen Đẳng Thêu Chỉ Vàng", "dai-taekwondo-dai-den-theu", "taekwondo", "dai", "dai_den", 120000, 150000, 20, False, "Đen"),
        ("prod-tkd-04", "Mũ Bảo Hộ Thi Đấu Taekwondo Có Kính Chắn", "mu-bao-ho-taekwondo", "taekwondo", "bao_ho", None, 350000, 420000, 16, False, "Đỏ"),
        ("prod-tkd-05", "Giáp Tay Chân Thi Đấu Taekwondo Chuẩn WTF", "giap-tay-chan-taekwondo-wtf", "taekwondo", "bao_ho", None, 280000, 340000, 17, False, "Trắng"),
        ("prod-tkd-06", "Túi Trống Đựng Giáp Và Võ Phục Taekwondo", "tui-trong-taekwondo", "taekwondo", "tui_dung", None, 210000, 260000, 19, False, "Đen"),

        # KARATE
        ("prod-kar-01", "Võ Phục Karate Vải Kaki Nhật Form Kata", "vo-phuc-karate-form-kata", "karate", "vo_phuc", "dai_trang", 310000, 360000, 14, True, "Trắng"),
        ("prod-kar-02", "Võ Phục Karate Kumite Siêu Nhẹ Thoát Khí", "vo-phuc-karate-kumite-sieu-nhe", "karate", "vo_phuc", "dai_den", 460000, 550000, 16, True, "Trắng"),
        ("prod-kar-03", "Đai Karate Đai Trắng Vải Bố 100% Cotton", "dai-karate-dai-trang", "karate", "dai", "dai_trang", 50000, 65000, 23, False, "Trắng"),
        ("prod-kar-04", "Găng Tay Thi Đấu Karate Chuẩn WKF Không Ngón", "gang-tay-karate-wkf", "karate", "bao_ho", None, 190000, 230000, 17, False, "Xanh"),
        ("prod-kar-05", "Bảo Hộ Ống Đồng Mu Bàn Chân Karate", "bao-ho-ong-dong-karate", "karate", "bao_ho", None, 240000, 290000, 17, False, "Đỏ"),
        ("prod-kar-06", "Băng Quấn Tay Thể Thao Karate Cotton 4.5m", "bang-quan-tay-karate", "karate", "phu_kien", None, 65000, 85000, 23, False, "Đen"),

        # VÕ CỔ TRUYỀN
        ("prod-vct-01", "Võ Phục Cổ Truyền Màu Đen Cúc Bấm Vải Đũi", "vo-phuc-co-truyen-den-cuc-bam", "vo_co_truyen", "vo_phuc", "dai_den", 250000, 290000, 14, True, "Đen"),
        ("prod-vct-02", "Võ Phục Cổ Truyền Thêu Rồng Biểu Diễn Hội Làng", "vo-phuc-co-truyen-theu-rong", "vo_co_truyen", "vo_phuc", "dai_vang", 490000, 590000, 17, True, "Đen chỉ vàng"),
        ("prod-vct-03", "Đai Cổ Truyền Đỏ Đậm Vải Sa Tanh Bản Rộng", "dai-co-truyen-do-dam", "vo_co_truyen", "dai", "dai_do", 55000, 70000, 21, False, "Đỏ"),
        ("prod-vct-04", "Đai Cổ Truyền Vàng Đai Đẳng Thắt Lưng Bụng", "dai-co-truyen-vang", "vo_co_truyen", "dai", "dai_vang", 55000, 70000, 21, False, "Vàng"),
        ("prod-vct-05", "Côn Nhị Khúc Bọc Mút Mềm Tập Luyện An Toàn", "con-nhi-khuc-boc-mut", "vo_co_truyen", "phu_kien", None, 95000, 120000, 20, False, "Đen vàng"),
        ("prod-vct-06", "Bao Đựng Binh Khí Trường Côn Kiếm Gỗ Cổ Truyền", "bao-dung-binh-khi-co-truyen", "vo_co_truyen", "tui_dung", None, 130000, 160000, 18, False, "Rằn ri"),
    ]

    product_docs = []
    sizes_sample = ["Size 0", "Size 1", "Size 2", "Size 3", "Size 4", "Size 5"]

    for pid, name, slug, ma, cat, belt, price, orig_price, disc, custom, color in raw_products:
        variants = []
        if cat == "vo_phuc":
            for s in sizes_sample:
                sku = f"{pid.upper()}-{s.replace(' ', '')}"
                variants.append({
                    "sku": sku,
                    "size": s,
                    "color": color,
                    "price": price,
                    "stock": 15,
                    "low_stock_threshold": 5,
                })
        else:
            variants.append({
                "sku": f"{pid.upper()}-FREE",
                "size": "Freesize",
                "color": color,
                "price": price,
                "stock": 25,
                "low_stock_threshold": 5,
            })

        product_docs.append({
            "id": pid,
            "name": name,
            "slug": slug,
            "martial_art_id": ma,
            "category_id": cat,
            "belt_rank": belt,
            "price": price,
            "original_price": orig_price,
            "discount_percent": disc,
            "thumbnail": f"/images/products/{slug}.jpg",
            "images": [f"/images/products/{slug}-1.jpg", f"/images/products/{slug}-2.jpg"],
            "material": "Vải Kaki Cotton 100% chuyên dụng võ thuật",
            "description": f"Sản phẩm {name} chất lượng cao, bền bỉ, thoáng mát khi vận động cường độ cao.",
            "is_customizable": custom,
            "rating": 4.9,
            "review_count": 28,
            "is_active": True,
            "variants": variants,
            "created_at": now,
            "updated_at": now,
        })

    await db["products"].insert_many(product_docs)

    # 6. Tạo một hồ sơ mẫu võ sinh (F05)
    print("6. Nạp hồ sơ mẫu võ sinh cho khách hàng...")
    await db["student_profiles"].delete_many({})
    await db["student_profiles"].insert_many([
        {
            "id": "prof-sample-01",
            "user_id": "usr-cust-01",
            "student_name": "Bé Nguyễn Hoàng Long (Con 1)",
            "birth_year": 2017,
            "martial_art": "vovinam",
            "height_cm": 128.0,
            "weight_kg": 27.5,
            "recommended_size": "Size 1",
            "measured_date": now,
            "created_at": now,
        }
    ])

    # 7. Nạp bài viết Blog & Cẩm nang võ sinh
    print("7. Nạp bài viết Blog & Cẩm nang võ thuật...")
    await db["blog_posts"].delete_many({})
    await db["blog_posts"].insert_many([
        {
            "id": "post-1",
            "title": "Hướng Dẫn Buộc Đai Vovinam & Karate Đúng Chuẩn Liên Đoàn",
            "slug": "huong-dan-that-dai-vovinam-karate",
            "summary": "Từng bước hướng dẫn thắt đai cân đối hai đầu, siết chặt vừa vặn vạt áo và tạo thẩm mỹ uy phong khi biểu diễn quyền pháp.",
            "content": "Nội dung hướng dẫn chi tiết cách thắt đai Vovinam, Karate đúng quy chuẩn Liên đoàn...",
            "thumbnail": "/vovi.jpg",
            "category": "Kỹ Thuật Võ Đạo",
            "is_published": True,
            "created_at": now,
        },
        {
            "id": "post-2",
            "title": "Mẹo Giặt & Bảo Quản Võ Phục Cotton Trắng Sáng, Không Ố Vàng",
            "slug": "meo-giat-bao-quan-vo-phuc",
            "summary": "Cách ngâm nước lạnh với giấm trắng khử mồ hôi muối, tránh phơi nắng gắt trực tiếp giúp sợi vải Kaki luôn bền chắc và đứng form.",
            "content": "Nội dung cẩm nang giặt và bảo quản võ phục Kaki 100% Cotton...",
            "thumbnail": "/vovi.jpg",
            "category": "Cẩm Nang Võ Sinh",
            "is_published": True,
            "created_at": now,
        },
        {
            "id": "post-3",
            "title": "Phân Biệt Quy Cách Võ Phục 4 Môn: Vovinam, Taekwondo, Karate, Cổ Truyền",
            "slug": "phan-biet-quy-cach-vo-phuc-4-mon",
            "summary": "Hiểu rõ sự khác biệt giữa áo cổ chữ V (Taekwondo), áo vạt chéo xanh lam (Vovinam), áo trắng nút chéo (Karate) và áo nút thắt (Cổ Truyền).",
            "content": "Nội dung phân biệt quy cách võ phục các môn phái...",
            "thumbnail": "/vovi.jpg",
            "category": "Kiến Thức Võ Thuật",
            "is_published": True,
            "created_at": now,
        },
    ])

    # 8. Nạp mã giảm giá Vouchers & Khuyến mãi
    print("8. Nạp mã giảm giá Vouchers...")
    await db["vouchers"].delete_many({})
    await db["vouchers"].insert_many([
        {
            "id": "vouc-01",
            "code": "VOVINAM10",
            "discount_type": "PERCENT",
            "discount_value": 10,
            "min_order_amount": 300000,
            "usage_limit": 100,
            "used_count": 0,
            "is_active": True,
            "created_at": now,
        },
        {
            "id": "vouc-02",
            "code": "TANBINH20",
            "discount_type": "FIXED",
            "discount_value": 20000,
            "min_order_amount": 200000,
            "usage_limit": 100,
            "used_count": 0,
            "is_active": True,
            "created_at": now,
        },
    ])

    # 9. Nạp CLB Võ Đường & Đợt gom đơn B2B mẫu
    print("9. Nạp CLB Võ Đường & Chiến dịch gom đơn B2B mẫu...")
    await db["clubs"].delete_many({})
    await db["clubs"].insert_one({
        "id": "dojo-phudong",
        "club_name": "CLB Vovinam Phù Đổng",
        "martial_art_id": "vovinam",
        "address": "Số 45 Lê Lợi, Quận 1, TP. Hồ Chí Minh",
        "coach_name": "Võ sư Nguyễn Văn Hùng",
        "coach_phone": "0987654321",
        "coach_email": "hung.phudong@daitrang.vn",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })

    await db["club_campaigns"].delete_many({})
    await db["club_campaigns"].insert_one({
        "id": "camp-phudong2026",
        "campaign_code": "PHUDONG2026",
        "club_id": "dojo-phudong",
        "club_name": "CLB Vovinam Phù Đổng",
        "campaign_title": "Đợt Đặt Đồng Phục Khóa Hè – CLB Vovinam Phù Đổng",
        "applicable_product_ids": ["prod-vov-01"],
        "target_quantity": 30,
        "discount_percent": 15,
        "deadline": now,
        "has_custom_logo": True,
        "allow_club_consolidated_payment": True,
        "campaign_url": f"{settings.FRONTEND_URL.rstrip('/')}/dojo/PHUDONG2026",
        "qr_code_url": f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={settings.FRONTEND_URL.rstrip('/')}/dojo/PHUDONG2026",
        "status": "open",
        "total_ordered": 3,
        "total_amount": 760000,
        "deposit_amount": 0,
        "deposit_paid": False,
        "remaining_amount_paid": False,
        "created_at": now,
        "updated_at": now,
    })

    print("=== NẠP DỮ LIỆU MẪU MONGODB ATLAS HOÀN TẤT THÀNH CÔNG! ===")


if __name__ == "__main__":
    asyncio.run(seed_data())
