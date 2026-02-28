import json, re
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """
You are a mental health crisis detection engine.
Analyze the user message for these signals:
- hopelessness_score (0-10)
- suicidal_ideation_score (0-10)
- self_harm_score (0-10)
- urgency_score (0-10)
- withdrawal_score (0-10)

Compute overall_risk_score (0-100):
hopelessness*0.25 + suicidal_ideation*0.30 + self_harm*0.20 + urgency*0.15 + withdrawal*0.10 (multiply by 10)

Assign risk_level: LOW (0-29) | MODERATE (30-49) | HIGH (50-69) | CRISIS (70-89) | IMMINENT (90-100)

Return ONLY valid JSON. No explanation.
{"overall_risk_score": 78, "risk_level": "CRISIS", "triggered_signals": ["hopelessness"],
"hopelessness_score": 8, "suicidal_ideation_score": 7, "self_harm_score": 3, "urgency_score": 6, "withdrawal_score": 5,
"reasoning": "..."}
"""

CRISIS_KEYWORDS = {
    "suicidal_ideation": ["don't want to live", "want to die", "end my life", "kill myself", "suicide", "no reason to live", "don't see the point"],
    "hopelessness": ["hopeless", "pointless", "no hope", "nothing matters", "worthless", "burden", "no future", "don't see the point"],
    "self_harm": ["hurt myself", "cut myself", "self harm", "self-harm", "punish myself"],
    "urgency": ["can't take it", "can't go on", "tonight", "last time", "goodbye", "farewell"],
    "withdrawal": ["alone", "isolated", "nobody cares", "disappear", "leave everyone"],
}

_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        try:
            from strands import Agent
            from aws_config import get_bedrock_model
            _agent = Agent(model=get_bedrock_model(), system_prompt=SYSTEM_PROMPT, tools=[])
        except Exception:
            _agent = False
    return _agent if _agent else None


def heuristic_detect(message: str) -> dict:
    msg_lower = message.lower()
    scores, triggered = {}, []
    for signal, keywords in CRISIS_KEYWORDS.items():
        score = min(10, sum(3 for kw in keywords if kw in msg_lower))
        scores[signal] = score
        if score > 0:
            triggered.append(signal)

    overall = min(100, round((
        scores.get("hopelessness", 0) * 0.25 +
        scores.get("suicidal_ideation", 0) * 0.30 +
        scores.get("self_harm", 0) * 0.20 +
        scores.get("urgency", 0) * 0.15 +
        scores.get("withdrawal", 0) * 0.10
    ) * 10))

    level = "LOW" if overall < 30 else "MODERATE" if overall < 50 else "HIGH" if overall < 70 else "CRISIS" if overall < 90 else "IMMINENT"
    return {
        "overall_risk_score": overall, "risk_level": level, "triggered_signals": triggered,
        **{f"{k}_score": v for k, v in scores.items()},
        "reasoning": f"Heuristic detection. Triggered: {triggered}"
    }


async def detect_risk(message: str, audio_emotion: dict = None) -> dict:
    agent = _get_agent()
    if agent:
        try:
            raw = agent(f"User message: {message}\nVoice emotion data: {audio_emotion or {}}")
            text = raw.message["content"][0]["text"]
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
    return heuristic_detect(message)
