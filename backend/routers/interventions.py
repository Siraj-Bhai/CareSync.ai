from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from database import get_db
from models import Intervention, User, Clinician, InterventionRequest
from agents.intervention import send_clinician_sms, book_therapy_appointment, get_crisis_resources
from auth import get_current_clinician
from datetime import datetime
import uuid

router = APIRouter()


@router.post("/alert")
async def trigger_alert(
    request: InterventionRequest,
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    user_result = await db.execute(select(User).where(User.id == request.user_id))
    user = user_result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    clin_result = await db.execute(select(Clinician).where(Clinician.id == clinician_id))
    clinician = clin_result.scalars().first()
    phone = clinician.phone if clinician else ""

    result = await send_clinician_sms(phone, user.name, 0, request.message or "Manual alert triggered")

    db.add(Intervention(
        id=str(uuid.uuid4()), user_id=request.user_id,
        type="sms", triggered_by="clinician", outcome=result, timestamp=datetime.utcnow()
    ))
    await db.commit()
    return {"status": result}


@router.post("/sms")
async def send_sms(
    request: InterventionRequest,
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    result = await send_clinician_sms(
        request.recipient or "", "Patient", 0, request.body or ""
    )
    db.add(Intervention(
        id=str(uuid.uuid4()), user_id=request.user_id,
        type="sms", triggered_by="clinician", outcome=result, timestamp=datetime.utcnow()
    ))
    await db.commit()
    return {"status": result}


@router.post("/book")
async def book_appointment(
    request: InterventionRequest,
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    result = await book_therapy_appointment(request.user_id, request.urgency or "regular")
    db.add(Intervention(
        id=str(uuid.uuid4()), user_id=request.user_id,
        type="booking", triggered_by="clinician", outcome=result, timestamp=datetime.utcnow()
    ))
    await db.commit()
    return {"booking_uid": result}


@router.post("/escalate")
async def escalate_emergency(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    resources = get_crisis_resources("IMMINENT")
    db.add(Intervention(
        id=str(uuid.uuid4()), user_id=user_id,
        type="escalation", triggered_by="clinician", outcome="escalated", timestamp=datetime.utcnow()
    ))
    await db.commit()
    return {"status": "escalated", "resources": resources}


@router.get("/{user_id}")
async def get_intervention_history(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    result = await db.execute(
        select(Intervention).where(Intervention.user_id == user_id)
        .order_by(desc(Intervention.timestamp))
    )
    interventions = result.scalars().all()
    return [
        {"id": i.id, "type": i.type, "triggered_by": i.triggered_by,
         "outcome": i.outcome, "timestamp": i.timestamp.isoformat() if i.timestamp else None}
        for i in interventions
    ]
