"""Same-origin proxies so browsers never need api./process. subdomain DNS."""

from __future__ import annotations

from typing import Iterable
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, Request, Response

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    # httpx already decompresses; never forward these or clients double-decode.
    "content-encoding",
    "content-length",
}


async def _doh_a(hostname: str) -> str | None:
    """Resolve A record via Cloudflare DoH when local DNS is stale."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(
                "https://cloudflare-dns.com/dns-query",
                params={"name": hostname, "type": "A"},
                headers={"accept": "application/dns-json"},
            )
            res.raise_for_status()
            for ans in res.json().get("Answer") or []:
                if ans.get("type") == 1 and ans.get("data"):
                    return str(ans["data"]).strip()
    except Exception:  # noqa: BLE001
        return None
    return None


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
        if k.lower() not in HOP_BY_HOP and k.lower() != "cookie"
    }
    headers["accept"] = request.headers.get("accept", "*/*")
    body = await request.body()

    upstream: httpx.Response | None = None
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            upstream = await client.request(method, url, headers=headers, content=body)
    except httpx.RequestError:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        ip = await _doh_a(host) if host else None
        if not ip:
            raise HTTPException(502, "upstream unreachable (dns)") from None
        ip_url = url.replace(f"{parsed.scheme}://{host}", f"{parsed.scheme}://{ip}", 1)
        headers = {**headers, "host": host}
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                verify=False,
            ) as client:
                upstream = await client.request(
                    method,
                    ip_url,
                    headers=headers,
                    content=body,
                    extensions={"sni_hostname": host},
                )
        except httpx.RequestError as exc:
            raise HTTPException(502, f"upstream unreachable: {exc}") from exc

    assert upstream is not None
    out_headers = {
        k: v
        for k, v in upstream.headers.items()
        if k.lower() not in HOP_BY_HOP
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=out_headers,
        media_type=upstream.headers.get("content-type"),
    )
