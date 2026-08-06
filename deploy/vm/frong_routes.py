"""Frong scrape sidecar routes — mounted on the process VM under /api/frong/*.

Auth: header X-Frong-Key (or Authorization: Bearer) must match FRONG_SCRAPE_SECRET.
Uses the shared GMGN JWT (file synced from the minter DB).
"""

from __future__ import annotations

import hmac
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
CHAIN = os.environ.get("FRONG_CHAIN", "robinhood")
CA_TRADER_LIMIT = int(os.environ.get("FRONG_CA_TRADER_LIMIT", "20"))
FRONG_MAX_WALLETS = int(os.environ.get("FRONG_MAX_WALLETS", "25"))
FRONG_CONCURRENCY = int(os.environ.get("FRONG_SCRAPE_CONCURRENCY", "3"))

router = APIRouter(prefix="/api/frong", tags=["frong"])


def _secret() -> str:
    return os.environ.get("FRONG_SCRAPE_SECRET", "").strip()


def _require_key(
    x_frong_key: Optional[str] = Header(default=None, alias="X-Frong-Key"),
    authorization: Optional[str] = Header(default=None),
) -> None:
    expected = _secret()
    if not expected:
        raise HTTPException(503, "frong scrape secret not configured on worker")
    provided = (x_frong_key or "").strip()
    if not provided and authorization:
        auth = authorization.strip()
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(401, "unauthorized")


class TradersBody(BaseModel):
    ca: str
    limit: int = Field(default=CA_TRADER_LIMIT, ge=1, le=50)


class WalletsBody(BaseModel):
    addresses: list[str]
    force: bool = False


class AnalyzeCaBody(BaseModel):
    ca: str
    limit: int = Field(default=CA_TRADER_LIMIT, ge=1, le=50)


def _get_bearer(ensure_token, scraper) -> str:
    if not ensure_token():
        raise HTTPException(503, "gmgn token unavailable — minter refreshing")
    token = scraper.get_valid_token(wait=False)
    if not token:
        raise HTTPException(503, "gmgn token unavailable — minter refreshing")
    return token


def fetch_top_traders(ca: str, limit: int, bearer: str, scraper) -> list[dict[str, Any]]:
    """Pull traders with Bearer via scraper's tls_client session.

    On 429/403, rotate the process VPN IP the same way the main scraper does.
    """
    url = (
        f"https://gmgn.ai/vas/api/v1/token_traders/{CHAIN}/{ca}"
        f"?limit={limit}&orderby=profit&direction=desc"
    )
    headers = {
        **getattr(scraper, "HEADERS", {}),
        "authorization": f"Bearer {bearer}",
        "Referer": "https://gmgn.ai/",
        "Origin": "https://gmgn.ai",
    }
    last_err = None
    for attempt in range(4):
        try:
            response = scraper.session.get(url, headers=headers, timeout_seconds=20)
            if response.status_code in (401,):
                raise HTTPException(503, "gmgn token rejected — waiting for minter refresh")
            if response.status_code in (403, 429):
                last_err = f"HTTP {response.status_code}"
                if hasattr(scraper, "rotate_ip"):
                    try:
                        scraper.rotate_ip()
                    except Exception:
                        pass
                time.sleep(0.5 + attempt)
                continue
            if response.status_code != 200:
                last_err = f"HTTP {response.status_code}"
                time.sleep(0.3)
                continue
            body = response.json()
            if body.get("code") != 0:
                msg = str(body.get("message") or "gmgn traders error")
                if "token" in msg.lower():
                    raise HTTPException(503, "gmgn token rejected — waiting for minter refresh")
                raise HTTPException(502, msg)
            traders = (body.get("data") or {}).get("list") or []
            out: list[dict[str, Any]] = []
            for t in traders:
                addr = t.get("address")
                if not addr or not ADDR_RE.match(str(addr)):
                    continue
                out.append(
                    {
                        "address": str(addr),
                        "profit": t.get("profit") or t.get("realized_profit"),
                        "pnl": t.get("pnl") or t.get("unrealized_profit"),
                        "buy_volume_cur": t.get("buy_volume_cur"),
                        "sell_volume_cur": t.get("sell_volume_cur"),
                    }
                )
                if len(out) >= limit:
                    break
            if out:
                return out
            # Empty list — fall through to scraper helper (may use different path/headers).
            break
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            time.sleep(0.3)

    # Fallback: address-only helper used by the main scrape loop.
    try:
        addrs = scraper.get_top_traders_addresses(ca, limit=limit) or []
        out = [{"address": a} for a in addrs if ADDR_RE.match(str(a))]
        if out:
            return out[:limit]
    except Exception as exc:  # noqa: BLE001
        last_err = last_err or str(exc)

    if last_err and ("429" in str(last_err) or "403" in str(last_err)):
        raise HTTPException(503, "gmgn rate limited — try again shortly")
    raise HTTPException(502, f"traders fetch failed: {last_err or 'empty'}")

