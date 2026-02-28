import os, httpx
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.getenv("TWILIO_FROM", "")
CAL_API_KEY = os.getenv("CAL_API_KEY", "")
URGENT_EVENT_TYPE_ID = int(os.getenv("URGENT_EVENT_TYPE_ID", 1))
REGULAR_EVENT_TYPE_ID = int(os.getenv("REGULAR_EVENT_TYPE_ID", 2))

CRISIS_RESOURCES = {
    "HIGH": {"hotline": "iCall: 9152987821", "text": "Text HOME to 741741"},
    "CRISIS": {"hotline": "Vandrevala Foundation: 1860-2662-345", "text": "Text HOME to 741741"},
    "IMMINENT": {"hotline": "Emergency: 112", "note": "Please call emergency services immediately"},
}


async def send_clinician_sms(clinician_phone: str, patient_name: str, risk_score: int, message: str) -> str:
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM]):
        return "sms_skipped_no_credentials"
    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=f"[MindGuard Alert] {patient_name} — Risk Score: {risk_score}/100\n{message}",
            from_=TWILIO_FROM,
            to=clinician_phone
        )
        return "sms_sent"
    except Exception as e:
        return f"sms_failed: {str(e)}"


async def send_emergency_sms(emergency_contact: str, patient_name: str, triggered_signals: list) -> str:
    """Make a voice call to the user's personal emergency contact on CRISIS/IMMINENT."""
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM]) or not emergency_contact:
        return "emergency_call_skipped"
    try:
        from twilio.rest import Client
        signal_map = {
            "hopelessness": "feelings of hopelessness",
            "suicidal_ideation": "suicidal thoughts",
            "self_harm": "self-harm tendencies",
            "urgency": "a sense of urgency or crisis",
            "withdrawal": "social withdrawal",
        }
        described = ", ".join(signal_map.get(s, s) for s in triggered_signals) or "severe emotional distress"
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        twiml = f"""<Response><Say voice="alice" language="en-IN">
            MindGuard Emergency Alert.
            {patient_name} is showing signs of {described}.
            They may need immediate support. Please check on them right away.
        </Say></Response>"""
        call = client.calls.create(twiml=twiml, from_=TWILIO_FROM, to=emergency_contact)
        return f"emergency_call_placed:{call.sid}"
    except Exception as e:
        return f"emergency_call_failed: {str(e)}"


async def book_therapy_appointment(user_id: str, urgency: str = "regular") -> str:
    if not CAL_API_KEY:
        return "booking_skipped_no_credentials"
    try:
        event_type_id = URGENT_EVENT_TYPE_ID if urgency == "urgent" else REGULAR_EVENT_TYPE_ID
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.cal.com/v1/bookings",
                json={"eventTypeId": event_type_id, "userId": user_id},
                headers={"Authorization": f"Bearer {CAL_API_KEY}"}
            )
        return response.json().get("uid", "booking_failed")
    except Exception as e:
        return f"booking_failed: {str(e)}"


def get_crisis_resources(risk_level: str) -> dict:
    return CRISIS_RESOURCES.get(risk_level, {})


async def run_intervention(user_id: str, patient_name: str, clinician_phone: str,
                           risk_level: str, risk_score: int, message: str,
                           emergency_contact: str = "", triggered_signals: list = None) -> dict:
    actions_taken = []
    resources = {}

    if risk_level == "LOW":
        return {"actions_taken": [], "resources": {}}

    if risk_level == "MODERATE":
        resources = {"tip": "Try deep breathing or grounding exercises"}
        actions_taken.append("coping_strategies_suggested")
        return {"actions_taken": actions_taken, "resources": resources}

    resources = get_crisis_resources(risk_level)

    if risk_level in ["HIGH", "CRISIS", "IMMINENT"]:
        sms_result = await send_clinician_sms(clinician_phone, patient_name, risk_score, message)
        actions_taken.append(f"clinician_sms:{sms_result}")
        actions_taken.append("crisis_resources_injected")

    if risk_level in ["CRISIS", "IMMINENT"]:
        actions_taken.append("therapy_booking_offered")
        if emergency_contact:
            ec_result = await send_emergency_sms(emergency_contact, patient_name, triggered_signals or [])
            actions_taken.append(f"emergency_contact_sms:{ec_result}")

    if risk_level == "IMMINENT":
        actions_taken.append("emergency_escalation_triggered")

    return {"actions_taken": actions_taken, "resources": resources}
