"""Streaming chat against local Ollama (frong model)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from config import FRONG_MODEL, OLLAMA_HOST, SYSTEM_PROMPT


async def stream_chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.4,
) -> AsyncIterator[str]:
    payload = {
        "model": model or FRONG_MODEL,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
            "repeat_penalty": 1.12,
        },
    }
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
        ) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise RuntimeError(
                    f"ollama {resp.status_code}: {body.decode(errors='replace')[:400]}"
                )
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if chunk.get("error"):
                    raise RuntimeError(str(chunk["error"]))
                piece = (chunk.get("message") or {}).get("content") or ""
                if piece:
                    yield piece


async def complete(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.4,
) -> str:
    parts: list[str] = []
    async for p in stream_chat(messages, model=model, temperature=temperature):
        parts.append(p)
    return "".join(parts)


def with_system(
    history: list[dict[str, Any]],
    user_text: str,
    tool_block: str | None = None,
    *,
    handle: str | None = None,
    capability_hint: str | None = None,
) -> list[dict[str, str]]:
    system = SYSTEM_PROMPT
    if handle:
        system = f"{system}\n\nThe user is signed in as @{handle.lstrip('@')}."
    if capability_hint:
        system = f"{system}\n\n{capability_hint}"
    msgs: list[dict[str, str]] = [{"role": "system", "content": system}]
    for m in history:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content:
            msgs.append({"role": role, "content": content})
    final_user = user_text
    if tool_block:
        final_user = (
            f"{user_text}\n\nTOOL_RESULT (use ONLY these numbers; cite winrate_30d, "
            f"total_profit / realized_profit_30d, buy_30d, sell_30d when present):\n"
            f"{tool_block}"
        )
    msgs.append({"role": "user", "content": final_user})
    return msgs
