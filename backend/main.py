from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from backend import config, db
from backend.routers import auth, chat, test_api, rooms, test_api


@asynccontextmanager
async def lifespan(app):
    if not config.JWT_SECRET:
        raise RuntimeError("Falta JWT_SECRET en .env")
    db.init_pool()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def no_cache(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health():
    return {"ok": True}


app.include_router(auth.router)
app.include_router(test_api.router)
app.include_router(chat.router)
app.include_router(rooms.router)
