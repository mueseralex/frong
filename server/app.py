"""Frong.ai API — auth, chat, tools. Run: uvicorn app:app --host 0.0.0.0 --port 8787"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
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
    PROCESS_API,
    SESSION_COOKIE,
    SESSION_DAYS,
    WALLET_API,
)
from db import delete_session, get_chat, init_db, session_user  # noqa: E402
from proxy import forward  # noqa: E402
import wallet_api  # noqa: E402
from tools.dune import activity_snapshot, cache_snapshot_file, upload_to_dune  # noqa: E402

FRONTEND_URL = os.environ.get("FRONG_FRONTEND_URL", FRONG_SITE_URL).rstrip("/")
DIST = Path(os.environ.get("FRONG_DIST", str(PROJECT / "dist")))
WALLETS_DIST = Path(os.environ.get("FRONG_WALLETS_DIST", str(PROJECT / "dist-wallets")))
UPLOAD_DIST = Path(os.environ.get("FRONG_UPLOAD_DIST", str(PROJECT / "dist-upload")))

# Disable stock Swagger at /docs — that path redirects to the public wallet API reference.
app = FastAPI(title="frong.ai", version="0.1.0", docs_url=None, redoc_url=None)
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
    # Tiny OAuth fingerprint so we can confirm which Client ID is live (not secret).
    from config import X_CLIENT_ID

    return {
        "ok": True,
        "service": "frong.ai",
        "oauth_id_mark": (X_CLIENT_ID[8:16] if len(X_CLIENT_ID) >= 16 else None),
    }


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
        async for ev in chat_turn(
            user["x_user_id"],
            body.message,
            handle=user.get("handle"),
        ):
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


def _safe_file(root: Path, rel: str) -> Path | None:
    if not root.is_dir():
        return None
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    return None


def _dist_file(rel: str) -> Path | None:
    return _safe_file(DIST, rel)


def _wallets_file(rel: str) -> Path | None:
    return _safe_file(WALLETS_DIST, rel)


def _wallets_response(rel: str = "") -> FileResponse | None:
    rel = rel.strip("/")
    if rel:
        asset = _wallets_file(rel)
        if asset:
            return FileResponse(asset)
        # SPA/MPA fallbacks: /wallets/packs → packs/index.html
        nested = _wallets_file(f"{rel}/index.html")
        if nested:
            return FileResponse(nested)
        return None
    index_path = _wallets_file("index.html")
    return FileResponse(index_path) if index_path else None


def _legal_page(title: str, body: str) -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title} — frong.ai</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:40rem;margin:2rem auto;padding:0 1rem;line-height:1.5;color:#111;background:#fff}}
a{{color:#111}}
</style></head><body>
<p><a href="/">frong.ai</a></p>
<h1>{title}</h1>
{body}
</body></html>"""
    return HTMLResponse(html)


@app.get("/privacy")
def privacy():
    return _legal_page(
        "Privacy Policy",
        """
<p>Frong (frong.ai) lets you sign in with X so we can create a session and personalize chat.</p>
<p>When you sign in with X we receive your X user id, username, display name, and profile image. We store these for your account/session. We do not sell X data.</p>
<p>Chat messages and analysis requests may be stored to provide the product. Contact: via @frong_ai on X.</p>
""",
    )


@app.get("/terms")
def terms():
    return _legal_page(
        "Terms of Service",
        """
<p>Frong is an experimental chat tool for wallet/contract analysis on Robinhood chain. It is not financial advice.</p>
<p>You are responsible for how you use outputs. We may change or discontinue the service at any time.</p>
<p>By using frong.ai you agree to these terms and the Privacy Policy.</p>
""",
    )


# Prefer direct Postgres when configured (Railway → api.frong.ai is flaky).
if wallet_api.enabled():
    app.include_router(wallet_api.router, prefix="/wallet-api")


@app.api_route("/wallet-api/{path:path}", methods=["GET", "OPTIONS"])
async def wallet_api_proxy(path: str, request: Request):
    """Browser-facing wallet DB proxy (avoids flaky api.* subdomain DNS)."""
    if wallet_api.enabled():
        raise HTTPException(404, detail="not found")
    return await forward(
        request,
        upstream_base=WALLET_API,
        upstream_path=path,
        allow_methods=("GET", "OPTIONS"),
    )



def _site_logo_png() -> Path | None:
    """Pink round dot for browser tabs."""
    for candidate in (
        DIST / "logo-dot.png",
        PROJECT / "public" / "logo-dot.png",
        DIST / "logo.png",
        PROJECT / "public" / "logo.png",
        WALLETS_DIST / "logo-dot.png",
        WALLETS_DIST / "logo.png",
        UPLOAD_DIST / "logo-dot.png",
        UPLOAD_DIST / "logo.png",
    ):
        if candidate.is_file():
            return candidate
    return None


