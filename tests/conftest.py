import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from mongomock_motor import AsyncMongoMockClient

import app.core.database as database_module
from app.core.database import get_db, init_db
from app.core.middleware import RateLimitMiddleware
from app.main import app


@pytest.fixture(autouse=True)
def disable_real_email(monkeypatch):
    """Không bao giờ gửi email thật khi chạy test, kể cả khi .env có RESEND_API_KEY."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Reset bộ nhớ Rate Limiting trước mỗi test case để tránh ảnh hưởng chéo."""
    RateLimitMiddleware.reset()


@pytest_asyncio.fixture(scope="function")
async def mock_mongo_db():
    """Tạo database MongoDB giả lập trên bộ nhớ cho từng test case độc lập."""
    mock_client = AsyncMongoMockClient()
    test_db = mock_client["test_vo_ecommerce"]
    
    # Gán vào database module
    database_module.client = mock_client
    database_module.db = test_db
    
    # Khởi tạo indexes
    await init_db()
    
    yield test_db
    
    # Cleanup sau test
    mock_client.close()


@pytest_asyncio.fixture(scope="function")
async def client(mock_mongo_db):
    """Cung cấp AsyncClient của httpx để gọi API FastAPI trong quá trình test."""
    async def override_get_db():
        return mock_mongo_db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()
