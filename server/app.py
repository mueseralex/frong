"""Frong.ai API — auth, chat, tools. Run: uvicorn app:app --host 0.0.0.0 --port 8787"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auth_x import (  # noqa: E402
    begin_login,
    dev_login,
    finish_login,
    oauth_configured,
    public_user,
)
from chat_service import chat_turn  # noqa: E402
from config import (  # noqa: E402
    CORS_ORIGINS,
    DEV_AUTH,
    FRONG_SITE_URL,
    SESSION_COOKIE,
    SESSION_DAYS,
)
from db import delete_session, get_chat, init_db, session_user  # noqa: E402
from tools.dune import activity_snapshot, cache_snapshot_file, upload_to_dune  # noqa: E402

FRONTEND_URL = os.environ.get("FRONG_FRONTEND_URL", FRONG_SITE_URL).rstrip("/")
DIST = Path(os.environ.get("FRONG_DIST", str(PROJECT / "dist")))

app = FastAPI(title="frong.ai", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


def _user(request: Request):
    return session_user(request.cookies.get(SESSION_COOKIE))


def _set_session_cookie(response: Response, token: str) -> None:
    secure = FRONG_SITE_URL.startswith("https") or os.environ.get("FRONG_SECURE_COOKIES") == "1"
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_DAYS * 86400,
        secure=secure,
        path="/",
    )


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "frong.ai"}


@app.get("/api/me")
def me(request: Request) -> dict:
    user = _user(request)
    return {
        "user": public_user(user),
        "oauth": oauth_configured(),
        "dev_auth": DEV_AUTH,
        "site": FRONG_SITE_URL,
    }


@app.get("/auth/x")
async def auth_x() -> RedirectResponse:
    try:
        url, _state = begin_login()
    except Exception as e:
        raise HTTPException(500, str(e)) from e
    return RedirectResponse(url)


@app.get("/auth/x/callback")
async def auth_x_callback(code: str = "", state: str = "") -> RedirectResponse:
    if not code or not state:
        raise HTTPException(400, "missing code/state")
    try:
        token = await finish_login(code, state)
    except Exception as e:
        raise HTTPException(400, f"oauth failed: {e}") from e
    resp = RedirectResponse(f"{FRONTEND_URL}/")
    _set_session_cookie(resp, token)
    return resp


@app.post("/auth/dev")
def auth_dev(response: Response) -> dict:
    if not DEV_AUTH:
        raise HTTPException(403, "dev auth disabled")
    token = dev_login()
    _set_session_cookie(response, token)
    return {"ok": True, "user": public_user(session_user(token))}


@app.post("/auth/logout")
def logout(request: Request, response: Response) -> dict:
    delete_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@app.get("/api/chat")
def chat_history(request: Request) -> dict:
    user = _user(request)
    if not user:
        raise HTTPException(401, "login required")
    msgs = get_chat(user["x_user_id"])
    slim = []
    for m in msgs:
        item = {"role": m.get("role"), "content": m.get("content")}
        if m.get("report"):
            item["has_report"] = True
            r = m["report"]
            if isinstance(r, dict):
                item["report"] = {
                    k: r[k]
                    for k in ("tool", "ranked", "track", "ca", "ok", "error", "count")
                    if k in r
                }
        slim.append(item)
    return {"messages": slim}


@app.post("/api/chat")
async def chat(request: Request, body: ChatIn) -> StreamingResponse:
    user = _user(request)
    if not user:
        raise HTTPException(401, "login required")

    async def gen():
        async for ev in chat_turn(user["x_user_id"], body.message):
            yield f"data: {json.dumps(ev, ensure_ascii=True)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/dune/snapshot")
def dune_snap(request: Request) -> dict:
    user = _user(request)
    if not user:
        raise HTTPException(401, "login required")
    snap = activity_snapshot()
    cache_snapshot_file(snap)
    return snap


@app.post("/api/dune/sync")
async def dune_sync(request: Request) -> dict:
    user = _user(request)
    if not user:
        raise HTTPException(401, "login required")
    return await upload_to_dune()


def _dist_file(rel: str) -> Path | None:
    if not DIST.is_dir():
        return None
    candidate = (DIST / rel).resolve()
    try:
        candidate.relative_to(DIST.resolve())
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    return None


@app.get("/")
def index():
    index_path = _dist_file("index.html")
    if not index_path:
        return {"ok": True, "service": "frong.ai", "ui": "not built"}
    return FileResponse(index_path)


@app.get("/{full_path:path}")
def spa(full_path: str):
    """Serve Vite assets; fall back to index.html for client routes."""
    if full_path.startswith(("api/", "auth/", "health")):
        raise HTTPException(404)
    asset = _dist_file(full_path)
    if asset:
        return FileResponse(asset)
    index_path = _dist_file("index.html")
    if index_path:
        return FileResponse(index_path)
    raise HTTPException(404)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8787")),
        reload=True,
    )
