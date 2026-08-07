#!/usr/bin/env -S python3 -u
"""
One-shot OAuth 2.0 PKCE for the @frong_ai bot user token.

Prereq (Developer Portal → your app → User authentication settings):
  - App permissions: Read and write
  - Callback URL includes exactly:
      http://127.0.0.1:8788/callback

Run (logged into X as @frong_ai in your browser):
  python3 scripts/x_bot_auth.py

Writes X_BOT_ACCESS_TOKEN, X_BOT_REFRESH_TOKEN, X_BOT_USER_ID into:
  - server/.env
  - ~/.frong/x.env
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
SERVER_ENV = ROOT / "server" / ".env"
FRONG_ENV = Path.home() / ".frong" / "x.env"

AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
ME_URL = "https://api.twitter.com/2/users/me"

REDIRECT_URI = "http://127.0.0.1:8788/callback"
BOT_SCOPES = "tweet.read tweet.write users.read offline.access"

# Filled by the callback handler
_result: dict = {}


def _load_env_files() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in (SERVER_ENV, FRONG_ENV, ROOT / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return out


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    if len(verifier) > 128:
        verifier = verifier[:128]
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return verifier, challenge


def _upsert_env(path: Path, updates: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
    keys_done = set()
    out: list[str] = []
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k = line.split("=", 1)[0].strip()
            if k in updates:
                out.append(f"{k}={updates[k]}")
                keys_done.add(k)
                continue
        out.append(line)
    for k, v in updates.items():
        if k not in keys_done:
            out.append(f"{k}={v}")
    text = "\n".join(out).rstrip() + "\n"
    path.write_text(text, encoding="utf-8")
    print(f"  wrote {path}")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quiet
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")
            return
        qs = parse_qs(parsed.query)
        if qs.get("error"):
            _result["error"] = qs.get("error_description", qs["error"])[0]
        else:
            _result["code"] = (qs.get("code") or [""])[0]
            _result["state"] = (qs.get("state") or [""])[0]
        body = (
            b"<html><body style='font-family:system-ui;padding:2rem'>"
            b"<h2>frong bot auth</h2>"
            b"<p>You can close this tab and return to the terminal.</p>"
            b"</body></html>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    env = _load_env_files()
    client_id = env.get("X_CLIENT_ID", "").strip()
    client_secret = env.get("X_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("Missing X_CLIENT_ID / X_CLIENT_SECRET in server/.env or ~/.frong/x.env")
        return 1

    print("=== frong.ai X bot auth ===")
    print(f"Redirect URI (must be in the X app): {REDIRECT_URI}")
    print(f"Scopes: {BOT_SCOPES}")
    print("In your browser, make sure you are logged into X as @frong_ai before approving.")
    print()

    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(24)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": BOT_SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTH_URL}?{urlencode(params, quote_via=quote)}"

    server = HTTPServer(("127.0.0.1", 8788), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print("Opening browser…")
    print(auth_url)
    print()
    webbrowser.open(auth_url)

    deadline = time.time() + 300
    while time.time() < deadline and "code" not in _result and "error" not in _result:
        time.sleep(0.2)
    server.shutdown()

    if _result.get("error"):
        print(f"Auth error: {_result['error']}")
        return 1
    if not _result.get("code"):
        print("Timed out waiting for callback. Did you approve in the browser?")
        return 1
    if _result.get("state") != state:
        print("State mismatch — try again.")
        return 1

    print("Exchanging code for tokens…")
    data = {
        "grant_type": "authorization_code",
        "code": _result["code"],
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
        "client_id": client_id,
    }
    with httpx.Client(timeout=30.0) as client:
        tr = client.post(TOKEN_URL, data=data, auth=(client_id, client_secret))
        if tr.status_code >= 400:
            print(f"Token exchange failed {tr.status_code}: {tr.text[:500]}")
            return 1
        tokens = tr.json()
        access = tokens.get("access_token") or ""
        refresh = tokens.get("refresh_token") or ""
        if not access:
            print("No access_token in response:", tokens)
            return 1

        me = client.get(
            ME_URL,
            params={"user.fields": "username,name"},
            headers={"Authorization": f"Bearer {access}"},
        )
        if me.status_code >= 400:
            print(f"/users/me failed {me.status_code}: {me.text[:400]}")
            return 1
        user = (me.json().get("data") or {})
        user_id = str(user.get("id") or "")
        username = user.get("username") or "?"

    print()
    print(f"Authorized as @{username} (id={user_id})")
    if username.lower() != "frong_ai":
        print("WARNING: expected @frong_ai — you may have approved with the wrong account.")
        print("Re-run after switching to @frong_ai in the browser.")

    updates = {
        "X_BOT_ACCESS_TOKEN": access,
        "X_BOT_USER_ID": user_id,
    }
    if refresh:
        updates["X_BOT_REFRESH_TOKEN"] = refresh

    print("Saving…")
    _upsert_env(SERVER_ENV, updates)
    _upsert_env(FRONG_ENV, updates)

    # Optional: also set Railway if CLI is available (non-fatal)
    try:
        import shutil
        import subprocess

        if shutil.which("railway"):
            print("Setting Railway variables on frong service…")
            cmd = ["railway", "variables", "set"]
            for k, v in updates.items():
                cmd.append(f"{k}={v}")
            subprocess.run(cmd, cwd=str(ROOT), check=False, capture_output=True)
    except Exception as exc:  # noqa: BLE001
        print(f"(Railway skip: {exc})")

    print()
    print("Done. Next:")
    print("  cd server && source .venv/bin/activate && python -m bot.worker")
    print("Then mention @frong_ai with a wallet or CA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
