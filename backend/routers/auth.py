# Convencion: los errores "esperados" (clave mala, usuario repetido...) devuelven HTTP 200
# con {"ok": false, "error": "<codigo>"} para no ensuciar la consola del navegador.
import hashlib
import json
import logging
import re
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse

from backend import config, mailer
from backend.db import cursor
from backend.routers import chat
from backend.security import (COOKIE, DUMMY_HASH, Throttle, check_origin, check_password, client_ip,
                              create_session, current_session, end_session, hash_password, make_token,
                              set_cookie)

log = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api/auth")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{3,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
login_throttle, register_throttle, resend_throttle = Throttle(10, 300), Throttle(5, 600), Throttle(3, 600)
FT_AUTH, FT_TOKEN, FT_ME = ("https://api.intra.42.fr/oauth/authorize", "https://api.intra.42.fr/oauth/token",
                            "https://api.intra.42.fr/v2/me")


# La API de 42 esta tras Cloudflare, que bloquea el User-Agent por defecto de urllib (error 1010).
UA_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ft_base/1.0)", "Accept": "application/json"}


def fail(code):
    return JSONResponse({"ok": False, "error": code})


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _new_verification(cur, user_id):
    token = secrets.token_urlsafe(32)
    cur.execute("UPDATE users SET verify_token_hash=%s, verify_expires=%s WHERE id=%s",
                (_hash(token), datetime.now(timezone.utc) + timedelta(hours=24), user_id))
    return token


def _login_response(request, user_id, method, payload):
    with cursor() as cur:
        sid = create_session(cur, user_id, client_ip(request), request.headers.get("user-agent"), method)
    return sid


@router.get("/me")
def me(request: Request):
    s = current_session(request.cookies.get(COOKIE))
    if not s:
        return {"authenticated": False}
    return {"authenticated": True, "user": {"username": s["username"], "email": s["email"]}}


@router.post("/register")
def register(request: Request, data: dict = Body(default={})):
    check_origin(request)
    if not register_throttle.allow(client_ip(request)):
        return fail("too_many_attempts")
    username, email, pw = str(data.get("username", "")).strip(), str(data.get("email", "")).strip().lower(), str(data.get("password", ""))
    if not USERNAME_RE.match(username):
        return fail("invalid_username")
    if not EMAIL_RE.match(email) or len(email) > 254:
        return fail("invalid_email")
    if len(pw) < 8 or len(pw.encode()) > 72:
        return fail("invalid_password")
    with cursor() as cur:
        cur.execute("SELECT lower(username)=lower(%s) AS u, email=%s AS e FROM users WHERE lower(username)=lower(%s) OR email=%s",
                    (username, email, username, email))
        rows = cur.fetchall()
        if any(r["u"] for r in rows):
            return fail("username_taken")
        if rows:
            return fail("email_taken")
        cur.execute("INSERT INTO users (username, email, password_hash) VALUES (%s,%s,%s) RETURNING id",
                    (username, email, hash_password(pw)))
        uid = cur.fetchone()["id"]
        token = _new_verification(cur, uid)
    try:
        mailer.send_verification(email, f"{config.PUBLIC_BASE_URL}/verify.html?token={token}")
    except Exception as exc:
        log.warning("Correo NO enviado a %s: %r (host=%s puerto=%s usuario=%s)", email, exc,
                    config.SMTP_HOST, config.SMTP_PORT, config.SMTP_USER)
        with cursor() as cur:
            cur.execute("DELETE FROM users WHERE id=%s", (uid,))
        return fail("email_failed")
    return {"ok": True}


@router.post("/verify-email")
def verify_email(request: Request, data: dict = Body(default={})):
    check_origin(request)
    token = str(data.get("token", ""))
    with cursor() as cur:
        cur.execute("UPDATE users SET email_verified=TRUE, verify_token_hash=NULL, verify_expires=NULL "
                    "WHERE verify_token_hash=%s AND verify_expires > now() RETURNING id", (_hash(token),))
        if not cur.fetchone():
            return fail("invalid_or_expired")
    return {"ok": True}


@router.post("/resend-verification")
def resend(request: Request, data: dict = Body(default={})):
    check_origin(request)
    if not resend_throttle.allow(client_ip(request)):
        return fail("too_many_attempts")
    email = str(data.get("email", "")).strip().lower()
    with cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email=%s AND email_verified=FALSE AND password_hash IS NOT NULL", (email,))
        row = cur.fetchone()
        token = _new_verification(cur, row["id"]) if row else None
    if token:
        try:
            mailer.send_verification(email, f"{config.PUBLIC_BASE_URL}/verify.html?token={token}")
        except Exception as exc:
            log.warning("Reenvio NO enviado a %s: %r", email, exc)
            return fail("email_failed")
    return {"ok": True}  # misma respuesta exista o no el correo


