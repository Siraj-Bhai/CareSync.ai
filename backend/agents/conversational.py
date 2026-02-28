import os
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """
You are MindGuard, a warm and empathetic mental health companion.
Your role is to make users feel heard, safe, and understood.
Never diagnose. Never minimize feelings. Ask gentle follow-up questions.
If risk_level is HIGH or CRISIS, shift your tone to be more grounding and direct.
Gently surface the idea of talking to someone.
Always respond in a calm, human, non-clinical way. Keep responses concise (2-4 sentences).
"""

FALLBACK_RESPONSES = {
    "LOW": "Thank you for sharing that with me. It sounds like things have been weighing on you. What's been on your mind most today?",
    "MODERATE": "I hear you, and I want you to know your feelings are completely valid. Can you tell me more about what's been happening?",
    "HIGH": "I'm really glad you're talking to me right now. You don't have to face this alone — have you been able to talk to anyone else about this?",
    "CRISIS": "I hear you, and I'm here with you right now. I want to make sure you're safe — can you tell me more about what's going through your mind?",
    "IMMINENT": "I'm here with you. Your life has value and you matter. Please reach out to emergency services or a crisis line right now.",
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


async def get_conversational_response(message: str, risk_level: str, resources: dict) -> str:
    agent = _get_agent()
    if agent:
        try:
            raw = agent(f"User message: {message}\nRisk level: {risk_level}\nResources to surface: {resources}")
            return raw.message["content"][0]["text"]
        except Exception:
            pass
    return FALLBACK_RESPONSES.get(risk_level, FALLBACK_RESPONSES["LOW"])
