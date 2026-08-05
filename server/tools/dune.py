"""Frong activity snapshot + optional Dune CSV upload (namespace frong_ai)."""

from __future__ import annotations

import csv
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from config import DATA_DIR, DUNE_API_KEY, DUNE_NAMESPACE, DUNE_TABLE
from db import recent_activity


def activity_snapshot(limit: int = 40) -> dict[str, Any]:
    rows = recent_activity(limit=limit)
    migrations = [r for r in rows if r.get("kind") == "migration"]
    analyses = [r for r in rows if r.get("kind") in ("wallet", "ca", "analyze_ca", "analyze_wallets")]
    track_hits = 0
    for r in rows:
        stats = r.get("stats") or {}
        if isinstance(stats, dict):
            track_hits += len(stats.get("track") or [])
    return {
        "ok": True,
        "tool": "dune_snapshot",
        "namespace": DUNE_NAMESPACE,
        "table": DUNE_TABLE,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "recent_events": len(rows),
        "migrations_covered": len(migrations),
        "analyses": len(analyses),
        "trackable_hits": track_hits,
        "latest": [
            {
                "kind": r.get("kind"),
                "ca": r.get("ca"),
                "summary": r.get("summary"),
                "created_at": r.get("created_at"),
            }
            for r in rows[:8]
        ],
    }


def activity_to_csv(limit: int = 500) -> str:
    rows = recent_activity(limit=limit)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "id",
            "kind",
            "ca",
            "summary",
            "track_count",
            "created_at_iso",
        ]
    )
    for r in rows:
        stats = r.get("stats") or {}
        track_count = 0
        if isinstance(stats, dict):
            track_count = len(stats.get("track") or stats.get("ranked") or [])
        ts = r.get("created_at") or 0
        w.writerow(
            [
                r.get("id"),
                r.get("kind"),
                r.get("ca") or "",
                (r.get("summary") or "")[:240],
                track_count,
                datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else "",
            ]
        )
    return buf.getvalue()


async def upload_to_dune(csv_text: str | None = None) -> dict[str, Any]:
    if not DUNE_API_KEY:
        # Still write a local artifact for the dashboard pipeline
        text = csv_text or activity_to_csv()
        out = DATA_DIR / "frong_activity.csv"
        out.write_text(text, encoding="utf-8")
        return {
            "ok": True,
            "uploaded": False,
            "reason": "DUNE_API_KEY not set",
            "local_csv": str(out),
            "namespace": DUNE_NAMESPACE,
            "table": DUNE_TABLE,
        }

    text = csv_text or activity_to_csv()
    url = "https://api.dune.com/api/v1/uploads/csv"
    payload = {
        "data": text,
        "table_name": DUNE_TABLE,
        "description": "Frong.ai activity — migrations and analyses",
        "is_private": False,
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(
            url,
            headers={
                "X-DUNE-API-KEY": DUNE_API_KEY,
                "Content-Type": "application/json",
            },
            content=json.dumps(payload),
            timeout=120.0,
        )
        if r.status_code >= 400:
            return {
                "ok": False,
                "error": r.text[:500],
                "status": r.status_code,
                "namespace": DUNE_NAMESPACE,
            }
        return {
            "ok": True,
            "uploaded": True,
            "namespace": DUNE_NAMESPACE,
            "table": DUNE_TABLE,
            "response": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:300],
        }


def cache_snapshot_file(snap: dict[str, Any] | None = None) -> Path:
    snap = snap or activity_snapshot()
    path = DATA_DIR / "dune_snapshot.json"
    path.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    return path
