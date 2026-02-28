from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import ChatRequest, User, Session as DBSession, Message, RiskHistory, Intervention, Clinician
from agents.orchestrator import process_message
from aws_config import upload_to_s3, _aws_session
from datetime import datetime, timezone
import uuid, os, io

router = APIRouter()
_sio = None

def set_sio(sio_instance):
    global _sio
    _sio = sio_instance


@router.post("/message")
async def send_message(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    # Get patient info
    user_result = await db.execute(select(User).where(User.id == request.user_id))
    user = user_result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    clinician_phone = ""
    if user.clinician_id:
        clin_result = await db.execute(select(Clinician).where(Clinician.id == user.clinician_id))
        clinician = clin_result.scalars().first()
        if clinician:
            clinician_phone = clinician.phone or ""

    # Get risk history
    rh_result = await db.execute(
        select(RiskHistory).where(RiskHistory.user_id == request.user_id)
        .order_by(RiskHistory.date).limit(14)
    )
    risk_history = [{"score": r.score} for r in rh_result.scalars().all()]

    # Ensure session exists
    sess_result = await db.execute(select(DBSession).where(DBSession.id == request.session_id))
    session = sess_result.scalars().first()
    if not session:
        session = DBSession(
            id=request.session_id, user_id=request.user_id,
            start_time=datetime.utcnow(), overall_risk_score=0.0, status="active"
        )
        db.add(session)
        await db.flush()

    # Run agent pipeline
    result = await process_message(
        user_id=request.user_id,
        session_id=request.session_id,
        message=request.message,
        patient_name=user.name,
        clinician_phone=clinician_phone,
        emergency_contact=user.emergency_contact or "",
        risk_history=risk_history
    )

    now = datetime.utcnow()
    risk = result["risk"]

    # Save user message
    db.add(Message(
        id=str(uuid.uuid4()), session_id=request.session_id,
        sender="user", text=request.message,
        risk_score=risk["overall_risk_score"],
        triggered_signals=risk.get("triggered_signals"),
        timestamp=now
    ))

    # Save agent reply
    db.add(Message(
        id=str(uuid.uuid4()), session_id=request.session_id,
        sender="agent", text=result["agent_reply"],
        timestamp=now
    ))

    # Save risk history
    db.add(RiskHistory(
        id=str(uuid.uuid4()), user_id=request.user_id,
        score=risk["overall_risk_score"],
        risk_level=risk["risk_level"],
        factors={"signals": risk.get("triggered_signals", [])},
        predicted_score=result["prediction"].get("crisis_probability"),
        date=now
    ))

    # Update session risk score
    session.overall_risk_score = risk["overall_risk_score"]

    # Save interventions
    for action in result.get("actions_taken", []):
        db.add(Intervention(
            id=str(uuid.uuid4()), user_id=request.user_id,
            type=action.split(":")[0], triggered_by="agent",
            outcome="fired", timestamp=now
        ))

    await db.commit()

    # Broadcast via WebSocket
    if _sio:
        await _sio.emit("risk_update", {
            "user_id": request.user_id,
            "patient_name": user.name,
            "risk_score": risk["overall_risk_score"],
            "risk_level": risk["risk_level"],
        })
        await _sio.emit("message_stream", {
            "session_id": request.session_id,
            "user_id": request.user_id,
            "message": request.message,
            "agent_reply": result["agent_reply"],
            "risk": risk,
        })
        if result.get("actions_taken"):
            await _sio.emit("intervention_fired", {
                "user_id": request.user_id,
                "patient_name": user.name,
                "actions": result["actions_taken"],
                "risk_level": risk["risk_level"],
            })

    return result


@router.post("/voice")
async def send_voice(
    user_id: str,
    session_id: str,
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    audio_bytes = await audio.read()
    s3_key = f"voice/{user_id}/{uuid.uuid4()}.webm"
    audio_url = None

    # Upload to S3
    try:
        audio_url = await upload_to_s3(audio_bytes, s3_key, audio.content_type or "audio/webm")
    except Exception:
        pass

    # Transcribe via Amazon Transcribe
    text = await _transcribe(audio_bytes, audio.filename or "audio.webm", s3_url=audio_url)

    req = ChatRequest(user_id=user_id, session_id=session_id, message=text)
    result = await send_message(req, db)

    # Attach S3 URL to the last user message
    if audio_url:
        result["audio_url"] = audio_url

    # Synthesize agent reply to speech via AWS Polly
    result["audio_reply"] = await _synthesize(result["agent_reply"])
    return result


async def _synthesize(text: str) -> str | None:
    """Convert text to speech via AWS Polly, return base64 MP3."""
    try:
        import base64
        polly = _aws_session.client("polly", region_name=os.getenv("AWS_REGION", "us-east-1"))
        resp = polly.synthesize_speech(
            Text=text[:3000],
            OutputFormat="mp3",
            VoiceId="Joanna",
            Engine="neural",
        )
        audio_bytes = resp["AudioStream"].read()
        return base64.b64encode(audio_bytes).decode()
    except Exception:
        return None


async def _transcribe(audio_bytes: bytes, filename: str, s3_url: str | None = None) -> str:
    """Transcribe audio using Amazon Transcribe."""
    import asyncio
    try:
        transcribe = _aws_session.client("transcribe", region_name=os.getenv("AWS_REGION", "us-east-1"))
        job_name = f"mg-{uuid.uuid4().hex[:16]}"

        # If not already on S3, upload it
        if not s3_url:
            key = f"voice/tmp/{job_name}.webm"
            s3_url = await upload_to_s3(audio_bytes, key, "audio/webm")

        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": s3_url},
            MediaFormat="webm",
            LanguageCode="en-US",
        )

        # Poll until complete (max 30s)
        for _ in range(30):
            await asyncio.sleep(1)
            resp = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            status = resp["TranscriptionJob"]["TranscriptionJobStatus"]
            if status == "COMPLETED":
                import urllib.request
                transcript_uri = resp["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
                with urllib.request.urlopen(transcript_uri) as r:
                    import json as _json
                    data = _json.loads(r.read())
                text = data["results"]["transcripts"][0]["transcript"]
                return text if text.strip() else "I couldn't hear that clearly."
            if status == "FAILED":
                break
    except Exception as e:
        print(f"[Transcribe] error: {e}")
    return "I couldn't hear that clearly."


@router.get("/session/{session_id}")
async def get_session_transcript(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Message).where(Message.session_id == session_id)
        .order_by(Message.timestamp)
    )
    messages = result.scalars().all()
    return [
        {"id": m.id, "sender": m.sender, "text": m.text,
         "risk_score": m.risk_score, "triggered_signals": m.triggered_signals,
         "timestamp": m.timestamp.isoformat() if m.timestamp else None}
        for m in messages
    ]
