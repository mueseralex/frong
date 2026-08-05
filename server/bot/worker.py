"""
Frong X bot worker — mentions + migration auto-tweets + periodic Dune KPIs.

Build-out only; wire credentials via env. Do not require live X for local smoke.

  cd server && python -m bot.worker
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import (  # noqa: E402
    FRONG_SITE_URL,
    X_BOT_ACCESS_TOKEN,
    X_BOT_BEARER,
    X_BOT_USER_ID,
)
from db import bot_get, bot_set, init_db, log_activity  # noqa: E402
from ollama_client import complete  # noqa: E402
from tools.ca import analyze_ca, fetch_trending_cas  # noqa: E402
from tools.dune import activity_snapshot, cache_snapshot_file, upload_to_dune  # noqa: E402
from tools.wallets import analyze_wallets, extract_addresses  # noqa: E402

ADDR_RE = re.compile(r"0x[a-fA-F0-9]{40}")
MENTION_POLL_SEC = 45
MIGRATE_POLL_SEC = 120
DUNE_TWEET_SEC = 6 * 3600


def _auth_headers() -> dict[str, str]:
    token = X_BOT_ACCESS_TOKEN or X_BOT_BEARER
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


async def post_tweet(text: str, reply_to: str | None = None) -> dict:
    headers = _auth_headers()
    if not headers:
        print("[bot] skip tweet (no X_BOT_ACCESS_TOKEN / X_BOT_BEARER)", flush=True)
        return {"skipped": True, "text": text}
    payload: dict = {"text": text[:280]}
    if reply_to:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to}
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.twitter.com/2/tweets",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=30.0,
        )
        if r.status_code >= 400:
            print(f"[bot] tweet failed {r.status_code}: {r.text[:300]}", flush=True)
            return {"ok": False, "error": r.text[:300]}
        return r.json()


async def fetch_mentions(since_id: str | None) -> list[dict]:
    headers = _auth_headers()
    if not headers or not X_BOT_USER_ID:
        return []
    params = {
        "max_results": 10,
        "tweet.fields": "author_id,created_at,entities",
    }
    if since_id:
        params["since_id"] = since_id
    url = f"https://api.twitter.com/2/users/{X_BOT_USER_ID}/mentions"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, params=params, timeout=30.0)
        if r.status_code >= 400:
            print(f"[bot] mentions error {r.status_code}: {r.text[:200]}", flush=True)
            return []
        return (r.json().get("data") or [])


async def handle_mention(tweet: dict) -> None:
    tid = tweet["id"]
    seen_key = f"mention:{tid}"
    if bot_get(seen_key):
        return
    text = tweet.get("text") or ""
    addrs = extract_addresses(text)
    ca_hint = "ca" in text.lower() or "contract" in text.lower()
    report = None
    if addrs and ca_hint:
        report = await analyze_ca(addrs[0])
    elif addrs:
        report = await analyze_wallets(addrs[:5])

    tool_json = json.dumps(
        {
            k: (report or {}).get(k)
            for k in ("ok", "tool", "error", "ranked", "track", "ca", "count")
        },
        ensure_ascii=True,
    )
    prompt = [
        {
            "role": "user",
            "content": (
                f"Write a short X reply (max 240 chars, no emoji) about this mention.\n"
                f"Mention text: {text}\n"
                f"TOOL_RESULT: {tool_json}\n"
                f"End with {FRONG_SITE_URL}"
            ),
        }
    ]
    reply = await complete(prompt, temperature=0.3)
    reply = reply.replace("\n", " ").strip()[:270]
    await post_tweet(reply, reply_to=tid)
    bot_set(seen_key, "1")
    log_activity("mention_reply", reply[:200], ca=addrs[0] if addrs else None, stats=report)


async def migration_pass() -> None:
    try:
        cas = await fetch_trending_cas(limit=8)
    except Exception as e:
        print(f"[bot] trending pull failed: {e}", flush=True)
        return
    for ca in cas:
        key = f"migrated:{ca.lower()}"
        if bot_get(key):
            continue
        print(f"[bot] migration report for {ca[:12]}…", flush=True)
        report = await analyze_ca(ca)
        if not report.get("ok"):
            bot_set(key, "error")
            continue
        track = report.get("track") or report.get("ranked") or []
        top = track[:3]
        lines = []
        for t in top:
            lines.append(
                f"{t.get('prefix')} score {t.get('score')} pnl {t.get('total_profit')}"
            )
        tool_json = json.dumps(
            {"ca": ca, "track": top, "trader_count": report.get("trader_count")},
            ensure_ascii=True,
        )
        prose = await complete(
            [
                {
                    "role": "user",
                    "content": (
                        "Write one X post (max 240 chars, no emoji) about a migrating/"
                        "trending coin and which wallets look worth tracking.\n"
                        f"TOOL_RESULT: {tool_json}\nLink {FRONG_SITE_URL}"
                    ),
                }
            ],
            temperature=0.35,
        )
        prose = prose.replace("\n", " ").strip()[:270]
        await post_tweet(prose)
        bot_set(key, "1")
        log_activity(
            "migration",
            prose[:200],
            ca=ca,
            stats={"track": top, "trader_count": report.get("trader_count")},
        )
        # one per pass to stay gentle on scrape
        break


async def dune_kpi_tweet() -> None:
    last = float(bot_get("dune_tweet_at") or "0")
    if time.time() - last < DUNE_TWEET_SEC:
        return
    snap = activity_snapshot()
    cache_snapshot_file(snap)
    try:
        await upload_to_dune()
    except Exception as e:
        print(f"[bot] dune upload: {e}", flush=True)
    prose = await complete(
        [
            {
                "role": "user",
                "content": (
                    "Write one short X post (max 240 chars, no emoji) with Frong desk KPIs.\n"
                    f"SNAPSHOT: {json.dumps(snap, ensure_ascii=True)}\n"
                    f"Mention dune namespace frong_ai if natural. Link {FRONG_SITE_URL}"
                ),
            }
        ],
        temperature=0.3,
    )
    await post_tweet(prose.replace("\n", " ").strip()[:270])
    bot_set("dune_tweet_at", str(time.time()))
    log_activity("dune_kpi", prose[:200], stats=snap)


async def loop() -> None:
    init_db()
    print("[bot] frong worker started", flush=True)
    last_migrate = 0.0
    while True:
        try:
            since = bot_get("mention_since_id") or None
            mentions = await fetch_mentions(since)
            if mentions:
                # API returns newest first
                bot_set("mention_since_id", mentions[0]["id"])
                for tw in reversed(mentions):
                    await handle_mention(tw)
            if time.time() - last_migrate >= MIGRATE_POLL_SEC:
                await migration_pass()
                last_migrate = time.time()
            await dune_kpi_tweet()
        except Exception as e:
            print(f"[bot] loop error: {e}", flush=True)
        await asyncio.sleep(MENTION_POLL_SEC)


def main() -> None:
    asyncio.run(loop())


if __name__ == "__main__":
    main()
