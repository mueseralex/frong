"""Same-origin proxies so browsers never need api./process. subdomain DNS."""

from __future__ import annotations

from typing import Iterable

import httpx
from fastapi import HTTPException, Request, Response

# Never forward browser/CDN headers upstream — they make Cloudflare treat the
# Railway → api/process hop as a forged/proxied request ("prohibited IP" / 403).
FORWARD_REQUEST_HEADERS = {
    "accept",
    "content-type",
    "authorization",
    "x-frong-scrape-secret",
    "x-scrape-secret",
}


async def forward(
    request: Request,
    *,
    upstream_base: str,
    upstream_path: str,
    timeout: float = 60.0,
    allow_methods: Iterable[str] | None = None,
) -> Response:
    method = request.method.upper()
    if allow_methods and method not in {m.upper() for m in allow_methods}:
        raise HTTPException(405, "method not allowed")

    base = upstream_base.rstrip("/")
    path = upstream_path.lstrip("/")
    url = f"{base}/{path}" if path else base
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() in FORWARD_REQUEST_HEADERS
    }
    headers.setdefault("accept", "*/*")
    headers["accept-encoding"] = "identity"
    headers["user-agent"] = "frong-apex-proxy/1.0"
    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            upstream = await client.request(method, url, headers=headers, content=body)
    except httpx.RequestError as exc:
        raise HTTPException(502, f"upstream unreachable: {exc}") from exc

    hop = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-encoding",
        "content-length",
    }
    out_headers = {
        k: v for k, v in upstream.headers.items() if k.lower() not in hop
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=out_headers,
        media_type=upstream.headers.get("content-type"),
    )
