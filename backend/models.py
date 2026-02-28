from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ── SQLAlchemy ORM Models ──────────────────────────────────────────────────────

class Clinician(Base):
    __tablename__ = "clinicians"
    id = Column(String, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)
    hashed_password = Column(String)
    phone = Column(String)
    role = Column(String, default="user")  # "admin" or "user"
    user_id = Column(String, ForeignKey("users.id"), nullable=True)  # linked patient record for role=user
    created_at = Column(DateTime)
    patients = relationship("User", back_populates="clinician", foreign_keys="[User.clinician_id]")


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String)
    age = Column(Integer)
    clinician_id = Column(String, ForeignKey("clinicians.id"))
    emergency_contact = Column(String)
    created_at = Column(DateTime)
    clinician = relationship("Clinician", back_populates="patients", foreign_keys="[User.clinician_id]")
    sessions = relationship("Session", back_populates="user")
    risk_history = relationship("RiskHistory", back_populates="user")
    interventions = relationship("Intervention", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    start_time = Column(DateTime)
    end_time = Column(DateTime, nullable=True)
    overall_risk_score = Column(Float, default=0.0)
    status = Column(String, default="active")
    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session")


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    sender = Column(String)
    text = Column(String)
    audio_url = Column(String, nullable=True)
    risk_score = Column(Float, nullable=True)
    triggered_signals = Column(JSON, nullable=True)
    timestamp = Column(DateTime)
    session = relationship("Session", back_populates="messages")


class RiskHistory(Base):
    __tablename__ = "risk_history"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    score = Column(Float)
    risk_level = Column(String)
    factors = Column(JSON)
    predicted_score = Column(Float, nullable=True)
    date = Column(DateTime)
    user = relationship("User", back_populates="risk_history")


class Intervention(Base):
    __tablename__ = "interventions"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    type = Column(String)
    triggered_by = Column(String)
    outcome = Column(String)
    timestamp = Column(DateTime)
    user = relationship("User", back_populates="interventions")


# ── Pydantic Schemas ───────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    clinician_id: str
    name: str
    role: str = "user"
    user_id: Optional[str] = None

class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str

class PatientCreate(BaseModel):
    name: str
    age: int
    emergency_contact: str

class InterventionRequest(BaseModel):
    user_id: str
    message: Optional[str] = None
    recipient: Optional[str] = None
    body: Optional[str] = None
    urgency: Optional[str] = "regular"

class RiskAnalyzeRequest(BaseModel):
    user_id: str
    message: str
