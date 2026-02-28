from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Clinician, User, LoginRequest, TokenResponse
from auth import verify_password, create_access_token, get_password_hash
from datetime import datetime
import uuid

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Clinician).where(Clinician.email == request.email))
    clinician = result.scalars().first()
    if not clinician or not verify_password(request.password, clinician.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": clinician.id, "email": clinician.email})
    return TokenResponse(
        access_token=token, clinician_id=clinician.id, name=clinician.name,
        role=clinician.role or "user", user_id=clinician.user_id
    )


class RegisterRequest(LoginRequest):
    name: str
    role: str = "user"
    age: int = 0

@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Clinician).where(Clinician.email == request.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")

    clinician_id = str(uuid.uuid4())
    user_id = None

    # For role=user, auto-create a linked patient record
    if request.role == "user":
        user_id = str(uuid.uuid4())
        db.add(User(
            id=user_id, name=request.name, age=request.age,
            clinician_id=None, emergency_contact="",
            created_at=datetime.utcnow()
        ))
        await db.flush()

    clinician = Clinician(
        id=clinician_id,
        name=request.name,
        email=request.email,
        hashed_password=get_password_hash(request.password),
        phone="",
        role=request.role,
        user_id=user_id,
        created_at=datetime.utcnow()
    )
    db.add(clinician)
    await db.commit()
    token = create_access_token({"sub": clinician.id, "email": clinician.email})
    return TokenResponse(
        access_token=token, clinician_id=clinician.id, name=clinician.name,
        role=clinician.role, user_id=clinician.user_id
    )


@router.get("/me")
async def get_me(db: AsyncSession = Depends(get_db)):
    from auth import get_current_clinician
    return {"message": "Use Authorization header"}
