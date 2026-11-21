# Operaciones sobre users.test (NULL / true / false). Siempre HTTP 200; el resultado va en "ok".
from fastapi import APIRouter, Request

from backend.db import cursor
from backend.security import COOKIE, check_origin, current_session

router = APIRouter(prefix="/api/test")


def _run(request, action):
    s = current_session(request.cookies.get(COOKIE))
    if not s:
        return {"ok": False, "error": "unauthenticated"}
    with cursor() as cur:
        cur.execute("SELECT test FROM users WHERE id=%s", (s["user_id"],))
        value = cur.fetchone()["test"]
        if action == "read":
            return {"ok": True, "value": value}
        if action == "create":
            if value is not None:
                return {"ok": False, "error": "already_exists"}
            new = True
        elif value is None:
            return {"ok": False, "error": "not_created"}
        else:
            new = (not value) if action == "update" else None
        cur.execute("UPDATE users SET test=%s WHERE id=%s", (new, s["user_id"]))
        return {"ok": True, "value": new}


@router.get("")
def read(request: Request):
    return _run(request, "read")


@router.post("")
def create(request: Request):
    check_origin(request)
    return _run(request, "create")


@router.put("")
def update(request: Request):
    check_origin(request)
    return _run(request, "update")


@router.delete("")
def delete(request: Request):
    check_origin(request)
    return _run(request, "delete")
