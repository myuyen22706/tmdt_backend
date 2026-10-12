from fastapi import APIRouter
from app.core.responses import APIResponse

router = APIRouter(prefix="/admin", tags=["Admin & Back-office Dashboard"])


@router.get("/dashboard/kpi")
async def get_dashboard_kpis():
    """Báo cáo KPI tổng quan: Doanh thu, số đơn, tỷ lệ đổi size, đơn võ đường."""
    return APIResponse(
        success=True,
        message="Lấy dữ liệu KPI thành công",
        data={
            "total_revenue": 145200000,
            "total_orders": 348,
            "pending_orders": 12,
            "size_exchange_rate": "2.1%",
            "active_dojo_campaigns": 4,
            "revenue_by_martial_art": [
                {"martial_art": "Vovinam", "revenue": 62500000, "share": "43%"},
                {"martial_art": "Taekwondo", "revenue": 45000000, "share": "31%"},
                {"martial_art": "Karate", "revenue": 23700000, "share": "16%"},
                {"martial_art": "Võ cổ truyền", "revenue": 14000000, "share": "10%"},
            ],
            "low_stock_alerts": [
                {"product_name": "Võ Phục Vovinam Tiêu Chuẩn", "size": "Size 5 (L)", "remaining": 3},
                {"product_name": "Võ Phục Karate Kata", "size": "Size 3 (S)", "remaining": 2},
            ],
        },
    )