def _site_logo_jpg() -> Path | None:
    """Square source for Open Graph / Google preview cards."""
    for candidate in (
        DIST / "logo.jpg",
        PROJECT / "public" / "logo.jpg",
        WALLETS_DIST / "logo.jpg",
        UPLOAD_DIST / "logo.jpg",
    ):
        if candidate.is_file():
            return candidate
    return None


@app.get("/logo-dot.png")
@app.get("/logo.png")
@app.get("/favicon.ico")
@app.get("/favicon.svg")
@app.get("/frong.svg")
@app.get("/wallets/logo-dot.png")
@app.get("/wallets/logo.png")
@app.get("/wallets/favicon.svg")
@app.get("/wallets/frong.svg")
@app.get("/upload/logo-dot.png")
@app.get("/upload/logo.png")
@app.get("/upload/favicon.svg")
@app.get("/upload/frong.svg")
def site_logo_png_routes():
    logo = _site_logo_png() or _site_logo_jpg()
    if not logo:
        raise HTTPException(404, detail="logo missing")
    media = "image/png" if logo.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(
        logo,
        media_type=media,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/logo.jpg")
@app.get("/wallets/logo.jpg")
@app.get("/upload/logo.jpg")
def site_logo_jpg_routes():
    logo = _site_logo_jpg()
    if not logo:
        raise HTTPException(404, detail="logo missing")
    return FileResponse(
        logo,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/apple-touch-icon.png")
@app.get("/wallets/apple-touch-icon.png")
@app.get("/upload/apple-touch-icon.png")
def apple_touch_icon():
    for candidate in (
        DIST / "apple-touch-icon.png",
        PROJECT / "public" / "apple-touch-icon.png",
        WALLETS_DIST / "apple-touch-icon.png",
        UPLOAD_DIST / "apple-touch-icon.png",
        _site_logo_png(),
    ):
        if candidate and Path(candidate).is_file():
            return FileResponse(
                candidate,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=86400"},
            )
    raise HTTPException(404, detail="logo missing")


@app.get("/wallets/newlogo.png")
@app.get("/wallets/mainlogo.png")
@app.get("/newlogo.png")
@app.get("/mainlogo.png")
def _gone_old_logos():
    """Old Hood artwork — intentionally removed."""
    return Response(
        content='{"detail":"logo removed"}',
        status_code=410,
        media_type="application/json",
        headers={
            "Cache-Control": "no-store, max-age=0",
            "CDN-Cache-Control": "no-store",
        },
    )


@app.api_route("/upload/api/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def upload_api_proxy(path: str, request: Request):
    """Browser-facing process/batch proxy under /upload/api/*."""
    return await forward(
        request,
        upstream_base=PROCESS_API,
        upstream_path=f"api/{path}",
        allow_methods=("GET", "POST", "OPTIONS"),
        timeout=120.0,
    )


def _upload_file(rel: str) -> Path | None:
    return _safe_file(UPLOAD_DIST, rel)


@app.get("/upload")
@app.get("/upload/")
def upload_index():
    index_path = _upload_file("index.html")
    if index_path:
        return FileResponse(index_path)
    raise HTTPException(404, detail="upload UI not built")


@app.get("/upload/{full_path:path}")
def upload_static(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404)
    asset = _upload_file(full_path)
    if asset:
        return FileResponse(asset)
    raise HTTPException(404)


@app.get("/database")
@app.get("/database/")
def redirect_database():
    return RedirectResponse("/wallets/", status_code=307)


@app.get("/packs")
@app.get("/packs/")
def redirect_packs():
    return RedirectResponse("/wallets/packs/", status_code=307)


@app.get("/docs")
@app.get("/docs/")
@app.get("/api-docs")
@app.get("/api-docs/")
def redirect_api_docs():
    return RedirectResponse("/wallets/api/", status_code=307)


@app.get("/wallets")
@app.get("/wallets/")
def wallets_index():
    resp = _wallets_response("")
    if resp:
        return resp
    raise HTTPException(404, detail="wallets UI not built")


@app.get("/wallets/{full_path:path}")
def wallets_spa(full_path: str):
    resp = _wallets_response(full_path)
    if resp:
        return resp
    # Fall back to database index for unknown /wallets/* paths
    index_path = _wallets_file("index.html")
    if index_path:
        return FileResponse(index_path)
    raise HTTPException(404)


@app.get("/")
def index():
    index_path = _dist_file("index.html")
    if not index_path:
        return {"ok": True, "service": "frong.ai", "ui": "not built"}
    return FileResponse(index_path)


@app.get("/{full_path:path}")
def spa(full_path: str):
    """Serve Vite assets; fall back to index.html for client routes."""
    if full_path.startswith(
        (
            "api/",
            "auth/",
            "health",
            "privacy",
            "terms",
            "wallets",
            "wallet-api",
            "upload",
            "database",
            "packs",
            "docs",
            "api-docs",
        )
    ):
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