@router.post("/login")
def login(request: Request, data: dict = Body(default={})):
    check_origin(request)
    if not login_throttle.allow(client_ip(request)):
        return fail("too_many_attempts")
    ident, pw = str(data.get("identifier", "")).strip().lower(), str(data.get("password", ""))
    with cursor() as cur:
        cur.execute("SELECT id, username, password_hash, email_verified FROM users WHERE lower(username)=%s OR email=%s", (ident, ident))
        user = cur.fetchone()
    valid = check_password(pw, user["password_hash"] if user and user["password_hash"] else DUMMY_HASH)
    if not user or not user["password_hash"] or not valid:
        return fail("invalid_credentials")
    if not user["email_verified"]:
        return fail("not_verified")
    sid = _login_response(request, user["id"], "password", None)
    resp = JSONResponse({"ok": True, "user": {"username": user["username"]}})
    set_cookie(resp, COOKIE, make_token(sid), config.SESSION_TTL_HOURS * 3600)
    return resp


@router.post("/logout")
async def logout(request: Request):
    check_origin(request)
    s = await run_in_threadpool(current_session, request.cookies.get(COOKIE))
    if s:
        await run_in_threadpool(end_session, s["sid"])
        await chat.kick(s["sid"])
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE, path="/")
    return resp


# ---- login con 42 (sin avatar) ----
def _to_login(error):
    return RedirectResponse(f"/login.html?error={error}", status_code=302)


@router.get("/42/login")
def ft_login():
    if not config.FT_ID or not config.FT_SECRET:
        log.warning("42: faltan FORTYTWO_CLIENT_ID / FORTYTWO_CLIENT_SECRET en el entorno del backend")
        return _to_login("oauth_unavailable")
    state = secrets.token_urlsafe(24)
    url = FT_AUTH + "?" + urllib.parse.urlencode({
        "client_id": config.FT_ID, "redirect_uri": f"{config.PUBLIC_BASE_URL}/api/auth/42/callback",
        "response_type": "code", "scope": "public", "state": state})
    resp = RedirectResponse(url, status_code=302)
    set_cookie(resp, "oauth_state", state, 600, path="/api/auth/42")
    return resp


def _post_json(url, form):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode(), method="POST", headers=UA_HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _get_json(url, token):
    req = urllib.request.Request(url, headers={**UA_HEADERS, "Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _find_or_create_42_user(me):
    ft_id, email = int(me["id"]), str(me["email"]).lower()
    base = (re.sub(r"[^A-Za-z0-9_-]", "", str(me["login"]))[:20] or "user42").ljust(3, "_")
    with cursor() as cur:
        cur.execute("SELECT id FROM users WHERE fortytwo_id=%s", (ft_id,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("SELECT id, email_verified FROM users WHERE email=%s", (email,))
        row = cur.fetchone()
        if row:
            # si la cuenta no estaba verificada se anula su contrasenya (evita pre-registros maliciosos)
            cur.execute("UPDATE users SET fortytwo_id=%s, email_verified=TRUE, "
                        "password_hash = CASE WHEN email_verified THEN password_hash ELSE NULL END WHERE id=%s", (ft_id, row["id"]))
            return row["id"]
        name = base
        while True:
            cur.execute("SELECT 1 FROM users WHERE lower(username)=lower(%s)", (name,))
            if not cur.fetchone():
                break
            name = base[:15] + str(secrets.randbelow(10000)).zfill(4)
        cur.execute("INSERT INTO users (username, email, email_verified, fortytwo_id) VALUES (%s,%s,TRUE,%s) RETURNING id",
                    (name, email, ft_id))
        return cur.fetchone()["id"]


@router.get("/42/callback")
def ft_callback(request: Request, code: str = "", state: str = ""):
    saved = request.cookies.get("oauth_state")
    if not code or not state or not saved or not secrets.compare_digest(state, saved):
        log.warning("42 callback rechazado: code=%s state=%s cookie_estado=%s (si falta code, 42 devolvio un error)",
                    bool(code), bool(state), bool(saved))
        return _to_login("oauth_failed")
    try:
        tok = _post_json(FT_TOKEN, {"grant_type": "authorization_code", "client_id": config.FT_ID,
                                    "client_secret": config.FT_SECRET, "code": code,
                                    "redirect_uri": f"{config.PUBLIC_BASE_URL}/api/auth/42/callback"})
        uid = _find_or_create_42_user(_get_json(FT_ME, tok["access_token"]))
        sid = _login_response(request, uid, "42", None)
    except Exception as exc:
        detail = exc.read().decode(errors="replace")[:300] if hasattr(exc, "read") else ""
        log.warning("42 callback fallo: %r %s | redirect_uri usada=%s", exc, detail, f"{config.PUBLIC_BASE_URL}/api/auth/42/callback")
        return _to_login("oauth_failed")
    resp = RedirectResponse("/home.html", status_code=302)
    set_cookie(resp, COOKIE, make_token(sid), config.SESSION_TTL_HOURS * 3600)
    resp.delete_cookie("oauth_state", path="/api/auth/42")
    return resp
