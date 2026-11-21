import base64
import hashlib
import hmac
import json
import time
import uuid

import bcrypt
from fastapi import HTTPException, Request

from backend import config
from backend.db import cursor

COOKIE = "cb_session"


# ---- contrasenyas (bcrypt, max 72 bytes) ----
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def check_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


DUMMY_HASH = hash_password("contrasenya-falsa")  # para igualar tiempos si el usuario no existe


# ---- token firmado (HMAC-SHA256): {"sid": ..., "exp": ...} ----
def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sig(data: str) -> str:
    return _b64(hmac.new(config.JWT_SECRET.encode(), data.encode(), hashlib.sha256).digest())


def make_token(sid: str) -> str:
    payload = _b64(json.dumps({"sid": sid, "exp": int(time.time()) + config.SESSION_TTL_HOURS * 3600}).encode())
    return payload + "." + _sig(payload)


def read_token(token):
    try:
        payload, sig = token.split(".")
        if not hmac.compare_digest(sig, _sig(payload)):
            return None
        data = json.loads(_unb64(payload))
        if data["exp"] < time.time():
            return None
        uuid.UUID(data["sid"])
        return data
    except Exception:
        return None


# ---- sesion actual (token valido Y fila de sesion sin cerrar) ----
def current_session(token):
    data = read_token(token) if token else None
    if not data:
        return None
    with cursor() as cur:
        cur.execute(
            "SELECT s.id::text AS sid, u.id AS user_id, u.username, u.email "
            "FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.id = %s AND s.logout_at IS NULL", (data["sid"],))
        return cur.fetchone()


def create_session(cur, user_id, ip, ua, method):
    cur.execute("INSERT INTO sessions (user_id, method, ip, user_agent) VALUES (%s,%s,%s,%s) RETURNING id::text",
                (user_id, method, ip, (ua or "")[:300]))
    return cur.fetchone()["id"]


def end_session(sid):
    with cursor() as cur:
        cur.execute("UPDATE sessions SET logout_at = now() WHERE id = %s AND logout_at IS NULL", (sid,))


def set_cookie(resp, name, value, max_age, path="/"):
    resp.set_cookie(name, value, max_age=max_age, httponly=True, secure=True, samesite="lax", path=path)


def client_ip(request: Request) -> str:
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "")


def origin_ok(headers) -> bool:
    origin = headers.get("origin")
    if not origin:
        return True
    return origin.split("://", 1)[-1] == headers.get("host")


def check_origin(request: Request):
    if not origin_ok(request.headers):
        raise HTTPException(status_code=403, detail="origin")


class Throttle:
    def __init__(self, limit, window):
        self.limit, self.window, self.hits = limit, window, {}

    def allow(self, key) -> bool:
        now = time.time()
        recent = [t for t in self.hits.get(key, []) if now - t < self.window]
        ok = len(recent) < self.limit
        if ok:
            recent.append(now)
        self.hits[key] = recent
        return ok
