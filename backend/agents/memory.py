import json, re
import numpy as np
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """
You are a longitudinal mental health trend analyzer.
Given a user's session history, compute their crisis probability over the next 72 hours.
Return ONLY a JSON object:
{"crisis_probability": int, "timeWindow": "72hrs", "confidence": float, "driving_factors": [], "recommendation": "string"}
"""

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


def compute_prediction(risk_scores: list) -> dict:
    if len(risk_scores) < 2:
        score = risk_scores[0] if risk_scores else 0
        return {"crisis_probability": int(min(100, score)), "timeWindow": "72hrs",
                "confidence": 0.5, "driving_factors": ["Insufficient history"], "recommendation": "Continue monitoring"}

    x = np.arange(len(risk_scores))
    slope = float(np.polyfit(x, risk_scores, 1)[0])
    predicted = float(min(100, max(0, risk_scores[-1] + slope * 3)))
    confidence = min(0.95, 0.5 + len(risk_scores) * 0.03)

    factors = []
    if slope > 5: factors.append("Rapid risk score escalation")
    elif slope > 2: factors.append("Gradual upward trend in risk")
    elif slope < -2: factors.append("Risk score improving")
    if risk_scores[-1] > 70: factors.append("Current score in crisis range")
    if len(risk_scores) >= 3 and all(risk_scores[-i] > risk_scores[-i - 1] for i in range(1, 3)):
        factors.append("Consecutive session deterioration")
    if not factors: factors = ["Stable pattern observed"]

    rec = ("Immediate proactive outreach recommended" if predicted > 70
           else "Proactive outreach recommended within 24hrs" if predicted > 50
           else "Monitor closely — upward trend detected" if slope > 3
           else "Continue regular check-ins")

    return {"crisis_probability": int(predicted), "timeWindow": "72hrs",
            "confidence": round(confidence, 2), "driving_factors": factors, "recommendation": rec}


async def predict_crisis(user_id: str, risk_scores: list) -> dict:
    agent = _get_agent()
    if agent and len(risk_scores) >= 3:
        try:
            raw = agent(f"User ID: {user_id}\nRisk score history (oldest to newest): {risk_scores}")
            text = raw.message["content"][0]["text"]
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
    return compute_prediction(risk_scores)
