from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timedelta, timezone
import uuid, random
from config_secrets import get_secret

DB_HOST = get_secret("DB_HOST_NAME", "localhost")
DB_PORT = get_secret("DB_PORT", "5432")
DB_NAME = get_secret("DB_NAME", "caresync_ai")
DB_USER = get_secret("DB_USER", "postgres")
DB_PASSWORD = get_secret("DB_PASSWORD", "admin123")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    from models import Base, Clinician, User, Session as DBSession, Message, RiskHistory, Intervention
    from auth import get_password_hash
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(Clinician))
        if result.scalars().first():
            return

        db.add(Clinician(
            id="clinician-1", name="Dr. Sarah Chen",
            email="sarah.chen@mindguard.com",
            hashed_password=get_password_hash("password123"),
            phone="+15551234567", role="admin", user_id=None, created_at=now()
        ))

        for uid, name, age, phone in [
            ("user-1", "John D.", 34, "+15559876543"),
            ("user-2", "Sara M.", 28, "+15558765432"),
            ("user-3", "Alex K.", 45, "+15557654321"),
            ("user-4", "Emma R.", 22, "+15556543210"),
        ]:
            db.add(User(id=uid, name=name, age=age, clinician_id="clinician-1",
                        emergency_contact=phone, created_at=now() - timedelta(days=30)))

        await db.flush()

        risk_profiles = {
            "user-1": [18, 22, 35, 41, 52, 61, 87],
            "user-2": [45, 50, 58, 65, 62, 68, 65],
            "user-3": [55, 48, 42, 38, 40, 42, 42],
            "user-4": [30, 25, 20, 18, 15, 18, 18],
        }
        risk_levels = {(0, 30): "LOW", (30, 50): "MODERATE", (50, 70): "HIGH", (70, 101): "CRISIS"}

        for uid, scores in risk_profiles.items():
            for i, score in enumerate(scores):
                level = next(v for (lo, hi), v in risk_levels.items() if lo <= score < hi)
                db.add(RiskHistory(
                    id=str(uuid.uuid4()), user_id=uid, score=float(score), risk_level=level,
                    factors={"signals": ["hopelessness", "withdrawal"] if score > 60 else ["stress"]},
                    predicted_score=float(min(100, score + 5)),
                    date=now() - timedelta(days=6 - i)
                ))

        session_id = "session-demo-1"
        db.add(DBSession(id=session_id, user_id="user-1",
                         start_time=now() - timedelta(hours=2),
                         overall_risk_score=87.0, status="active"))

        for sender, text, risk in [
            ("user", "I've been feeling really stressed about work lately.", 18.0),
            ("agent", "I hear you. Work stress can be really overwhelming. What's been weighing on you most?", None),
            ("user", "Everything just feels pointless. I don't see the point anymore.", 87.0),
            ("agent", "I'm really glad you shared that with me. Can you tell me more about what you mean?", None),
        ]:
            db.add(Message(
                id=str(uuid.uuid4()), session_id=session_id, sender=sender, text=text,
                risk_score=risk,
                triggered_signals=["hopelessness", "withdrawal"] if risk and risk > 60 else None,
                timestamp=now() - timedelta(minutes=random.randint(1, 30))
            ))

        for uid, itype, triggered_by, outcome in [
            ("user-1", "sms", "agent", "delivered"),
            ("user-1", "resources", "agent", "shown"),
            ("user-2", "sms", "clinician", "delivered"),
            ("user-2", "booking", "clinician", "confirmed"),
        ]:
            db.add(Intervention(id=str(uuid.uuid4()), user_id=uid, type=itype,
                                triggered_by=triggered_by, outcome=outcome,
                                timestamp=now() - timedelta(hours=random.randint(1, 48))))

        await db.commit()
