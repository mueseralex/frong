"""Chat orchestration: tools + memory + Ollama stream."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any

from config import CHAT_RATE_PER_MIN, SCRAPE_RATE_PER_HOUR
from db import check_rate, clear_chat, get_chat, log_activity, save_chat
from ollama_client import stream_chat, with_system
from tools.ca import analyze_ca, looks_like_ca_request
from tools.dune import activity_snapshot
from tools.wallets import analyze_wallets, extract_addresses

EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001faff"
    "\U00002600-\U000027bf"
    "\U0000fe0f"
    "\U0000200d"
    "]+",
    flags=re.UNICODE,
)


def scrub(text: str, *, trim: bool = False) -> str:
    """Remove emoji/decorative unicode. Do not strip by default — streaming
    chunks often start with a leading space that must be preserved."""
    out = EMOJI_RE.sub("", text or "")
    return out.strip() if trim else out


async def run_tools_for_message(
    text: str,
    x_user_id: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Auto-run wallet/CA/dune tools from user text. Returns (report, status_notes)."""
    notes: list[str] = []
    t = text.strip()
    low = t.lower()

    if low in ("/dune", "dune", "dashboard stats", "show dune"):
        snap = activity_snapshot()
        return snap, ["loaded frong activity snapshot"]

    ca = looks_like_ca_request(t)
    if ca:
        if not check_rate(f"scrape:{x_user_id}", SCRAPE_RATE_PER_HOUR, 3600):
            return {
                "ok": False,
                "error": "scrape rate limit — try again later",
                "tool": "analyze_ca",
            }, ["rate limited"]
        notes.append(f"pulling traders for ca {ca[:8]}…")
        result = await analyze_ca(str(ca))
        if result.get("ok"):
            log_activity(
                "analyze_ca",
                f"CA {ca[:10]}… traders={result.get('trader_count')} track={len(result.get('track') or [])}",
                ca=str(ca),
                stats=result,
            )
        return result, notes

    addrs = extract_addresses(t)
    analyze_words = any(
        w in low
        for w in ("analy", "wallet", "track", "pnl", "winrate", "look at", "check")
    )
    if addrs and (analyze_words or len(addrs) >= 1):
        # If user pasted addresses, analyze them (main feature).
        if not check_rate(f"scrape:{x_user_id}", SCRAPE_RATE_PER_HOUR, 3600):
            return {
                "ok": False,
                "error": "scrape rate limit — try again later",
                "tool": "analyze_wallets",
            }, ["rate limited"]
        notes.append(f"loading stats for {len(addrs)} wallet(s)…")
        result = await analyze_wallets(addrs)
        if result.get("ok"):
            log_activity(
                "analyze_wallets",
                f"{len(addrs)} wallets · track={len(result.get('track') or [])}",
                stats=result,
            )
        return result, notes

    return None, notes


async def chat_turn(
    x_user_id: str,
    user_text: str,
    *,
    handle: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield SSE-ish dict events: status | report | token | done | error."""
    if not check_rate(f"chat:{x_user_id}", CHAT_RATE_PER_MIN, 60):
        yield {"type": "error", "error": "chat rate limit"}
        return

    text = user_text.strip()
    if not text:
        yield {"type": "error", "error": "empty message"}
        return

    if text.lower() in ("/clear", "clear"):
        clear_chat(x_user_id)
        yield {"type": "cleared"}
        yield {"type": "done", "assistant": ""}
        return

    history = get_chat(x_user_id)
    report, notes = await run_tools_for_message(text, x_user_id)
    for n in notes:
        yield {"type": "status", "message": n}

    tool_block = None
    if report is not None:
        # Compact for the model — include wallet rows so it can cite winrate/PnL/txns.
        slim = {
            k: report[k]
            for k in (
                "ok",
                "tool",
                "error",
                "ca",
                "prefix_ca",
                "trader_count",
                "count",
                "wallets",
                "ranked",
                "track",
                "skip",
                "recent_events",
                "migrations_covered",
                "analyses",
                "trackable_hits",
                "latest",
                "namespace",
                "table",
            )
            if k in report
        }
        # Cap wallet rows so the prompt stays small.
        if isinstance(slim.get("wallets"), list) and len(slim["wallets"]) > 12:
            slim["wallets"] = slim["wallets"][:12]
        if isinstance(slim.get("ranked"), list) and len(slim["ranked"]) > 12:
            slim["ranked"] = slim["ranked"][:12]
        tool_block = json.dumps(slim, ensure_ascii=True)
        yield {"type": "report", "report": {
            k: slim[k]
            for k in ("tool", "ranked", "track", "ca", "ok", "error", "count", "prefix_ca")
            if k in slim
        }}

    # If they ask about stats/capabilities without an address, tell the model clearly
    # so it does not invent a "I can't provide winrate" refusal.
    capability_hint = None
    if report is None and not extract_addresses(text):
        low = text.lower()
        if any(
            w in low
            for w in (
                "winrate",
                "win rate",
                "pnl",
                "profit",
                "transaction",
                "txn",
                "stats",
                "analy",
                "what can you",
                "how do you",
                "database",
                "data",
            )
        ):
            capability_hint = (
                "CAPABILITY: You pull Robinhood-chain wallet stats from our DB/tools "
                "(winrate_30d, total_profit, realized_profit_30d, buy_30d, sell_30d, "
                "token_num, fast_trades_percentage, early entries, multipliers). "
                "You happily report those after a 0x wallet or CA is provided. "
                "Do not refuse winrate/PnL. Ask for the address once if they want numbers now."
            )

    messages = with_system(
        history,
        text,
        tool_block,
        handle=handle,
        capability_hint=capability_hint,
    )
    parts: list[str] = []
    try:
        async for piece in stream_chat(messages):
            parts.append(piece)
            yield {"type": "token", "text": scrub(piece)}
    except Exception as e:
        yield {"type": "error", "error": str(e)}
        return

    assistant = scrub("".join(parts), trim=True)
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": assistant, "report": report})
    save_chat(x_user_id, history)
    yield {"type": "done", "assistant": assistant}
