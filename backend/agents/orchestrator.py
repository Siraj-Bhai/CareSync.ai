from agents.detection import detect_risk
from agents.conversational import get_conversational_response
from agents.memory import predict_crisis
from agents.intervention import run_intervention


async def process_message(
    user_id: str,
    session_id: str,
    message: str,
    patient_name: str = "Patient",
    clinician_phone: str = "",
    emergency_contact: str = "",
    risk_history: list = None,
    audio_emotion: dict = None
) -> dict:

    # Step 1: Detect risk
    risk = await detect_risk(message, audio_emotion)

    # Step 2: Memory prediction
    scores = [r["score"] for r in (risk_history or [])]
    scores.append(risk["overall_risk_score"])
    prediction = await predict_crisis(user_id, scores)

    # Step 3: Intervention if needed
    intervention_result = await run_intervention(
        user_id=user_id,
        patient_name=patient_name,
        clinician_phone=clinician_phone,
        emergency_contact=emergency_contact,
        risk_level=risk["risk_level"],
        risk_score=int(risk["overall_risk_score"]),
        message=message,
        triggered_signals=risk.get("triggered_signals", [])
    )

    # Step 4: Empathetic response
    agent_reply = await get_conversational_response(
        message=message,
        risk_level=risk["risk_level"],
        resources=intervention_result.get("resources", {})
    )

    return {
        "agent_reply": agent_reply,
        "risk": risk,
        "prediction": prediction,
        "actions_taken": intervention_result.get("actions_taken", []),
        "resources": intervention_result.get("resources", {})
    }
