from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timezone
from app.core.database import get_db
from app.core.responses import APIResponse
from app.modules.dojos.schemas import DojoCampaignCreate, StudentOrderCreate
from app.modules.dojos.models import DojoClub, DojoOrderCampaign, DojoStudentOrder


router = APIRouter(prefix="/dojos", tags=["Dojo / Coach Ordering (USP #3 B2B2C)"])


@router.get("/campaigns")
async def list_campaigns(db: Session = Depends(get_db)):
    """Lấy danh sách các đợt đặt hàng đồng phục võ đường từ Database."""
    campaigns = db.query(DojoOrderCampaign).all()
    result = []
    for c in campaigns:
        result.append({
            "id": c.id,
            "campaign_code": c.campaign_code,
            "dojo_name": c.dojo.club_name if c.dojo else "CLB Võ Thuật",
            "coach_name": c.dojo.coach_name if c.dojo else "HLV Phụ trách",
            "phone": c.dojo.coach_phone if c.dojo else "",
            "martial_art": c.dojo.martial_art_id if c.dojo else "vovinam",
            "campaign_title": c.campaign_title,
            "target_product_id": c.target_product_id,
            "deadline": c.deadline,
            "discount_tier_info": c.discount_tier_info,
            "shareable_link": c.shareable_link,
            "total_ordered_count": len(c.student_orders),
            "orders": [
                {
                    "id": o.id,
                    "student_name": o.student_name,
                    "parent_phone": o.parent_phone,
                    "selected_size": o.selected_size,
                    "is_embroidered_name": o.is_embroidered_name,
                    "embroidered_text": o.embroidered_text,
                    "total_amount": float(o.total_amount),
                    "is_paid": o.is_paid,
                    "payment_method": o.payment_method,
                    "created_at": o.created_at,
                }
                for o in c.student_orders
            ],
            "created_at": c.created_at,
        })

    return APIResponse(
        success=True,
        message="Lấy danh sách đợt đặt hàng thành công",
        data=result,
    )


@router.post("/campaigns")
async def create_campaign(data: DojoCampaignCreate, db: Session = Depends(get_db)):
    """HLV / Võ đường tạo đợt đặt hàng đồng phục mới và lưu vào SQL Server."""
    code = f"DOJO-{uuid.uuid4().hex[:6].upper()}"

    # Create club
    club = DojoClub(
        club_name=data.dojo_name,
        coach_name=data.coach_name,
        coach_phone=data.phone,
        martial_art_id=data.martial_art,
        logo_url=data.logo_url,
    )
    db.add(club)
    db.flush()

    # Create campaign
    camp = DojoOrderCampaign(
        campaign_code=code,
        dojo_id=club.id,
        campaign_title=data.campaign_title,
        target_product_id=data.target_product_id,
        deadline=data.deadline,
        discount_tier_info=data.discount_tier_info,
        shareable_link=f"http://localhost:3000/dojo/{code}",
        status="OPEN",
    )
    db.add(camp)
    db.commit()
    db.refresh(camp)

    return APIResponse(
        success=True,
        message="Tạo đợt đặt hàng đồng phục thành công",
        data={
            "id": camp.id,
            "campaign_code": camp.campaign_code,
            "campaign_title": camp.campaign_title,
            "shareable_link": camp.shareable_link,
            "deadline": camp.deadline,
        },
    )


@router.get("/campaigns/{campaign_code}")
async def get_campaign_by_code(campaign_code: str, db: Session = Depends(get_db)):
    """Phụ huynh hoặc HLV truy cập qua link đặt hàng riêng (USP #3)."""
    camp = db.query(DojoOrderCampaign).filter(
        DojoOrderCampaign.campaign_code == campaign_code.upper()
    ).first()

    if not camp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đợt đặt hàng")

    data = {
        "id": camp.id,
        "campaign_code": camp.campaign_code,
        "dojo_name": camp.dojo.club_name if camp.dojo else "",
        "coach_name": camp.dojo.coach_name if camp.dojo else "",
        "phone": camp.dojo.coach_phone if camp.dojo else "",
        "campaign_title": camp.campaign_title,
        "deadline": camp.deadline,
        "discount_tier_info": camp.discount_tier_info,
        "shareable_link": camp.shareable_link,
        "total_ordered_count": len(camp.student_orders),
        "orders": [
            {
                "id": o.id,
                "student_name": o.student_name,
                "parent_phone": o.parent_phone,
                "selected_size": o.selected_size,
                "is_embroidered_name": o.is_embroidered_name,
                "embroidered_text": o.embroidered_text,
                "total_amount": float(o.total_amount),
                "is_paid": o.is_paid,
                "payment_method": o.payment_method,
            }
            for o in camp.student_orders
        ],
    }

    return APIResponse(
        success=True,
        message="Lấy thông tin đợt đặt hàng thành công",
        data=data,
    )


@router.post("/campaigns/{campaign_code}/order")
async def submit_student_order(
    campaign_code: str,
    order: StudentOrderCreate,
    db: Session = Depends(get_db),
):
    """Phụ huynh đặt võ phục cho con theo đợt của võ đường."""
    camp = db.query(DojoOrderCampaign).filter(
        DojoOrderCampaign.campaign_code == campaign_code.upper()
    ).first()

    if not camp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đợt đặt hàng")

    total = 260000 if order.is_embroidered_name else 240000
    new_student_order = DojoStudentOrder(
        campaign_id=camp.id,
        student_name=order.student_name,
        parent_phone=order.parent_phone,
        selected_size=order.selected_size,
        is_embroidered_name=order.is_embroidered_name,
        embroidered_text=order.embroidered_text,
        total_amount=total,
        is_paid=order.payment_method == "VietQR",
        payment_method=order.payment_method,
    )
    db.add(new_student_order)
    db.commit()
    db.refresh(new_student_order)

    return APIResponse(
        success=True,
        message="Ghi nhận đơn đặt hàng võ sinh thành công",
        data={
            "id": new_student_order.id,
            "student_name": new_student_order.student_name,
            "selected_size": new_student_order.selected_size,
            "total_amount": float(new_student_order.total_amount),
            "is_paid": new_student_order.is_paid,
        },
    )
