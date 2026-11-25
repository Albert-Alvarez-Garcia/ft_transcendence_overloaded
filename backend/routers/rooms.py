# HTTP + WebSocket de las salas de juego. Contratos: docs/API.md (HTTP) y docs/WS.md (WebSocket).
import json
import logging

from fastapi import APIRouter, Body, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from backend import game_rooms, games  # noqa: F401  (games registra los juegos al importarse)
from backend.security import COOKIE, check_origin, current_session, origin_ok

log = logging.getLogger("uvicorn.error")
router = APIRouter()
CLOSE_CODES = {"room_not_found": 4404, "room_closed": 4410, "room_full": 4411}
UNAUTH = {"ok": False, "error": "unauthenticated"}


async def record_match(game_id, code, results):
    # PUNTO DE ENGANCHE con la base de datos: aquí se guardará el historial y las estadísticas.
    # Por ahora solo deja constancia en el log. Lo implementará quien sea dueño de la tabla de partidas.
    log.info("Partida terminada: juego=%s sala=%s resultados=%s", game_id, code, results)


manager = game_rooms.RoomManager(record_match=record_match)


async def kick(sid):
    """Se llama al cerrar sesión: corta las conexiones de esa sesión a las salas."""
    await manager.kick_session(sid)


async def _session(request: Request):
    return await run_in_threadpool(current_session, request.cookies.get(COOKIE))


@router.get("/api/games")
async def list_games(request: Request):
    if not await _session(request):
        return UNAUTH
    return {"ok": True, "games": [
        {"id": c.id, "name": c.name, "minPlayers": c.min_players, "maxPlayers": c.max_players,
         "defaultSettings": c().default_settings()} for c in game_rooms.GAMES.values()]}


@router.get("/api/rooms")
async def list_rooms(request: Request, game: str = ""):
    if not await _session(request):
        return UNAUTH
    return {"ok": True, "rooms": manager.list_lobbies(game or None)}


@router.post("/api/rooms")
async def create_room(request: Request, data: dict = Body(default={})):
    check_origin(request)
    session = await _session(request)
    if not session:
        return UNAUTH
    room, err = manager.create(str(data.get("game", "")), session["user_id"],
                               data.get("maxPlayers"), data.get("settings"))
    return {"ok": False, "error": err} if err else {"ok": True, "code": room.code}


@router.get("/api/rooms/{code}")
async def room_info(code: str, request: Request):
    if not await _session(request):
        return UNAUTH
    room = manager.rooms.get(code.upper())
    return {"ok": True, "room": room.summary()} if room else {"ok": False, "error": "room_not_found"}


@router.websocket("/ws/rooms/{code}")
async def room_ws(ws: WebSocket, code: str):
    await ws.accept()
    if not origin_ok(ws.headers):
        await ws.close(code=4403)
        return
    session = await run_in_threadpool(current_session, ws.cookies.get(COOKIE))
    if not session:
        await ws.close(code=4401)
        return
    room, player, err = await manager.join(code.upper(), session["user_id"], session["username"], ws, session["sid"])
    if err:
        await ws.close(code=CLOSE_CODES[err])
        return
    try:
        while True:
            raw = await ws.receive_text()
            if len(raw) > 4096:
                await room.send(player, "error", code="too_large")
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                msg = None
            if not isinstance(msg, dict):
                await room.send(player, "error", code="bad_message")
                continue
            if msg.get("type") == "leave":
                break
            await manager.handle(room, player, msg)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.leave(room, player, ws)
        try:
            await ws.close()
        except Exception:
            pass
