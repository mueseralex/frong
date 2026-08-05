"""X (Twitter) OAuth 2.0 PKCE login for frong.ai."""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

from config import (
    DEV_AUTH,
    X_CALLBACK_URL,
    X_CLIENT_ID,
    X_CLIENT_SECRET,
    X_SCOPES,
)
from db import create_session, upsert_user

AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
ME_URL = "https://api.twitter.com/2/users/me"

# short-lived PKCE state (in-memory; fine for single-process v1)
_pending: dict[str, dict[str, str]] = {}


def oauth_configured() -> bool:
    return bool(X_CLIENT_ID and X_CLIENT_SECRET)


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return verifier, challenge


def begin_login() -> tuple[str, str]:
    """Return (authorize_url, state)."""
    if not oauth_configured():
        raise RuntimeError("X OAuth not configured (X_CLIENT_ID / X_CLIENT_SECRET)")
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(24)
    _pending[state] = {"verifier": verifier}
    params = {
        "response_type": "code",
        "client_id": X_CLIENT_ID,
        "redirect_uri": X_CALLBACK_URL,
        "scope": X_SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URL}?{urlencode(params)}", state


async def finish_login(code: str, state: str) -> str:
    """Exchange code → user → session token."""
    pending = _pending.pop(state, None)
    if not pending:
        raise RuntimeError("invalid or expired oauth state")
    verifier = pending["verifier"]
    auth = (X_CLIENT_ID, X_CLIENT_SECRET)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": X_CALLBACK_URL,
        "code_verifier": verifier,
        "client_id": X_CLIENT_ID,
    }
    async with httpx.AsyncClient() as client:
        tr = await client.post(TOKEN_URL, data=data, auth=auth, timeout=30.0)
        tr.raise_for_status()
        tokens = tr.json()
        access = tokens["access_token"]
        ur = await client.get(
            ME_URL,
            params={"user.fields": "profile_image_url,name,username"},
            headers={"Authorization": f"Bearer {access}"},
            timeout=20.0,
        )
        ur.raise_for_status()
        user = (ur.json().get("data") or {})
    x_id = str(user["id"])
    handle = user.get("username") or x_id
    upsert_user(
        x_id,
        handle=handle,
        name=user.get("name"),
        avatar_url=user.get("profile_image_url"),
    )
    return create_session(x_id)


def dev_login(handle: str = "frong_dev") -> str:
    if not DEV_AUTH:
        raise RuntimeError("dev auth disabled")
    user = upsert_user("dev-local", handle=handle, name="Frong Dev")
    return create_session(user["x_user_id"])


def public_user(user: dict[str, Any] | None) -> dict[str, Any] | None:
    if not user:
        return None
    return {
        "id": user["x_user_id"],
        "handle": user["handle"],
        "name": user.get("name"),
        "avatar_url": user.get("avatar_url"),
    }
