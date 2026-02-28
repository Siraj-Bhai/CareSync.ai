from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from database import get_db
from models import User, RiskHistory, Intervention
from auth import get_current_clinician

router = APIRouter()


@router.get("/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    # Admin sees all users; filter by clinician_id only if patients are explicitly assigned
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
            .order_by(desc(RiskHistory.date)).limit(7)
        )
        history = rh.scalars().all()
        latest = history[0] if history else None
        trend = "stable"
        if len(history) >= 2:
            if history[0].score > history[-1].score + 5:
                trend = "rising"
            elif history[0].score < history[-1].score - 5:
                trend = "falling"
        out.append({
            "id": p.id, "name": p.name, "age": p.age,
            "risk_score": latest.score if latest else 0,
            "risk_level": latest.risk_level if latest else "LOW",
            "trend": trend,
            "last_active": latest.date.isoformat() if latest else None,
            "trend_data": [{"score": h.score, "date": h.date.isoformat()} for h in reversed(history)]
        })
    out.sort(key=lambda x: x["risk_score"], reverse=True)
    return out


@router.get("/critical")
async def get_critical_patients(
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    overview = await get_overview(db, clinician_id)
    return [p for p in overview if p["risk_level"] in ["HIGH", "CRISIS", "IMMINENT"]]


@router.get("/analytics")
async def get_analytics(
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    from models import Clinician
    clin_result = await db.execute(select(Clinician).where(Clinician.id == clinician_id))
    clinician = clin_result.scalars().first()
    if clinician and clinician.role == "admin":
        patients_result = await db.execute(select(User))
    else:
        patients_result = await db.execute(select(User).where(User.clinician_id == clinician_id))
    patient_ids = [p.id for p in patients_result.scalars().all()]

    if not patient_ids:
        return {"crisis_events": 0, "avg_risk": 0, "intervention_outcomes": {}, "top_signals": []}

    # Crisis events count
    crisis_result = await db.execute(
        select(func.count(RiskHistory.id)).where(
            RiskHistory.user_id.in_(patient_ids),
            RiskHistory.risk_level.in_(["CRISIS", "IMMINENT"])
        )
    )
    crisis_count = crisis_result.scalar() or 0

    # Average risk
    avg_result = await db.execute(
        select(func.avg(RiskHistory.score)).where(RiskHistory.user_id.in_(patient_ids))
    )
    avg_risk = round(avg_result.scalar() or 0, 1)

    # Intervention outcomes
    int_result = await db.execute(
        select(Intervention).where(Intervention.user_id.in_(patient_ids))
    )
    interventions = int_result.scalars().all()
    outcomes = {}
    for i in interventions:
        outcomes[i.type] = outcomes.get(i.type, 0) + 1

    # Risk over time (last 14 days aggregated)
    rh_result = await db.execute(
        select(RiskHistory).where(RiskHistory.user_id.in_(patient_ids))
        .order_by(RiskHistory.date).limit(100)
    )
    all_history = rh_result.scalars().all()

    return {
        "crisis_events": crisis_count,
        "avg_risk": avg_risk,
        "total_patients": len(patient_ids),
        "intervention_outcomes": outcomes,
        "risk_timeline": [
            {"date": h.date.isoformat(), "score": h.score, "level": h.risk_level}
            for h in all_history[-30:]
        ]
    }
