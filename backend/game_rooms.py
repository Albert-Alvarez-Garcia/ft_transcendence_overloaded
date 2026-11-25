# Capa genérica de salas de juego. No depende de FastAPI, así que se puede probar sola (ver tests/).
# Contrato de mensajes: docs/WS.md. Límites conocidos: README (salas solo en memoria).
import asyncio
import logging
import secrets
import time
from collections import deque

log = logging.getLogger("uvicorn.error")

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sin 0/O/1/I/L para que no se confundan
MAX_ROOMS = 200
CHAT_MAX_LEN = 300


class GameHandler:
    """Lo que implementa cada juego. Solo id y name son obligatorios; los hooks son opcionales."""
    id = "base"
    name = "Base"
    min_players = 2
    max_players = 4

    def default_settings(self):
        return {}

    async def on_start(self, room):
        pass

    async def on_message(self, room, player, msg):
        pass

    async def on_leave(self, room, player):   # el jugador se ha desconectado en mitad de la partida
        pass

    async def on_rejoin(self, room, player):  # el jugador ha vuelto
        pass

    def snapshot(self, room, player):         # estado del juego visible para ese jugador
        return {}


GAMES = {}


def register(handler_cls):
    GAMES[handler_cls.id] = handler_cls
    return handler_cls


class Player:
    def __init__(self, user_id, username, sid=None):
        self.user_id, self.username, self.sid = user_id, username, sid
        self.ws = None
        self.connected = False
        self.recent = deque(maxlen=5)  # límite de velocidad del chat

    def public(self, room):
        return {"id": self.user_id, "username": self.username, "connected": self.connected,
                "isHost": self.user_id == room.host_id}


class Room:
    def __init__(self, manager, code, handler, host_id, settings, max_players):
        self.manager, self.code, self.handler = manager, code, handler
        self.host_id, self.settings, self.max_players = host_id, settings, max_players
        self.players = {}        # user_id -> Player (en orden de llegada)
        self.phase = "lobby"     # lobby | playing | finished
        self.ends_at = None      # epoch en milisegundos, o None
        self.data = {}           # estado propio del juego (lo gestiona el handler)
        self._grace = None

    def connected_players(self):
        return [p for p in self.players.values() if p.connected]

    def summary(self):
        host = self.players.get(self.host_id)
        return {"code": self.code, "game": self.handler.id, "phase": self.phase,
                "players": len(self.players), "maxPlayers": self.max_players,
                "host": host.username if host else None}

    def state_for(self, player):
        return {"code": self.code, "game": self.handler.id, "phase": self.phase, "endsAt": self.ends_at,
                "hostId": self.host_id, "you": {"id": player.user_id, "username": player.username},
                "players": [p.public(self) for p in self.players.values()], "settings": self.settings,
                "minPlayers": self.handler.min_players, "maxPlayers": self.max_players,
                "gameState": self.handler.snapshot(self, player) if self.phase != "lobby" else {}}

    # ---- envío (lo usan los juegos) ----
    async def send(self, player, type_, /, **data):
        if player.ws is None:
            return
        try:
            await player.ws.send_json({"type": type_, **data})
        except Exception:
            pass  # la desconexión se detecta en el bucle de recepción

    async def broadcast(self, type_, /, **data):
        for p in list(self.players.values()):
            await self.send(p, type_, **data)

    async def broadcast_except(self, skip, type_, /, **data):
        for p in list(self.players.values()):
            if p is not skip:
                await self.send(p, type_, **data)

    async def send_state(self):
        for p in list(self.players.values()):
            await self.send(p, "room_state", **self.state_for(p))

    async def set_phase(self, phase, ends_at=None):
        self.phase, self.ends_at = phase, ends_at
        await self.broadcast("phase", phase=phase, endsAt=ends_at)

    async def finish(self, results):
        """results: [{"userId", "username", "score", "rank"}, ...]. Avisa a todos y registra la partida."""
        self.phase, self.ends_at = "finished", None
        await self.broadcast("finished", results=results)
        await self.manager.record(self.handler.id, self.code, results)


