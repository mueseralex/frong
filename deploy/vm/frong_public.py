"""Frong traders routes for the main scraper VM public API (api.hoodwallets.com).

Mounted at /v1/frong/* — uses shared DB JWT + tls_client. Wallet scrapes stay on
the process VM; this path is for CA → traders only (better VPN / less 429s).
"""

from __future__ import annotations

import hmac
import os
import re
import time
from typing import Any, Optional

import tls_client
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

import db

ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
CHAIN = os.environ.get("FRONG_CHAIN", os.environ.get("CHAIN", "robinhood"))
CA_TRADER_LIMIT = int(os.environ.get("FRONG_CA_TRADER_LIMIT", "20"))

# Same path shape as the process-VM sidecar so Railway can point FRONG_SCRAPE_API
# at either host without code changes.
router = APIRouter(prefix="/api/frong", tags=["frong"])

def _secret() -> str:
    return os.environ.get("FRONG_SCRAPE_SECRET", "").strip()


def _require_key(
    x_frong_key: Optional[str] = Header(default=None, alias="X-Frong-Key"),
    authorization: Optional[str] = Header(default=None),
) -> None:
    expected = _secret()
    if not expected:
        raise HTTPException(503, "frong scrape secret not configured")
    provided = (x_frong_key or "").strip()
    if not provided and authorization and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(401, "unauthorized")


def _bearer() -> str:
    row = db.get_token("gmgn_jwt")
    token = (row or {}).get("token") if row else None
    if not token:
        raise HTTPException(503, "gmgn token unavailable — minter refreshing")
    return token


class TradersBody(BaseModel):
    ca: str
    limit: int = Field(default=CA_TRADER_LIMIT, ge=1, le=50)


@router.get("/health")
def health(
    x_frong_key: Optional[str] = Header(default=None, alias="X-Frong-Key"),
    authorization: Optional[str] = Header(default=None),
) -> dict:
    _require_key(x_frong_key, authorization)
    ttl = None
    try:
        token = _bearer()
        # JWT exp is middle segment; avoid importing scraper.
        import base64
        import json

        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        exp = json.loads(base64.urlsafe_b64decode(part.encode())).get("exp")
        if exp:
            ttl = int(exp - time.time())
    except HTTPException:
        ttl = -1
    except Exception:
        ttl = -1
    return {"ok": True, "worker": "frong-traders-main", "chain": CHAIN, "token_ttl_sec": ttl}


@router.post("/traders")
def traders(
    body: TradersBody,
    x_frong_key: Optional[str] = Header(default=None, alias="X-Frong-Key"),
    authorization: Optional[str] = Header(default=None),
) -> dict:
    _require_key(x_frong_key, authorization)
    ca = body.ca.strip()
    if not ADDR_RE.match(ca):
        raise HTTPException(400, "invalid ca")
    bearer = _bearer()
    url = (
        f"https://gmgn.ai/vas/api/v1/token_traders/{CHAIN}/{ca}"
        f"?limit={body.limit}&orderby=profit&direction=desc"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) frong-traders",
        "Accept": "application/json",
        "Referer": "https://gmgn.ai/",
        "Origin": "https://gmgn.ai",
        "authorization": f"Bearer {bearer}",
    }
    session = tls_client.Session(client_identifier="chrome_120", random_tls_extension_order=True)
    last_err = None
    for attempt in range(3):
        try:
            response = session.get(url, headers=headers, timeout_seconds=20)
            if response.status_code == 401:
                raise HTTPException(503, "gmgn token rejected — waiting for minter refresh")
            if response.status_code in (403, 429):
                last_err = f"HTTP {response.status_code}"
                time.sleep(0.6 + attempt)
                continue
            if response.status_code != 200:
                last_err = f"HTTP {response.status_code}"
                time.sleep(0.3)
                continue
            data = response.json()
            if data.get("code") != 0:
                msg = str(data.get("message") or "gmgn traders error")
                if "token" in msg.lower():
                    raise HTTPException(503, "gmgn token rejected — waiting for minter refresh")
                raise HTTPException(502, msg)
            rows = (data.get("data") or {}).get("list") or []
            out: list[dict[str, Any]] = []
            for t in rows:
                addr = t.get("address")
                if not addr or not ADDR_RE.match(str(addr)):
                    continue
                out.append(
                    {
                        "address": str(addr),
                        "profit": t.get("profit") or t.get("realized_profit"),
                        "pnl": t.get("pnl") or t.get("unrealized_profit"),
                    }
                )
                if len(out) >= body.limit:
                    break
            return {
                "ok": True,
                "ca": ca,
                "traders": out,
                "addresses": [t["address"] for t in out],
                "count": len(out),
            }
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            time.sleep(0.3)
    if last_err and ("429" in str(last_err) or "403" in str(last_err)):
        raise HTTPException(503, "gmgn rate limited — try again shortly")
    raise HTTPException(502, f"traders fetch failed: {last_err}")
