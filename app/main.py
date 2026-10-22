from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import api_router
from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection, init_db, get_db
from app.core.exceptions import AppException
from app.core.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.modules.seo.router import generate_robots_txt, generate_sitemap


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo kết nối MongoDB và tạo các index
    await connect_to_mongo()
    await init_db()
    if settings.AUTO_SEED_DB:
        try:
            database = await get_db()
            users_count = await database["users"].count_documents({})
            products_count = await database["products"].count_documents({})
            if users_count == 0 or products_count == 0:
                from app.seed_mongo import seed_data
                await seed_data(target_db=database)
        except Exception as e:
            print(f"Auto-seed warning: {e}")
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
