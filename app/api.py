from fastapi import APIRouter
from app.modules.admin.router import router as admin_router
from app.modules.auth.router import router as auth_router
from app.modules.blog.router import router as blog_router
from app.modules.cart.router import router as cart_router
from app.modules.dojos.router import router as dojos_router
from app.modules.orders.router import router as orders_router
from app.modules.products.router import router as products_router
from app.modules.promotions.router import router as promotions_router
from app.modules.reviews.router import router as reviews_router
from app.modules.size_advisor.router import router as size_advisor_router

api_router = APIRouter()

# Register domain modules
api_router.include_router(products_router)
api_router.include_router(size_advisor_router)
api_router.include_router(dojos_router)
api_router.include_router(cart_router)
api_router.include_router(orders_router)
api_router.include_router(auth_router)
api_router.include_router(promotions_router)
api_router.include_router(reviews_router)
api_router.include_router(blog_router)
api_router.include_router(admin_router)