def scrape_wallets(addresses: list[str], scraper, concurrency: int) -> list[dict[str, Any]]:
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = {pool.submit(scraper.scrape_wallet, addr, False): addr for addr in addresses}
        for future in as_completed(futures):
            addr = futures[future]
            try:
                results[addr] = future.result() or {}
            except Exception as exc:  # noqa: BLE001
                results[addr] = {"address": addr, "error": str(exc)}
    ordered = []
    for addr in addresses:
        data = results.get(addr) or {}
        if data and not data.get("address"):
            data = {**data, "address": addr}
        ordered.append(data if data else {"address": addr, "status": "no_data"})
    return ordered


def bind_frong_routes(*, ensure_token, scraper, log) -> APIRouter:
    """Attach handlers that close over process-worker helpers."""

    @router.get("/health")
    def frong_health(
        x_frong_key: Optional[str] = Header(default=None, alias="X-Frong-Key"),
        authorization: Optional[str] = Header(default=None),
    ) -> dict:
        _require_key(x_frong_key, authorization)
        ttl = -1.0
        try:
            token = scraper.get_valid_token(wait=False)
            if token:
                exp = scraper._jwt_payload(token).get("exp")
                ttl = (exp - time.time()) if exp else float("inf")
        except Exception:
            ttl = -1.0
        return {
            "ok": True,
            "worker": "frong-scrape",
            "chain": CHAIN,
            "token_ttl_sec": None if ttl == float("inf") else int(ttl),
        }

    @router.post("/traders")
    def frong_traders(
        body: TradersBody,
        x_frong_key: Optional[str] = Header(default=None, alias="X-Frong-Key"),
        authorization: Optional[str] = Header(default=None),
    ) -> dict:
        _require_key(x_frong_key, authorization)
        ca = body.ca.strip()
        if not ADDR_RE.match(ca):
            raise HTTPException(400, "invalid ca")
        bearer = _get_bearer(ensure_token, scraper)
        try:
            traders = fetch_top_traders(ca, body.limit, bearer, scraper)
        except HTTPException:
            scraper.invalidate_token()
            raise
        return {
            "ok": True,
            "ca": ca,
            "traders": traders,
            "addresses": [t["address"] for t in traders],
            "count": len(traders),
        }

    @router.post("/wallets/scrape")
    def frong_scrape_wallets(
        body: WalletsBody,
        x_frong_key: Optional[str] = Header(default=None, alias="X-Frong-Key"),
        authorization: Optional[str] = Header(default=None),
    ) -> dict:
        _require_key(x_frong_key, authorization)
        seen: set[str] = set()
        addresses: list[str] = []
        for raw in body.addresses:
            addr = (raw or "").strip()
            if ADDR_RE.match(addr) and addr.lower() not in seen:
                seen.add(addr.lower())
                addresses.append(addr)
            if len(addresses) >= FRONG_MAX_WALLETS:
                break
        if not addresses:
            raise HTTPException(400, "no valid wallets")
        if not ensure_token():
            raise HTTPException(503, "gmgn token unavailable — minter refreshing")
        wallets = scrape_wallets(addresses, scraper, FRONG_CONCURRENCY)
        ok = sum(
            1 for w in wallets if w and not w.get("error") and w.get("total_profit") is not None
        )
        return {"ok": True, "count": len(wallets), "ok_count": ok, "wallets": wallets}

    @router.post("/analyze/ca")
    def frong_analyze_ca(
        body: AnalyzeCaBody,
        x_frong_key: Optional[str] = Header(default=None, alias="X-Frong-Key"),
        authorization: Optional[str] = Header(default=None),
    ) -> dict:
        _require_key(x_frong_key, authorization)
        ca = body.ca.strip()
        if not ADDR_RE.match(ca):
            raise HTTPException(400, "invalid ca")
        bearer = _get_bearer(ensure_token, scraper)
        try:
            traders = fetch_top_traders(ca, body.limit, bearer, scraper)
        except HTTPException:
            scraper.invalidate_token()
            raise
        addresses = [t["address"] for t in traders]
        if not addresses:
            return {
                "ok": False,
                "error": "no traders returned for ca",
                "ca": ca,
                "tool": "analyze_ca",
            }
        wallets = scrape_wallets(addresses, scraper, FRONG_CONCURRENCY)
        return {
            "ok": True,
            "tool": "analyze_ca",
            "ca": ca,
            "trader_count": len(addresses),
            "traders": traders,
            "wallets": wallets,
            "count": len(wallets),
        }

    return router
