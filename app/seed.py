"""Database seeder script for SQL Server / Development DB.
Tạo toàn bộ bảng và nạp dữ liệu mẫu ban đầu cho toàn bộ hệ thống.
"""
from datetime import datetime, timedelta, timezone
from app.core.database import SessionLocal, init_db, engine
from app.core.security import hash_password

# Import all models so SQLAlchemy discovers them
from app.modules.users.models import User, StudentProfile
from app.modules.products.models import MartialArt, ProductCategory, Product, ProductVariant, SizeChart
from app.modules.dojos.models import DojoClub, DojoOrderCampaign, DojoStudentOrder
from app.modules.orders.models import Order, OrderItem
from app.modules.promotions.models import Voucher
from app.modules.reviews.models import Review
from app.modules.blog.models import BlogPost


def seed():
    print("1. Khởi tạo schema và tạo các bảng trong Database...")
    init_db()

    db = SessionLocal()
    try:
        # Check if already seeded
        if db.query(MartialArt).first():
            print("Dữ liệu mẫu đã tồn tại trong database, bỏ qua bước seed.")
            return

        print("2. Đang nạp danh mục Môn võ & Loại sản phẩm...")
        martial_arts = [
            MartialArt(id="vovinam", name="Vovinam (Việt Võ Đạo)", description="Môn võ truyền thống kết hợp tinh hoa võ học Việt Nam"),
            MartialArt(id="taekwondo", name="Taekwondo (WTF)", description="Môn võ thi đấu Olympic với kỹ thuật đòn chân uy lực"),
            MartialArt(id="karate", name="Karatedo", description="Môn võ truyền thống Nhật Bản với thế quyền Kata và Kumite"),
            MartialArt(id="vo_co_truyen", name="Võ Cổ Truyền", description="Võ thuật cổ truyền dân tộc Việt Nam"),
        ]
        db.add_all(martial_arts)

        categories = [
            ProductCategory(id="vo_phuc", name="Võ Phục"),
            ProductCategory(id="dai", name="Đai Võ Thuật"),
            ProductCategory(id="bao_ho", name="Đồ Bảo Hộ & Giáp"),
            ProductCategory(id="phu_kien", name="Binh Khí & Phụ Kiện"),
        ]
        db.add_all(categories)
        db.commit()

        print("3. Đang nạp bảng Size quy chuẩn theo nhân trắc học...")
        size_charts = [
            SizeChart(martial_art_id="vovinam", size_name="Size 00 (Trẻ em)", height_min_cm=100, height_max_cm=115, weight_min_kg=15, weight_max_kg=22, fit_note="Trẻ 4-5 tuổi"),
            SizeChart(martial_art_id="vovinam", size_name="Size 0 (Trẻ em)", height_min_cm=115, height_max_cm=125, weight_min_kg=20, weight_max_kg=28, fit_note="Trẻ 6-7 tuổi"),
            SizeChart(martial_art_id="vovinam", size_name="Size 1", height_min_cm=125, height_max_cm=135, weight_min_kg=26, weight_max_kg=35, fit_note="Học sinh tiểu học"),
            SizeChart(martial_art_id="vovinam", size_name="Size 2", height_min_cm=135, height_max_cm=145, weight_min_kg=33, weight_max_kg=42, fit_note="Học sinh cấp 2"),
            SizeChart(martial_art_id="vovinam", size_name="Size 3 (S)", height_min_cm=145, height_max_cm=155, weight_min_kg=40, weight_max_kg=50, fit_note="Người lớn thanh mảnh"),
            SizeChart(martial_art_id="vovinam", size_name="Size 4 (M)", height_min_cm=155, height_max_cm=165, weight_min_kg=48, weight_max_kg=60, fit_note="Size phổ biến nhất"),
            SizeChart(martial_art_id="vovinam", size_name="Size 5 (L)", height_min_cm=165, height_max_cm=172, weight_min_kg=58, weight_max_kg=70, fit_note="Dáng người cao vừa"),
            SizeChart(martial_art_id="vovinam", size_name="Size 6 (XL)", height_min_cm=172, height_max_cm=180, weight_min_kg=68, weight_max_kg=82, fit_note="Dáng người cao đậm"),
            SizeChart(martial_art_id="vovinam", size_name="Size 7 (XXL)", height_min_cm=180, height_max_cm=195, weight_min_kg=80, weight_max_kg=105, fit_note="Thể hình cao lớn"),
        ]
        db.add_all(size_charts)
        db.commit()

        print("4. Đang nạp Sản phẩm & Biến thể tồn kho...")
        p1 = Product(
            id="prod-vovinam-standard",
            name="Võ Phục Vovinam Tiêu Chuẩn Việt Võ Đạo",
            slug="vo-phuc-vovinam-tieu-chuan",
            martial_art_id="vovinam",
            category_id="vo_phuc",
            belt_rank="lam_dai",
            price=240000,
            original_price=280000,
            discount_percent=14,
            thumbnail="/mau_1.jpg",
            material="Vải Kaki 100% Cotton dệt chéo",
            description="Võ phục Vovinam chuẩn quy cách liên đoàn Việt Võ Đạo, đường chỉ may dằn chắc chắn, thấm hút mồ hôi tốt.",
            is_customizable=True,
            rating=4.9,
            review_count=58,
        )
        db.add(p1)
        db.flush()

        # Variants for p1
        variants_p1 = [
            ProductVariant(product_id=p1.id, size="Size 1", color="Xanh Vovinam", stock_quantity=20, price_adjustment=0),
            ProductVariant(product_id=p1.id, size="Size 2", color="Xanh Vovinam", stock_quantity=25, price_adjustment=0),
            ProductVariant(product_id=p1.id, size="Size 3 (S)", color="Xanh Vovinam", stock_quantity=15, price_adjustment=0),
            ProductVariant(product_id=p1.id, size="Size 4 (M)", color="Xanh Vovinam", stock_quantity=30, price_adjustment=10000),
            ProductVariant(product_id=p1.id, size="Size 5 (L)", color="Xanh Vovinam", stock_quantity=18, price_adjustment=15000),
            ProductVariant(product_id=p1.id, size="Size 6 (XL)", color="Xanh Vovinam", stock_quantity=10, price_adjustment=20000),
        ]
        db.add_all(variants_p1)

        p2 = Product(
            id="prod-taekwondo-dobok",
            name="Võ Phục Taekwondo Cổ Đen (WTF) Siêu Nhẹ",
            slug="vo-phuc-taekwondo-co-den",
            martial_art_id="taekwondo",
            category_id="vo_phuc",
            belt_rank="dai_den",
            price=320000,
            original_price=380000,
            discount_percent=16,
            thumbnail="/mau_1.jpg",
            material="Poly-Cotton dập gân tổ ong thoát khí",
            description="Võ phục Dobok Taekwondo cổ đen tiêu chuẩn thi đấu quốc tế WTF, cực kỳ thoáng khí.",
            is_customizable=True,
            rating=4.8,
            review_count=42,
        )
        db.add(p2)
        db.flush()

        variants_p2 = [
            ProductVariant(product_id=p2.id, size="Size 3 (S)", color="Trắng Cổ Đen", stock_quantity=15, price_adjustment=0),
            ProductVariant(product_id=p2.id, size="Size 4 (M)", color="Trắng Cổ Đen", stock_quantity=22, price_adjustment=0),
            ProductVariant(product_id=p2.id, size="Size 5 (L)", color="Trắng Cổ Đen", stock_quantity=12, price_adjustment=15000),
        ]
        db.add_all(variants_p2)

        p3 = Product(
            id="prod-karate-gi",
            name="Võ Phục Karatedo Kata Canvas 12oz",
            slug="vo-phuc-karatedo-kata",
            martial_art_id="karate",
            category_id="vo_phuc",
            belt_rank="dai_trang",
            price=290000,
            original_price=340000,
            discount_percent=15,
            thumbnail="/mau_1.jpg",
            material="Vải Canvas 12oz tạo tiếng vút đòn giòn giã",
            description="Võ phục Karate gi chất lượng cao dành cho quyền Kata và đối kháng Kumite.",
            is_customizable=True,
            rating=5.0,
            review_count=31,
        )
        db.add(p3)

        p4 = Product(
            id="prod-vct-den",
            name="Võ Phục Võ Cổ Truyền Màu Đen Cúc Bấm",
            slug="vo-phuc-co-truyen-den",
            martial_art_id="vo_co_truyen",
            category_id="vo_phuc",
            belt_rank="dai_den",
            price=230000,
            original_price=270000,
            discount_percent=15,
            thumbnail="/mau_1.jpg",
            material="Vải Kaki đen tuyền dệt chéo",
            description="Võ phục truyền thống cúc bấm kim loại chắc chắn, chuẩn môn phái cổ truyền.",
            is_customizable=True,
            rating=4.8,
            review_count=68,
        )
        db.add(p4)

        p5 = Product(
            id="prod-belt-vovinam",
            name="Đai Vovinam Lam Đai Tiêu Chuẩn Thêu Chữ Nổi",
            slug="dai-vovinam-lam-dai",
            martial_art_id="vovinam",
            category_id="dai",
            belt_rank="lam_dai",
            price=45000,
            original_price=60000,
            discount_percent=25,
            thumbnail="/mau_1.jpg",
            material="Vải đai nhiều lớp may 8 đường chỉ thẳng",
            description="Đai xanh lam bản 4.5cm thêu logo Liên đoàn sắc nét.",
            is_customizable=True,
            rating=4.9,
            review_count=198,
        )
        db.add(p5)
        db.commit()

        print("5. Đang nạp CLB Võ Đường & Đợt đặt hàng mẫu (USP #3)...")
        dojo = DojoClub(
            id="dojo-phudong",
            club_name="CLB Vovinam Phù Đổng",
            coach_name="Võ sư Nguyễn Văn Hùng",
            coach_phone="0987654321",
            martial_art_id="vovinam",
            address="Số 45 Lê Lợi, Quận 1, TP. Hồ Chí Minh",
        )
        db.add(dojo)
        db.flush()

        campaign = DojoOrderCampaign(
            id="camp-phudong2026",
            campaign_code="PHUDONG2026",
            dojo_id=dojo.id,
            campaign_title="Đợt Đặt Đồng Phục Khóa Hè – CLB Vovinam Phù Đổng",
            target_product_id="prod-vovinam-standard",
            deadline=datetime.now(timezone.utc) + timedelta(days=14),
            discount_tier_info="10 bộ: giảm 5%, 20 bộ: giảm 10%, 50 bộ: giảm 15%",
            shareable_link="http://localhost:3000/dojo/PHUDONG2026",
            status="OPEN",
        )
        db.add(campaign)
        db.flush()

        student_orders = [
            DojoStudentOrder(
                campaign_id=campaign.id,
                student_name="Trần Bảo Nam",
                parent_phone="0912345678",
                selected_size="Size 2",
                is_embroidered_name=True,
                embroidered_text="Bảo Nam",
                total_amount=260000,
                is_paid=True,
                payment_method="VietQR",
            ),
            DojoStudentOrder(
                campaign_id=campaign.id,
                student_name="Lê Gia Hân",
                parent_phone="0912345679",
                selected_size="Size 1",
                is_embroidered_name=True,
                embroidered_text="Gia Hân",
                total_amount=260000,
                is_paid=True,
                payment_method="VietQR",
            ),
            DojoStudentOrder(
                campaign_id=campaign.id,
                student_name="Nguyễn Minh Khang",
                parent_phone="0912345680",
                selected_size="Size 3 (S)",
                is_embroidered_name=False,
                embroidered_text=None,
                total_amount=240000,
                is_paid=False,
                payment_method="COD",
            ),
        ]
        db.add_all(student_orders)
        db.commit()

        print("6. Đang nạp Người dùng mẫu & Quản trị viên...")
        admin = User(
            phone="0999999999",
            full_name="Quản Trị Viên VÕ",
            hashed_password=hash_password("admin123"),
            role="admin",
            email="admin@vosport.vn",
        )
        customer = User(
            phone="0987654321",
            full_name="Nguyễn Văn Tuấn",
            hashed_password=hash_password("123456"),
            role="customer",
            email="tuan.nguyen@example.com",
            address="123 Võ Văn Tần, Q3, TP.HCM",
        )
        db.add_all([admin, customer])

        print("7. Đang nạp Voucher & Khuyến mãi...")
        vouchers = [
            Voucher(code="VOVINAM10", discount_type="PERCENT", discount_value=10, min_order_amount=300000),
            Voucher(code="TANBINH20", discount_type="FIXED", discount_value=20000, min_order_amount=200000),
        ]
        db.add_all(vouchers)

        print("8. Đang nạp Bài viết Blog hướng dẫn võ sinh...")
        posts = [
            BlogPost(
                title="Hướng Dẫn Buộc Đai Vovinam & Karate Đúng Chuẩn Liên Đoàn",
                slug="huong-dan-that-dai-vovinam-karate",
                summary="Chi tiết từng bước thắt đai võ thuật giúp đai chặt, cân xứng hai đầu và thẩm mỹ khi biểu diễn tấn pháp.",
                content="Nội dung hướng dẫn cách thắt đai võ thuật chi tiết...",
                thumbnail="/vovi.jpg",
                category="Kỹ Thuật Võ Đạo",
            ),
            BlogPost(
                title="Mẹo Giặt & Bảo Quản Võ Phục Cotton Không Ố Vàng",
                slug="meo-giat-bao-quan-vo-phuc",
                summary="Cách khử mồ hôi muối và phơi đúng cách để bộ võ phục luôn giữ màu và đứng form bền bỉ.",
                content="Nội dung mẹo giặt võ phục cotton...",
                thumbnail="/vovi.jpg",
                category="Cẩm Nang Võ Sinh",
            ),
        ]
        db.add_all(posts)
        db.commit()

        print("🎉 NẠP DỮ LIỆU BAN ĐẦU THÀNH CÔNG RỰC RỠ!")
    except Exception as e:
        db.rollback()
        print(f"Lỗi khi nạp dữ liệu: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed()