class RoomManager:
    def __init__(self, record_match=None, grace_seconds=60):
        self.rooms = {}
        self.record_match = record_match  # función (game_id, code, results); puede ser sync o async
        self.grace_seconds = grace_seconds

    # ---- creación y consulta ----
    def create(self, game_id, host_id, max_players=None, settings=None):
        cls = GAMES.get(game_id)
        if cls is None:
            return None, "unknown_game"
        if len(self.rooms) >= MAX_ROOMS:
            return None, "too_many_rooms"
        handler = cls()
        mp = handler.max_players if max_players is None else max_players
        if type(mp) is not int or not handler.min_players <= mp <= handler.max_players:
            return None, "invalid_settings"
        defaults = handler.default_settings()
        given = settings if isinstance(settings, dict) else {}
        merged = {**defaults, **{k: v for k, v in given.items() if k in defaults and type(v) is type(defaults[k])}}
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(5))
        while code in self.rooms:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(5))
        room = Room(self, code, handler, host_id, merged, mp)
        self.rooms[code] = room
        self._schedule_expiry(room)  # si nadie llega a entrar, la sala se limpia sola
        return room, None

    def list_lobbies(self, game_id=None):
        return [r.summary() for r in self.rooms.values()
                if r.phase == "lobby" and r.players and (not game_id or r.handler.id == game_id)]

    # ---- conexión de jugadores ----
    async def join(self, code, user_id, username, ws, sid=None):
        room = self.rooms.get(code)
        if room is None:
            return None, None, "room_not_found"
        player = room.players.get(user_id)
        is_new = player is None
        if is_new:
            if room.phase != "lobby":
                return None, None, "room_closed"
            if len(room.players) >= room.max_players:
                return None, None, "room_full"
            player = room.players[user_id] = Player(user_id, username)
        old = player.ws
        player.ws, player.connected, player.sid = ws, True, sid
        self._cancel_expiry(room)
        if old is not None and old is not ws:
            try:
                await old.close(code=4409)  # sustituida por otra conexión del mismo usuario
            except Exception:
                pass
        await room.send(player, "room_state", **room.state_for(player))
        if is_new:
            await room.broadcast_except(player, "player_joined", player=player.public(room))
        else:
            await room.broadcast_except(player, "player_status", id=user_id, connected=True)
            if room.phase == "playing":
                await self._safe(room.handler.on_rejoin(room, player))
        return room, player, None

    async def leave(self, room, player, ws):
        if player.ws is not ws:
            return  # esta conexión ya había sido sustituida
        player.ws, player.connected = None, False
        if room.phase == "lobby":
            room.players.pop(player.user_id, None)
            if not room.players:
                self._drop(room)
                return
            if room.host_id == player.user_id:
                room.host_id = next(iter(room.players))
            await room.broadcast("player_left", id=player.user_id, hostId=room.host_id)
        else:
            await room.broadcast("player_status", id=player.user_id, connected=False)
            await self._safe(room.handler.on_leave(room, player))
        if not room.connected_players():
            self._schedule_expiry(room)

    async def kick_session(self, sid):
        for room in list(self.rooms.values()):
            for p in list(room.players.values()):
                if p.sid == sid and p.ws is not None:
                    try:
                        await p.ws.close(code=4401)
                    except Exception:
                        pass

    # ---- mensajes del cliente ----
    async def handle(self, room, player, msg):
        kind = msg.get("type")
        if kind == "chat":
            now = time.time()
            if len(player.recent) == 5 and now - player.recent[0] < 3:
                return await room.send(player, "error", code="too_fast")
            player.recent.append(now)
            text = " ".join(str(msg.get("text", "")).split())[:CHAT_MAX_LEN]
            if text:
                await room.broadcast("chat", user=player.username, text=text, ts=int(now))
        elif kind == "start":
            if player.user_id != room.host_id:
                return await room.send(player, "error", code="not_host")
            if room.phase == "playing":
                return await room.send(player, "error", code="already_started")
            if len(room.connected_players()) < room.handler.min_players:
                return await room.send(player, "error", code="not_enough_players")
            for p in list(room.players.values()):  # al (re)empezar se retiran los desconectados
                if not p.connected:
                    del room.players[p.user_id]
            room.phase, room.ends_at = "playing", None
            await self._safe(room.handler.on_start(room))
            await room.send_state()
        elif kind == "game":
            if room.phase != "playing":
                return await room.send(player, "error", code="not_playing")
            await self._safe(room.handler.on_message(room, player, msg))
        else:
            await room.send(player, "error", code="unknown_type")

    async def record(self, game_id, code, results):
        if not self.record_match:
            return
        try:
            res = self.record_match(game_id, code, results)
            if asyncio.iscoroutine(res):
                await res
        except Exception:
            log.exception("record_match ha fallado")

    # ---- utilidades internas ----
    async def _safe(self, coro):
        try:
            await coro
        except Exception:
            log.exception("Error en el juego")

    def _drop(self, room):
        self._cancel_expiry(room)
        self.rooms.pop(room.code, None)

    def _cancel_expiry(self, room):
        if room._grace is not None:
            room._grace.cancel()
            room._grace = None

    def _schedule_expiry(self, room):
        self._cancel_expiry(room)
        room._grace = asyncio.get_running_loop().create_task(self._expire(room))

    async def _expire(self, room):
        try:
            await asyncio.sleep(self.grace_seconds)
        except asyncio.CancelledError:
            return
        if not room.connected_players():
            self.rooms.pop(room.code, None)
