"""Wallet lookup + on-demand scrape via upstream APIs."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

import httpx

from config import (
    MAX_WALLETS_PER_REQUEST,
    PROCESS_API,
    WALLET_API,
)
from tools.rank import compact_wallet, rank_wallets

ADDR_RE = re.compile(r"0x[a-fA-F0-9]{40}")


def extract_addresses(text: str, limit: int = MAX_WALLETS_PER_REQUEST) -> list[str]:
    found = ADDR_RE.findall(text or "")
    # de-dupe preserve order
    out: list[str] = []
    seen: set[str] = set()
    for a in found:
        key = a.lower()
        if key not in seen:
            seen.add(key)
            out.append(a)
        if len(out) >= limit:
            break
    return out


async def lookup_wallet(client: httpx.AsyncClient, address: str) -> dict[str, Any] | None:
    url = f"{WALLET_API}/v1/wallets/{address}"
    try:
        r = await client.get(url, timeout=20.0)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        w = data.get("wallet") or data
        w["address"] = w.get("address") or address
        w["status"] = "cached"
        return w
    except Exception as e:
        return {"address": address, "status": "error", "error": str(e)}


async def submit_batch(client: httpx.AsyncClient, addresses: list[str]) -> str:
    r = await client.post(
        f"{PROCESS_API}/api/v1/batches",
        json={"addresses": addresses, "note": "frong"},
        timeout=30.0,
    )
    if r.status_code >= 400:
        # fallback older path
        r = await client.post(
            f"{PROCESS_API}/api/submit",
            json={"addresses": addresses, "note": "frong"},
            timeout=30.0,
        )
    r.raise_for_status()
    data = r.json()
    job_id = data.get("job_id") or data.get("id")
    if not job_id:
        raise RuntimeError(f"batch submit missing job_id: {data}")
    return str(job_id)


async def poll_batch(
    client: httpx.AsyncClient,
    job_id: str,
    timeout_sec: float = 180.0,
) -> list[dict[str, Any]]:
    deadline = time.time() + timeout_sec
    status_urls = [
        f"{PROCESS_API}/api/v1/batches/{job_id}",
        f"{PROCESS_API}/api/status/{job_id}",
    ]
    results_urls = [
        f"{PROCESS_API}/api/v1/batches/{job_id}/results",
        f"{PROCESS_API}/api/status/{job_id}/results",
    ]
    while time.time() < deadline:
        status = None
        for url in status_urls:
            try:
                r = await client.get(url, timeout=20.0)
                if r.status_code == 200:
                    status = r.json()
                    break
            except Exception:
                continue
        if not status:
            await asyncio.sleep(2)
            continue
        st = (status.get("status") or "").lower()
        if st in ("done", "complete", "completed", "error"):
            break
        await asyncio.sleep(2.5)

    for url in results_urls:
        try:
            r = await client.get(url, timeout=30.0)
            if r.status_code != 200:
                continue
            data = r.json()
            wallets = data.get("wallets") or data.get("results") or []
            out = []
            for item in wallets:
                if isinstance(item, dict):
                    if "data" in item and isinstance(item["data"], dict):
                        w = {**item["data"], "address": item.get("address") or item["data"].get("address")}
                        w["status"] = item.get("status") or "scraped"
                    else:
                        w = item
                        w.setdefault("status", "scraped")
                    out.append(w)
            return out
        except Exception:
            continue
    return []


async def analyze_wallets(
    addresses: list[str],
    *,
    force_scrape: bool = False,
) -> dict[str, Any]:
    addresses = [a for a in addresses if ADDR_RE.fullmatch(a)][:MAX_WALLETS_PER_REQUEST]
    if not addresses:
        return {"ok": False, "error": "no valid 0x wallets", "wallets": [], "ranked": []}

    async with httpx.AsyncClient(headers={"User-Agent": "frong.ai/1.0"}) as client:
        found: list[dict[str, Any]] = []
        missing: list[str] = []
        if not force_scrape:
            for addr in addresses:
                w = await lookup_wallet(client, addr)
                if w and w.get("status") != "error" and w.get("total_profit") is not None:
                    found.append(w)
                elif w and w.get("status") == "error":
                    missing.append(addr)
                else:
                    missing.append(addr)
        else:
            missing = list(addresses)

        scraped: list[dict[str, Any]] = []
        job_id = None
        if missing:
            try:
                job_id = await submit_batch(client, missing)
                scraped = await poll_batch(client, job_id)
            except Exception as e:
                return {
                    "ok": False,
                    "error": f"scrape failed: {e}",
                    "wallets": [compact_wallet(w) for w in found],
                    "ranked": rank_wallets(found),
                    "missing": missing,
                }

        by_addr = {str(w.get("address", "")).lower(): w for w in found}
        for w in scraped:
            by_addr[str(w.get("address", "")).lower()] = w
        merged = list(by_addr.values())
        ranked = rank_wallets(merged, top_n=min(15, len(merged)))
        # Attach verdicts onto compact wallet rows for the model.
        by = {r["address"].lower(): r for r in ranked if r.get("address")}
        wallets_out = []
        for w in merged:
            c = compact_wallet(w)
            extra = by.get(c["address"].lower())
            if extra:
                c["score"] = extra.get("score")
                c["track"] = extra.get("track")
                c["verdict"] = extra.get("verdict")
                c["rank"] = extra.get("rank")
            wallets_out.append(c)
        return {
            "ok": True,
            "tool": "analyze_wallets",
            "count": len(merged),
            "job_id": job_id,
            "wallets": wallets_out,
            "ranked": ranked,
            "track": [r for r in ranked if r.get("track")],
            "skip": [r for r in ranked if r.get("verdict") == "NO"],
        }
