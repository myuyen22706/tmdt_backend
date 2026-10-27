import asyncio
import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

from sqlalchemy.orm import declarative_base

logger = logging.getLogger("vo_ecommerce.database")

Base = declarative_base()

client: Optional[AsyncIOMotorClient] = None
db: Optional[AsyncIOMotorDatabase] = None
_is_mock: bool = False


async def connect_to_mongo():
    global client, db, _is_mock
    uri = settings.MONGODB_URI
    db_name = settings.MONGODB_DB_NAME

    try:
        logger.info(f"Đang kết nối MongoDB Atlas: {uri[:25]}.../db={db_name}")
        real_client = AsyncIOMotorClient(
            uri,
            serverSelectionTimeoutMS=4000,
            connectTimeoutMS=4000,
        )
        # Kiểm tra kết nối thực tế bằng lệnh ping, sau đó thử một lệnh cần quyền đọc:
        # ping vẫn thành công với MongoDB bật xác thực khi thiếu tài khoản, khiến mọi truy vấn sau đó lỗi.
        await real_client.admin.command("ping")
        await real_client[db_name].list_collection_names()
        client = real_client
        db = client[db_name]
        _is_mock = False
        logger.info(">>> Kết nối MongoDB Atlas thành công! <<<")
    except Exception as e:
        logger.warning(
            f"Chưa kết nối được MongoDB Atlas ({e}). "
            "Khởi chạy chế độ Mongomock nội bộ để hệ thống hoạt động ổn định và sẵn sàng chạy test. "
            "Sau khi điền chuỗi MONGODB_URI chính xác vào .env, hệ thống sẽ tự động lưu trữ trên MongoDB Atlas."
        )
        from mongomock_motor import AsyncMongoMockClient

        mock_client = AsyncMongoMockClient()
        client = mock_client
        db = client[db_name]
        _is_mock = True


async def close_mongo_connection():
    global client
    if client:
        client.close()
        logger.info("Đã đóng kết nối MongoDB.")


def get_database() -> AsyncIOMotorDatabase:
    global db
    if db is None:
        raise RuntimeError("Database chưa được khởi tạo. Hãy gọi connect_to_mongo() trước.")
    return db


async def get_db() -> AsyncIOMotorDatabase:
    """FastAPI Dependency cung cấp database MongoDB."""
    return get_database()


async def init_db():
    """Tạo các Index cần thiết trên MongoDB Atlas cho các collections."""
    database = get_database()

    try:
        # 1. Collection 'users'
        users_col = database["users"]
        await users_col.create_index("phone", unique=True)
        await users_col.create_index("email", unique=False, sparse=True)
        await users_col.create_index("role")

        # 2. Collection 'login_attempts' (Theo dõi brute force F01 / Mục 9)
        login_attempts_col = database["login_attempts"]
        await login_attempts_col.create_index("phone")
        await login_attempts_col.create_index("created_at")

        # 3. Collection 'products'
        products_col = database["products"]
        await products_col.create_index("slug", unique=True)
        await products_col.create_index("martial_art_id")
        await products_col.create_index("category_id")
        await products_col.create_index("price")
        await products_col.create_index([("is_active", 1), ("martial_art_id", 1), ("category_id", 1)])
        await products_col.create_index([("is_active", 1), ("created_at", -1)])
        await products_col.create_index("variants.sku")

        # 4. Collection 'orders'
        orders_col = database["orders"]
        await orders_col.create_index("order_code", unique=True)
        await orders_col.create_index("user_id")
        await orders_col.create_index("status")
        await orders_col.create_index("created_at")

        # 5. Collection 'clubs' & 'club_campaigns'
        clubs_col = database["clubs"]
        await clubs_col.create_index("slug", unique=True, sparse=True)
        campaigns_col = database["club_campaigns"]
        await campaigns_col.create_index("club_id")
        await campaigns_col.create_index("code", unique=True, sparse=True)

        # 6. Giỏ hàng được truy vấn theo user_id / session_id ở mọi thao tác
        carts_col = database["carts"]
        await carts_col.create_index("user_id", sparse=True)
        await carts_col.create_index("session_id", sparse=True)

        # 7. Voucher, đánh giá, bài viết
        await database["vouchers"].create_index("code")
        await database["reviews"].create_index("product_id")
        await database["blog_posts"].create_index("slug")

        logger.info("Khởi tạo và đánh chỉ mục (indexes) MongoDB Atlas thành công.")
    except Exception as e:
        logger.warning(f"Lỗi khi khởi tạo indexes: {e}")
