"""Live CA → top traders (GMGN) → scrape → rank."""

from __future__ import annotations

import re
from typing import Any

import httpx

from config import CA_TRADER_LIMIT, GMGN_BEARER, GMGN_CHAIN
from tools.wallets import analyze_wallets

CA_RE = re.compile(r"0x[a-fA-F0-9]{40}")


def extract_cas(text: str) -> list[str]:
    """Heuristic: treat 0x addresses mentioned with 'ca' context, or all if tagged."""
    return []


def looks_like_ca_request(text: str) -> str | None:
    """Return CA address if user asks about a contract, else None."""
    t = (text or "").lower()
    addrs = CA_RE.findall(text or "")
    if not addrs:
        return None
    ca_hints = (
        "ca ",
        "ca:",
        " ca",
        "contract",
        "token",
        "migrate",
        "migration",
        "launch",
        "pair",
        "traders",
        "holders",
    )
    if any(h in t for h in ca_hints):
        return addrs[0]
    return None


async def fetch_top_traders(ca: str, limit: int = CA_TRADER_LIMIT) -> list[str]:
    if not CA_RE.fullmatch(ca):
        raise ValueError("invalid ca")
    url = (
        f"https://gmgn.ai/vas/api/v1/token_traders/{GMGN_CHAIN}/{ca}"
        f"?limit={limit}&orderby=profit&direction=desc"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) frong.ai",
        "Accept": "application/json",
        "Referer": "https://gmgn.ai/",
    }
    if GMGN_BEARER:
        headers["authorization"] = f"Bearer {GMGN_BEARER}"

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        r = await client.get(url, timeout=25.0)
        if r.status_code in (401, 403) and not GMGN_BEARER:
            raise RuntimeError(
                "GMGN blocked trader pull — set FRONG_GMGN_BEARER on the Frong server"
            )
        r.raise_for_status()
        body = r.json()
        if body.get("code") != 0:
            raise RuntimeError(body.get("message") or "gmgn traders error")
        traders = (body.get("data") or {}).get("list") or []
        return [t["address"] for t in traders if t.get("address")][:limit]


async def analyze_ca(ca: str, limit: int = CA_TRADER_LIMIT) -> dict[str, Any]:
    ca = ca.strip()
    if not CA_RE.fullmatch(ca):
        return {"ok": False, "error": "invalid ca", "tool": "analyze_ca"}
    try:
        traders = await fetch_top_traders(ca, limit=limit)
    except Exception as e:
        return {"ok": False, "error": str(e), "tool": "analyze_ca", "ca": ca}

    if not traders:
        return {
            "ok": False,
            "error": "no traders returned for ca",
            "tool": "analyze_ca",
            "ca": ca,
        }

    result = await analyze_wallets(traders, force_scrape=False)
    result["tool"] = "analyze_ca"
    result["ca"] = ca
    result["trader_count"] = len(traders)
    result["prefix_ca"] = ca[:6] + "…" + ca[-4:]
    # Prefer forcing scrape for freshness on CA reports when many missing
    if result.get("ok") and len(result.get("wallets") or []) < max(3, len(traders) // 3):
        result = await analyze_wallets(traders, force_scrape=True)
        result["tool"] = "analyze_ca"
        result["ca"] = ca
        result["trader_count"] = len(traders)
        result["prefix_ca"] = ca[:6] + "…" + ca[-4:]
        result["fresh_scrape"] = True
    return result


async def fetch_trending_cas(limit: int = 10) -> list[str]:
    """Pull fresh trending CAs for migration watcher."""
    url = (
        f"https://gmgn.ai/trs/api/v1/trending_rank"
        f"?device_id=frong&client_id=frong&from_app=yes"
        f"&app_ver=1&tz_name=UTC&tz_offset=0&app_lang=en&os=web"
        f"&chain={GMGN_CHAIN}&limit={limit}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 frong.ai",
        "Accept": "application/json",
        "Referer": "https://gmgn.ai/",
    }
    if GMGN_BEARER:
        headers["authorization"] = f"Bearer {GMGN_BEARER}"
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        r = await client.get(url, timeout=25.0)
        r.raise_for_status()
        body = r.json()
        rows = (body.get("data") or {}).get("rank") or (body.get("data") or {}).get("list") or []
        out = []
        for row in rows:
            addr = row.get("address") or row.get("token_address") or row.get("ca")
            if addr and CA_RE.fullmatch(str(addr)):
                out.append(str(addr))
        return out[:limit]
