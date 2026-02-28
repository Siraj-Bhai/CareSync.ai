from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from database import get_db
from models import User, RiskHistory, Session as DBSession, PatientCreate
from auth import get_current_clinician
from datetime import datetime
import uuid

router = APIRouter()


@router.get("/")
async def get_all_patients(
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    from models import Clinician
    clin_result = await db.execute(select(Clinician).where(Clinician.id == clinician_id))
    clinician = clin_result.scalars().first()
    if clinician and clinician.role == "admin":
        result = await db.execute(select(User))
    else:
        result = await db.execute(select(User).where(User.clinician_id == clinician_id))
    patients = result.scalars().all()
    out = []
    for p in patients:
        rh = await db.execute(
            select(RiskHistory).where(RiskHistory.user_id == p.id)
            .order_by(desc(RiskHistory.date)).limit(1)
        )
        latest = rh.scalars().first()
        out.append({
            "id": p.id, "name": p.name, "age": p.age,
            "risk_score": latest.score if latest else 0,
            "risk_level": latest.risk_level if latest else "LOW",
            "last_active": latest.date.isoformat() if latest else None,
            "emergency_contact": p.emergency_contact,
        })
    return out


@router.get("/{patient_id}")
async def get_patient(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    result = await db.execute(select(User).where(User.id == patient_id))
    patient = result.scalars().first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {
        "id": patient.id, "name": patient.name, "age": patient.age,
        "clinician_id": patient.clinician_id,
        "emergency_contact": patient.emergency_contact,
        "created_at": patient.created_at.isoformat() if patient.created_at else None
    }


@router.get("/{patient_id}/sessions")
async def get_patient_sessions(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    result = await db.execute(
        select(DBSession).where(DBSession.user_id == patient_id)
        .order_by(desc(DBSession.start_time))
    )
    sessions = result.scalars().all()
    return [
        {"id": s.id, "start_time": s.start_time.isoformat() if s.start_time else None,
         "end_time": s.end_time.isoformat() if s.end_time else None,
         "overall_risk_score": s.overall_risk_score, "status": s.status}
        for s in sessions
    ]


@router.get("/{patient_id}/risk-history")
async def get_risk_history(
    patient_id: str,
    days: int = 14,
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    result = await db.execute(
        select(RiskHistory).where(RiskHistory.user_id == patient_id)
        .order_by(RiskHistory.date).limit(days)
    )
    history = result.scalars().all()
    return [
        {"date": h.date.isoformat(), "score": h.score, "risk_level": h.risk_level,
         "predicted_score": h.predicted_score, "factors": h.factors}
        for h in history
    ]


@router.patch("/{patient_id}/emergency-contact")
async def update_emergency_contact(
    patient_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    result = await db.execute(select(User).where(User.id == patient_id))
    patient = result.scalars().first()
    if not patient:
        raise HTTPException(status_code=404, detail="User not found")
    patient.emergency_contact = body.get("emergency_contact", patient.emergency_contact)
    await db.commit()
    return {"emergency_contact": patient.emergency_contact}


@router.post("/")
async def create_patient(
    patient: PatientCreate,
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    new_patient = User(
        id=str(uuid.uuid4()),
        name=patient.name,
        age=patient.age,
        clinician_id=clinician_id,
        emergency_contact=patient.emergency_contact,
        created_at=datetime.utcnow()
    )
    db.add(new_patient)
    await db.commit()
    return {"id": new_patient.id, "name": new_patient.name, "message": "Patient created"}
