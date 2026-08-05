#!/usr/bin/env python3
"""Local reverse proxy: Cloudflare Host header → Ollama on 127.0.0.1:11434."""

from __future__ import annotations

import asyncio
from aiohttp import ClientSession, ClientTimeout, web

UPSTREAM = "http://127.0.0.1:11434"
LISTEN = ("127.0.0.1", 11435)


async def handle(request: web.Request) -> web.StreamResponse:
    path = request.rel_url.raw_path_qs
    url = f"{UPSTREAM}{path}"
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower()
        not in {"host", "content-length", "transfer-encoding", "connection"}
    }
    headers["Host"] = "127.0.0.1:11434"
    headers["Origin"] = "http://127.0.0.1:11434"
    body = await request.read()
    timeout = ClientTimeout(total=None, sock_connect=30, sock_read=None)
    async with ClientSession(timeout=timeout) as session:
        async with session.request(
            request.method,
            url,
            headers=headers,
            data=body if body else None,
        ) as resp:
            out = web.StreamResponse(status=resp.status, reason=resp.reason)
            for k, v in resp.headers.items():
                if k.lower() in {"transfer-encoding", "content-encoding", "content-length"}:
                    continue
                out.headers[k] = v
            await out.prepare(request)
            async for chunk in resp.content.iter_any():
                await out.write(chunk)
            await out.write_eof()
            return out


def main() -> None:
    app = web.Application(client_max_size=1024 * 1024 * 64)
    app.router.add_route("*", "/{path:.*}", handle)
    web.run_app(app, host=LISTEN[0], port=LISTEN[1], print=lambda *a, **k: None)


if __name__ == "__main__":
    main()
