# Chat grupal: una sala global, solo en memoria (sin historial).
import time
from collections import deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from backend.security import COOKIE, current_session, origin_ok

router = APIRouter()
clients = {}  # WebSocket -> sesion


async def broadcast(message: dict):
    for ws in list(clients):
        try:
            await ws.send_json(message)
        except Exception:
            clients.pop(ws, None)


async def kick(sid: str):
    for ws, s in list(clients.items()):
        if s["sid"] == sid:
            clients.pop(ws, None)
            try:
                await ws.close(code=4401)
            except Exception:
                pass


@router.websocket("/ws/chat")
async def chat_ws(ws: WebSocket):
    await ws.accept()
    if not origin_ok(ws.headers):
        await ws.close(code=4403)
        return
    session = await run_in_threadpool(current_session, ws.cookies.get(COOKIE))
    if not session:
        await ws.close(code=4401)
        return
    clients[ws] = session
    name = session["username"]
    recent = deque(maxlen=5)
    await broadcast({"type": "system", "text": f"{name} se ha unido"})
    try:
        while True:
            text = (await ws.receive_text()).strip()[:500]
            if not text:
                continue
            now = time.time()
            if len(recent) == 5 and now - recent[0] < 3:
                await ws.send_json({"type": "system", "text": "Vas demasiado rapido"})
                continue
            recent.append(now)
            await broadcast({"type": "message", "user": name, "text": text, "ts": int(now)})
    except WebSocketDisconnect:
        pass
    finally:
        if clients.pop(ws, None):
            await broadcast({"type": "system", "text": f"{name} se ha ido"})
