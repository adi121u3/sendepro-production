from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from backend.database import get_db
from backend.models import Campaign, CampaignRecipient, ActivityLog, Template, Lead, Account
from backend.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignResponse
from backend.campaign.engine import CampaignEngine

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


def _normalize_rotation(mode: str | None) -> str:
    value = (mode or "round_robin").strip().lower()
    if value not in {"round_robin", "random", "failover"}:
        return "round_robin"
    return value


def _normalize_route(route: str | None) -> str:
    value = (route or "auto").strip().lower()
    if value not in {"auto", "smtp", "zeptomail_smtp", "zeptomail_api"}:
        return "auto"
    return value


@router.get("", response_model=List[CampaignResponse])
def get_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).order_by(Campaign.id.desc()).all()
    return [CampaignResponse.from_orm(c) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignResponse.from_orm(campaign)


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    lead_ids = list(dict.fromkeys(payload.lead_ids))
    template_ids = list(dict.fromkeys(payload.template_ids))
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="Campaign name cannot be blank.")
    if payload.account_id and not db.query(Account.id).filter(Account.id == payload.account_id).first():
        raise HTTPException(status_code=400, detail="Selected sender account does not exist.")
    existing_lead_ids = {row[0] for row in db.query(Lead.id).filter(Lead.id.in_(lead_ids)).all()} if lead_ids else set()
    missing_leads = sorted(set(lead_ids) - existing_lead_ids)
    if missing_leads:
        raise HTTPException(status_code=400, detail=f"Unknown lead IDs: {missing_leads}")
    templates_list = []
    if template_ids:
        templates_list = db.query(Template).filter(Template.id.in_(template_ids)).all()
        if len(templates_list) != len(template_ids):
            raise HTTPException(status_code=400, detail="One or more selected templates do not exist.")
    elif payload.template_id:
        template = db.query(Template).filter(Template.id == payload.template_id).first()
        if not template:
            raise HTTPException(status_code=400, detail="Selected template does not exist.")
        templates_list = [template]
    total_recipients = len(lead_ids)

    delay = max(1, int(payload.delay_seconds or 30))
    jitter = max(0, int(payload.jitter_seconds if payload.jitter_seconds is not None else 2))
    retries = max(0, int(payload.max_retries if payload.max_retries is not None else 3))

    campaign = Campaign(
        name=payload.name,
        tag=payload.tag or "Marketing",
        status="draft",
        template_id=payload.template_id,
        account_id=payload.account_id,
        delay_seconds=delay,
        jitter_seconds=jitter,
        max_retries=retries,
        rotation_mode=_normalize_rotation(payload.rotation_mode),
        reply_to=(payload.reply_to or "").strip() or None,
        delivery_route=_normalize_route(payload.delivery_route),
        total_recipients=total_recipients,
        sent_count=0,
        failed_count=0,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    if templates_list:
        campaign.templates = templates_list
        if not campaign.template_id:
            campaign.template_id = templates_list[0].id
        db.commit()

    if lead_ids:
        for lead_id in lead_ids:
            recipient = CampaignRecipient(
                campaign_id=campaign.id,
                lead_id=lead_id,
                status="queued",
            )
            db.add(recipient)
        db.commit()

    log = ActivityLog(
        event_type="campaign_created",
        severity="info",
        message=(
            f"Campaign '{campaign.name}' created with {total_recipients} recipients, "
            f"delay={delay}s, rotation={campaign.rotation_mode}, route={campaign.delivery_route}."
        ),
        entity_id=campaign.id,
        campaign_id=campaign.id,
    )
    db.add(log)
    db.commit()

    return CampaignResponse.from_orm(campaign)


@router.delete("/{campaign_id}", status_code=status.HTTP_200_OK)
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    try:
        CampaignEngine.stop_campaign(campaign.id)
    except Exception:
        pass

    name = campaign.name

    db.query(CampaignRecipient).filter(
        CampaignRecipient.campaign_id == campaign_id
    ).delete(synchronize_session=False)

    db.delete(campaign)

    log = ActivityLog(
        event_type="campaign_deleted",
        severity="info",
        message=f"Campaign '{name}' (id={campaign_id}) deleted.",
        entity_id=campaign_id,
        campaign_id=campaign_id,
    )
    db.add(log)
    db.commit()

    return {"status": "success", "message": f"Campaign {campaign_id} deleted."}

@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(campaign_id: int, payload: CampaignUpdate, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status == "running":
        raise HTTPException(status_code=409, detail="Pause the campaign before editing it.")
    values = payload.model_dump(exclude_unset=True)
    template_ids = values.pop("template_ids", None)
    if values.get("account_id") is not None and not db.query(Account.id).filter(Account.id == values["account_id"]).first():
        raise HTTPException(status_code=400, detail="Selected sender account does not exist.")
    if "name" in values and not str(values["name"] or "").strip():
        raise HTTPException(status_code=422, detail="Campaign name cannot be blank.")
    if "rotation_mode" in values: values["rotation_mode"] = _normalize_rotation(values["rotation_mode"])
    if "delivery_route" in values: values["delivery_route"] = _normalize_route(values["delivery_route"])
    if "reply_to" in values: values["reply_to"] = str(values["reply_to"] or "").strip() or None
    for numeric in ("delay_seconds", "jitter_seconds", "max_retries"):
        if numeric in values and values[numeric] is not None:
            values[numeric] = max(0 if numeric != "delay_seconds" else 1, int(values[numeric]))
    for key, value in values.items(): setattr(campaign, key, value)
    if template_ids is not None:
        unique_ids = list(dict.fromkeys(template_ids))
        rows = db.query(Template).filter(Template.id.in_(unique_ids)).all() if unique_ids else []
        if len(rows) != len(unique_ids): raise HTTPException(status_code=400, detail="One or more selected templates do not exist.")
        campaign.templates = rows
        campaign.template_id = unique_ids[0] if unique_ids else None
    db.add(ActivityLog(event_type="campaign_updated", severity="info", message=f"Campaign '{campaign.name}' updated.", entity_id=campaign.id, campaign_id=campaign.id))
    db.commit(); db.refresh(campaign)
    return CampaignResponse.from_orm(campaign)


@router.api_route("/{campaign_id}/status", methods=["PATCH", "POST"], response_model=CampaignResponse)
async def update_campaign_status(campaign_id: int, request: Request, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    new_status = body.get("status") or request.query_params.get("status")
    if not new_status or new_status not in ["draft", "running", "paused", "completed", "stopped"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    # Apply status first and COMMIT so the worker thread sees "running"
    # in its own DB session (avoids race: worker starts, reads old draft/stopped).
    campaign.status = new_status
    if new_status == "running":
        if not campaign.started_at:
            campaign.started_at = datetime.utcnow()
    elif new_status == "paused":
        campaign.paused_at = datetime.utcnow()
    elif new_status == "completed":
        campaign.completed_at = datetime.utcnow()
    elif new_status == "stopped":
        campaign.stopped_at = datetime.utcnow()

    db.commit()
    db.refresh(campaign)

    # Start / stop worker AFTER the status is durable
    if new_status == "running":
        CampaignEngine.start_campaign(campaign.id)
    elif new_status == "paused":
        try:
            CampaignEngine.pause_campaign(campaign.id)
        except Exception:
            pass
    elif new_status == "stopped":
        try:
            CampaignEngine.stop_campaign(campaign.id)
        except Exception:
            pass

    log = ActivityLog(
        event_type=f"campaign_{new_status}",
        severity="info",
        message=f"Campaign '{campaign.name}' status updated to {new_status}.",
        entity_id=campaign.id,
        campaign_id=campaign.id,
    )
    db.add(log)
    db.commit()

    return CampaignResponse.from_orm(campaign)
