from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend.models import ActivityLog, DeliveryLog, DeliveryEvent
from backend.schemas.log import ActivityLogResponse, DeliveryLogResponse

router = APIRouter(prefix="/api/logs", tags=["logs"])

@router.get("", response_model=List[ActivityLogResponse])
@router.get("/", response_model=List[ActivityLogResponse])
def get_logs_root(db: Session = Depends(get_db)):
    return db.query(ActivityLog).order_by(ActivityLog.id.desc()).limit(100).all()

@router.get("/activity", response_model=List[ActivityLogResponse])
def get_activity_logs(db: Session = Depends(get_db)):
    return db.query(ActivityLog).order_by(ActivityLog.id.desc()).limit(100).all()

@router.get("/delivery", response_model=List[DeliveryLogResponse])
def get_delivery_logs(db: Session = Depends(get_db)):
    rows = db.query(DeliveryLog).order_by(DeliveryLog.id.desc()).limit(500).all()
    return [{
        "id": row.id,
        "campaign_id": row.campaign_id,
        "account_id": row.account_id,
        "recipient": row.recipient,
        "sender_name": row.sender_name,
        "account_name": row.account.name if row.account else None,
        "campaign_name": row.campaign.name if row.campaign else None,
        "provider": row.provider,
        "status": row.status,
        "message_id": row.message_id,
        "error_info": row.error_info,
        "created_at": row.created_at,
    } for row in rows]

@router.delete("/delivery/{log_id}")
def delete_delivery_log(log_id: int, db: Session = Depends(get_db)):
    row = db.query(DeliveryLog).filter(DeliveryLog.id == log_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Delivery log not found.")
    db.delete(row)
    db.commit()
    return {"status": "success", "deleted_id": log_id}

@router.delete("/delivery")
def clear_delivery_logs(db: Session = Depends(get_db)):
    db.query(DeliveryEvent).delete(synchronize_session=False)
    deleted = db.query(DeliveryLog).delete(synchronize_session=False)
    db.commit()
    return {"status": "success", "deleted_count": deleted}
