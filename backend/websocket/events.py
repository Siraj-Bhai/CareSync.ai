import socketio

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


@sio.event
async def connect(sid, environ):
    print(f"[WS] Client connected: {sid}")


@sio.event
async def join_session(sid, data):
    session_id = data.get("session_id")
    if session_id:
        await sio.enter_room(sid, f"session_{session_id}")
        print(f"[WS] {sid} joined session_{session_id}")


@sio.event
async def join_dashboard(sid, data):
    await sio.enter_room(sid, "dashboard")
    print(f"[WS] {sid} joined dashboard")


@sio.event
async def disconnect(sid):
    print(f"[WS] Client disconnected: {sid}")
