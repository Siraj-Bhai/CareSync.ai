from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from database import get_db
from models import RiskHistory, RiskAnalyzeRequest
from agents.detection import detect_risk
from agents.memory import predict_crisis
from auth import get_current_clinician

router = APIRouter()


@router.get("/{user_id}/current")
async def get_current_risk(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    result = await db.execute(
        select(RiskHistory).where(RiskHistory.user_id == user_id)
        .order_by(desc(RiskHistory.date)).limit(1)
    )
    latest = result.scalars().first()
    if not latest:
        raise HTTPException(status_code=404, detail="No risk data found")
    return {
        "score": latest.score, "risk_level": latest.risk_level,
        "factors": latest.factors, "predicted_score": latest.predicted_score,
        "date": latest.date.isoformat()
    }


@router.get("/{user_id}/trend")
async def get_risk_trend(
    user_id: str,
    days: int = 14,
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    result = await db.execute(
        select(RiskHistory).where(RiskHistory.user_id == user_id)
        .order_by(RiskHistory.date).limit(days)
    )
    history = result.scalars().all()
    return [
        {"date": h.date.isoformat(), "score": h.score,
         "risk_level": h.risk_level, "predicted_score": h.predicted_score}
        for h in history
    ]


@router.get("/{user_id}/predict")
async def predict_crisis_endpoint(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    clinician_id: str = Depends(get_current_clinician)
):
    result = await db.execute(
        select(RiskHistory).where(RiskHistory.user_id == user_id)
        .order_by(RiskHistory.date).limit(14)
    )
    history = result.scalars().all()
    scores = [h.score for h in history]
    return await predict_crisis(user_id, scores)


@router.post("/analyze")
async def analyze_message(
    request: RiskAnalyzeRequest,
    clinician_id: str = Depends(get_current_clinician)
):
    return await detect_risk(request.message)
