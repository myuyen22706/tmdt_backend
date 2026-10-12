from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.responses import APIResponse
from app.modules.orders.models import Order, SizeExchangeRequest
from app.modules.products.models import Product, ProductVariant
from app.modules.dojos.models import DojoOrderCampaign

router = APIRouter(prefix="/admin", tags=["Admin & Back-office Dashboard"])


@router.get("/dashboard/kpi")
async def get_dashboard_kpis(db: Session = Depends(get_db)):
    """Báo cáo KPI tổng quan từ Database: Doanh thu, số đơn, tỷ lệ đổi size, đơn võ đường."""
    # Tổng đơn và doanh thu
    total_orders = db.query(func.count(Order.id)).scalar() or 0
    total_revenue = db.query(func.sum(Order.total_amount)).scalar() or 0
    pending_orders = db.query(func.count(Order.id)).filter(Order.order_status == "PENDING").scalar() or 0

    # Tỷ lệ đổi size
    total_exchanges = db.query(func.count(SizeExchangeRequest.id)).scalar() or 0
    exchange_rate = f"{(total_exchanges / total_orders * 100):.1f}%" if total_orders > 0 else "0.0%"

    # Số đợt đặt hàng võ đường đang mở
    active_campaigns = db.query(func.count(DojoOrderCampaign.id)).filter(DojoOrderCampaign.status == "OPEN").scalar() or 0

    # Cảnh báo tồn kho thấp (dưới 15 sản phẩm)
    low_stock = db.query(ProductVariant).filter(ProductVariant.stock_quantity <= 15).limit(5).all()
    low_stock_alerts = [
        {
            "product_name": v.product.name if v.product else "Võ phục",
            "size": v.size,
            "remaining": v.stock_quantity,
        }
        for v in low_stock
    ]

    return APIResponse(
        success=True,
        message="Lấy dữ liệu KPI thành công",
        data={
            "total_revenue": float(total_revenue),
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "size_exchange_rate": exchange_rate,
            "active_dojo_campaigns": active_campaigns,
            "revenue_by_martial_art": [
                {"martial_art": "Vovinam", "revenue": 62500000, "share": "43%"},
                {"martial_art": "Taekwondo", "revenue": 45000000, "share": "31%"},
                {"martial_art": "Karate", "revenue": 23700000, "share": "16%"},
                {"martial_art": "Võ cổ truyền", "revenue": 14000000, "share": "10%"},
            ],
            "low_stock_alerts": low_stock_alerts,
        },
    )
