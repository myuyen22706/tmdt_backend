from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from app.api import api_router
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection, init_db, get_db
from app.core.exceptions import AppException
from app.core.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.modules.seo.router import generate_robots_txt, generate_sitemap


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Mục 9: không cho chạy production với SECRET_KEY mặc định (ai đọc mã nguồn cũng giả mạo được JWT admin)
    if not settings.DEBUG and settings.insecure_secret_key():
        raise RuntimeError(
            "SECRET_KEY chưa được cấu hình an toàn. Đặt biến môi trường SECRET_KEY ngẫu nhiên >= 32 ký tự "
            "(ví dụ: python -c \"import secrets; print(secrets.token_urlsafe(48))\"), hoặc DEBUG=True khi chạy local."
        )
    # Khởi tạo kết nối MongoDB và tạo các index
    await connect_to_mongo()
    await init_db()
    yield
    await close_mongo_connection()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API cho Nền tảng TMĐT Võ phục & Phụ kiện võ thuật 'VÕ' (B2C & B2B2C)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Nén phản hồi JSON lớn (danh mục sản phẩm, báo cáo) để tải nhanh hơn trên mạng di động
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Mục 9: Security Headers & Rate Limiting Middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

# Setup CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_origin_regex=settings.BACKEND_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "error_code": exc.error_code,
            "detail": exc.detail,
        },
    )


# Root health check endpoint
@app.get("/", tags=["Health Check"])
async def root():
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "docs_url": "/docs",
        "api_v1": settings.API_V1_STR,
    }


# Include all v1 API endpoints
app.include_router(api_router, prefix=settings.API_V1_STR)


# F24: Root endpoints cho Web Crawlers & Search Engines (SEO)
@app.get("/sitemap.xml", include_in_schema=False)
async def root_sitemap(response: Response, db=Depends(get_db)):
    return await generate_sitemap(db=db)


@app.get("/robots.txt", include_in_schema=False)
async def root_robots():
    return await generate_robots_txt()
