from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
from contextlib import asynccontextmanager

from websocket.events import sio
from routers import auth, patients, chat, risk, interventions, dashboard
from routers.chat import set_sio
from database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    set_sio(sio)
    yield


app = FastAPI(title="MindGuard Pro API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(patients.router, prefix="/api/patients", tags=["Patients"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(risk.router, prefix="/api/risk", tags=["Risk"])
app.include_router(interventions.router, prefix="/api/interventions", tags=["Interventions"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])


@app.get("/")
async def root():
    return {"message": "MindGuard Pro API", "version": "1.0.0", "docs": "/docs"}


# Mount Socket.io
socket_app = socketio.ASGIApp(sio, app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:socket_app", host="0.0.0.0", port=8000, reload=True, factory=False)
