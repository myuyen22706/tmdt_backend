from typing import List
from fastapi import APIRouter, HTTPException, status
from app.core.responses import APIResponse
from app.modules.dojos.schemas import (
    DojoCampaignCreate,
    DojoCampaignResponse,
    StudentOrderCreate,
    StudentOrderItem,
)
from app.modules.dojos.service import DojoService

router = APIRouter(prefix="/dojos", tags=["Dojo / Coach Ordering (USP #3 B2B2C)"])


@router.get("/campaigns", response_model=APIResponse[List[DojoCampaignResponse]])
async def list_campaigns():
    """Danh sách các đợt đặt hàng đồng phục võ đường."""
    return APIResponse(
        success=True,
        message="Lấy danh sách đợt đặt hàng thành công",
        data=DojoService.get_campaigns(),
    )


@router.post("/campaigns", response_model=APIResponse[DojoCampaignResponse])
async def create_campaign(data: DojoCampaignCreate):
    """HLV / Võ đường tạo đợt đặt hàng đồng phục mới."""
    camp = DojoService.create_campaign(data)
    return APIResponse(
        success=True,
        message="Tạo đợt đặt hàng đồng phục thành công",
        data=camp,
    )


@router.get("/campaigns/{campaign_code}", response_model=APIResponse[DojoCampaignResponse])
async def get_campaign_by_code(campaign_code: str):
    """Phụ huynh hoặc HLV truy cập qua link đặt hàng riêng (USP #3)."""
    camp = DojoService.get_by_code(campaign_code)
    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đợt đặt hàng với mã này",
        )
    return APIResponse(
        success=True,
        message="Lấy thông tin đợt đặt hàng thành công",
        data=camp,
    )


@router.post("/campaigns/{campaign_code}/order", response_model=APIResponse[StudentOrderItem])
async def submit_student_order(campaign_code: str, order: StudentOrderCreate):
    """Phụ huynh đặt võ phục cho con theo đợt của võ đường."""
    result = DojoService.add_student_order(campaign_code, order)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy đợt đặt hàng",
        )
    return APIResponse(
        success=True,
        message="Ghi nhận đơn đặt hàng võ sinh thành công",
        data=result,
    )
