"""
Frong batch processor — backend for process.frong.ai.

Visitors submit up to MAX_WALLETS addresses (no account needed) and get back a
CSV of full GMGN stats. Jobs go into a SQLite-backed FIFO queue; ONE worker
thread drains it so GMGN only ever sees a steady, bounded request rate no
matter how many people submit at once. The job id (uuid4) in the URL is the
only "auth" a visitor needs to poll status / download results.

Runs on its own VM. Job state stays in local SQLite, while successful wallet
results are also upserted into the main public PostgreSQL wallet database.
The GMGN JWT lives in a local JSON file (GMGN_TOKEN_FILE) and is minted on
demand by token_minter.py --once under xvfb-run whenever needed.

Run (systemd unit `hood-process`):
    uvicorn worker_api:app --host 127.0.0.1 --port 8600
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import psycopg2

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(os.path.dirname(HERE), "server")


def _load_env() -> None:
    env_file = os.path.join(HERE, ".env")
    if not os.path.exists(env_file):
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.strip().split("=", 1)
                os.environ.setdefault(key, value)


_load_env()

# Keep the shared scraper DB-disabled so it cannot mutate scraper status or use
# the database token store. Batch results use PROCESS_DATABASE_URL explicitly.
os.environ.pop("DATABASE_URL", None)
os.environ.setdefault("GMGN_TOKEN_FILE", os.path.expanduser("~/.gmgn_token.json"))
TOKEN_FILE = os.environ["GMGN_TOKEN_FILE"]

sys.path.insert(0, SERVER_DIR)
import server as scraper  # noqa: E402  (reuses scrape_wallet + token handling)
import db as wallet_db  # noqa: E402  (row mapping + safe wallet upsert SQL)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DB_PATH = os.environ.get("PROCESS_DB", os.path.join(HERE, "jobs.sqlite3"))
MAX_WALLETS = int(os.environ.get("PROCESS_MAX_WALLETS", "100"))
CONCURRENCY = int(os.environ.get("PROCESS_CONCURRENCY", "3"))
COOLDOWN_SEC = int(os.environ.get("PROCESS_IP_COOLDOWN", "60"))
MAX_QUEUED_JOBS = int(os.environ.get("PROCESS_MAX_QUEUE", "20"))
JOB_TTL_HOURS = int(os.environ.get("PROCESS_JOB_TTL_HOURS", "48"))
MINT_TIMEOUT_SEC = int(os.environ.get("PROCESS_MINT_TIMEOUT", "420"))
PROCESS_DATABASE_URL = os.environ.get("PROCESS_DATABASE_URL", "").strip()
NOTE_MAX_LENGTH = int(os.environ.get("PROCESS_NOTE_MAX_LENGTH", "80"))
RECENT_LIMIT = min(20, int(os.environ.get("PROCESS_RECENT_LIMIT", "10")))
# Mint a fresh token when the current one has less life than this. Sized so a
# full batch comfortably finishes before expiry.
TOKEN_MIN_TTL_SEC = int(os.environ.get("PROCESS_TOKEN_MIN_TTL", "420"))

ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

CSV_COLUMNS = [
    "address", "status", "total_profit", "realized_profit_30d",
    "unrealized_profit", "winrate_30d", "all_pnl", "buy_30d", "sell_30d",
    "balance", "token_num", "pnl_2x_5x_num", "pnl_gt_5x_num",
    "sub_75k_entries", "sub_75k_avg_entry", "sub_75k_avg_buy_amount",
    "sub_75k_avg_buy_30d", "sub_75k_avg_sell_30d", "sub_75k_avg_total_profit_pnl",
    "fdv_75k_250k_entries", "fdv_75k_250k_avg_entry", "fdv_75k_250k_avg_buy_amount",
    "fdv_75k_250k_avg_buy_30d", "fdv_75k_250k_avg_sell_30d",
    "fdv_75k_250k_avg_total_profit_pnl", "fast_trades_percentage", "date_reviewed",
]


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# SQLite job store (each call opens its own connection — thread-safe pattern)
# ---------------------------------------------------------------------------
@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        with conn:  # transaction: commit on success, rollback on error
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id          TEXT PRIMARY KEY,
                ip          TEXT,
                status      TEXT,           -- queued | processing | done | error
                total       INTEGER,
                done        INTEGER DEFAULT 0,
                addresses   TEXT,           -- JSON list
                results     TEXT,           -- JSON list of wallet dicts
                note        TEXT,           -- optional public short note
                db_saved    INTEGER DEFAULT 0,
                error       TEXT,
                created_at  REAL,
                started_at  REAL,
                finished_at REAL
            )
            """
        )
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
        }
        if "note" not in columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN note TEXT")
        if "db_saved" not in columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN db_saved INTEGER DEFAULT 0")


# ---------------------------------------------------------------------------
# Token: prefer shared DB (main minter), else local file, else on-demand mint
# ---------------------------------------------------------------------------
_mint_lock = threading.Lock()


def _token_ttl() -> float:
    try:
        with open(TOKEN_FILE, encoding="utf-8") as f:
            token = json.load(f).get("token") or ""
    except (OSError, json.JSONDecodeError):
        return -1.0
    exp = scraper._jwt_payload(token).get("exp")
    if not exp:
        return float("inf")
    return exp - time.time()


def sync_token_from_shared_db() -> bool:
    """Copy gmgn_jwt from the shared Postgres store written by the main minter."""
    if not PROCESS_DATABASE_URL:
        return False
    try:
        with psycopg2.connect(
            PROCESS_DATABASE_URL,
            sslmode=os.environ.get("DB_SSLMODE", "require"),
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT token, expires_at FROM app_tokens WHERE name=%s",
                    ("gmgn_jwt",),
                )
                row = cur.fetchone()
        if not row or not row[0]:
            return False
        token = row[0]
        exp = scraper._jwt_payload(token).get("exp")
        if not exp or exp - time.time() < 90:
            return False
        payload = {
            "token": token,
            "expires_at": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
            "source": "shared_db",
            "synced_at": datetime.now().isoformat(),
        }
        tmp = TOKEN_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp, TOKEN_FILE)
        scraper.invalidate_token()
        return _token_ttl() >= TOKEN_MIN_TTL_SEC
    except Exception as exc:  # noqa: BLE001
        log(f"Shared DB token sync failed: {exc.__class__.__name__}: {exc}")
        return False


def ensure_token() -> bool:
    """Make sure a usable token exists in TOKEN_FILE.

    Prefer the JWT minted on the main scraper VM (shared DB). Fall back to a
    local browser mint only when the shared store has nothing usable.
    """
    if _token_ttl() >= TOKEN_MIN_TTL_SEC:
        return True
    with _mint_lock:
        if _token_ttl() >= TOKEN_MIN_TTL_SEC:  # another thread already refreshed
            return True
        if sync_token_from_shared_db():
            log("Synced GMGN token from shared DB (main minter)")
            return True
        log("Token missing/expiring — minting a fresh one (on-demand browser)...")
        env = {**os.environ, "GMGN_TOKEN_FILE": TOKEN_FILE}
        try:
            proc = subprocess.run(
                ["xvfb-run", "-a", sys.executable, "token_minter.py", "--once"],
                cwd=SERVER_DIR, env=env, capture_output=True, text=True,
                timeout=MINT_TIMEOUT_SEC,
            )
            if proc.returncode != 0:
                log(f"Mint failed: {(proc.stdout or proc.stderr)[-500:]}")
        except subprocess.TimeoutExpired:
            log("Mint timed out")
        ok = _token_ttl() > 60
        if ok:
            scraper.invalidate_token()  # drop scraper's cached token, re-read file
            log("Fresh token ready")
        return ok


def _token_sync_loop() -> None:
    """Keep TOKEN_FILE fresh from the shared minter while this process runs."""
    while True:
        try:
            if _token_ttl() < TOKEN_MIN_TTL_SEC:
                if sync_token_from_shared_db():
                    log("Background sync: GMGN token refreshed from shared DB")
        except Exception as exc:  # noqa: BLE001
            log(f"token sync loop error: {exc}")
        time.sleep(120)

# ---------------------------------------------------------------------------
# Worker: drain the queue one job at a time, bounded wallet concurrency
# ---------------------------------------------------------------------------
def _save_wallets_to_public_db(results: list[dict]) -> int:
    """Upsert successful batch results in one PostgreSQL transaction."""
    if not PROCESS_DATABASE_URL:
        log("PROCESS_DATABASE_URL missing — batch results were not saved publicly")
        return 0
    rows = [
        wallet_db.wallet_row_from_scrape(result)
        for result in results
        if result and wallet_db.wallet_result_is_allowed(result)
    ]
    if not rows:
        return 0
    for attempt in range(2):
        try:
            with psycopg2.connect(
                PROCESS_DATABASE_URL,
                sslmode=os.environ.get("DB_SSLMODE", "require"),
            ) as conn:
                with conn.cursor() as cur:
                    cur.executemany(wallet_db.UPSERT_WALLET_SQL, rows)
            return len(rows)
        except psycopg2.Error as exc:
            if attempt:
                log(f"Public DB upsert failed: {exc.__class__.__name__}")
                return 0
            time.sleep(2)
    return 0


def _process_job(job_id: str, addresses: list[str]) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE jobs SET status='processing', started_at=? WHERE id=?",
            (time.time(), job_id),
        )

    if not ensure_token():
        with _conn() as conn:
            conn.execute(
                "UPDATE jobs SET status='error', error=?, finished_at=? WHERE id=?",
                ("could not reach the data source right now — try again in a few minutes",
                 time.time(), job_id),
            )
        return

    results: dict[str, dict] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {
            pool.submit(scraper.scrape_wallet, addr, False): addr
            for addr in addresses
        }
        for future in as_completed(futures):
            addr = futures[future]
            try:
                results[addr] = future.result() or {}
            except Exception as e:  # noqa: BLE001 — one bad wallet shouldn't kill the job
                log(f"scrape error for {addr[:12]}...: {e}")
                results[addr] = {}
            done += 1
            with _conn() as conn:
                conn.execute("UPDATE jobs SET done=? WHERE id=?", (done, job_id))

    ordered = [results.get(a, {}) for a in addresses]
    saved = _save_wallets_to_public_db(ordered)
    with _conn() as conn:
        conn.execute(
            "UPDATE jobs SET status='done', results=?, db_saved=?, finished_at=? WHERE id=?",
            (json.dumps(ordered), saved, time.time(), job_id),
        )
    ok = sum(1 for r in ordered if r)
    log(
        f"Job {job_id[:8]} done — {ok}/{len(addresses)} wallets had data, "
        f"{saved} upserted to public DB"
    )


def worker_loop() -> None:
    log(f"Worker started (concurrency={CONCURRENCY}, max {MAX_WALLETS}/job)")
    while True:
        try:
            with _conn() as conn:
                row = conn.execute(
                    "SELECT id, addresses FROM jobs WHERE status='queued' "
                    "ORDER BY created_at LIMIT 1"
                ).fetchone()
            if not row:
                time.sleep(1.5)
                continue
            job_id, addresses_json = row
            _process_job(job_id, json.loads(addresses_json))
        except Exception as e:  # noqa: BLE001 — the worker must never die
            log(f"worker error: {e}")
            time.sleep(5)


def cleanup_loop() -> None:
    while True:
        try:
            cutoff = time.time() - JOB_TTL_HOURS * 3600
            with _conn() as conn:
                cur = conn.execute("DELETE FROM jobs WHERE created_at < ?", (cutoff,))
                if cur.rowcount:
                    log(f"Cleaned up {cur.rowcount} expired job(s)")
        except Exception as e:  # noqa: BLE001
            log(f"cleanup error: {e}")
        time.sleep(3600)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
app = FastAPI(title="Frong batch processor")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    # Recover jobs stuck in 'processing' after a service restart.
    with _conn() as conn:
        conn.execute("UPDATE jobs SET status='queued', done=0 WHERE status='processing'")
    # Pull shared JWT before serving Frong / batch scrapes.
    sync_token_from_shared_db()
    threading.Thread(target=worker_loop, daemon=True).start()
    threading.Thread(target=cleanup_loop, daemon=True).start()
    threading.Thread(target=_token_sync_loop, daemon=True).start()


# Frong scrape sidecar (auth via FRONG_SCRAPE_SECRET) — CA traders + wallet pulls.
try:
    from frong_routes import bind_frong_routes

    app.include_router(bind_frong_routes(ensure_token=ensure_token, scraper=scraper, log=log))
except Exception as _frong_exc:  # noqa: BLE001 — process API must still boot
    print(f"[process] frong routes not loaded: {_frong_exc}", flush=True)

def _client_ip(request: Request) -> str:
    return (
        request.headers.get("cf-connecting-ip")
        or (request.client.host if request.client else "unknown")
    )


class SubmitBody(BaseModel):
    addresses: list[str]
    note: Optional[str] = None


@app.get("/health")
@app.get("/api/health")  # /api/ is the only prefix nginx proxies, so monitors use this
def health() -> dict:
    # Deliberately minimal: this is public (behind the tunnel), so it must not
    # leak queue depth or token state that could help someone probe the box.
    return {"ok": True}


@app.post("/api/submit")
@app.post("/api/v1/batches")
def submit(body: SubmitBody, request: Request) -> dict:
    # Validate + dedupe, preserving order.
    seen: set[str] = set()
    addresses: list[str] = []
    for raw in body.addresses:
        addr = raw.strip()
        if ADDR_RE.match(addr) and addr.lower() not in seen:
            seen.add(addr.lower())
            addresses.append(addr)
    if not addresses:
        raise HTTPException(400, "no valid wallet addresses found (expected 0x… format)")
    if len(addresses) > MAX_WALLETS:
        raise HTTPException(400, f"max {MAX_WALLETS} wallets per batch (got {len(addresses)})")

    note = " ".join((body.note or "").split())
    if len(note) > NOTE_MAX_LENGTH:
        raise HTTPException(400, f"note must be {NOTE_MAX_LENGTH} characters or fewer")
    if re.search(r"(?:https?://|www\.)", note, re.IGNORECASE):
        raise HTTPException(400, "notes cannot contain links")

    ip = _client_ip(request)
    now = time.time()
    with _conn() as conn:
        active = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE ip=? AND status IN ('queued','processing')",
            (ip,),
        ).fetchone()[0]
        if active:
            raise HTTPException(429, "you already have a batch in progress — wait for it to finish")
        last = conn.execute(
            "SELECT MAX(created_at) FROM jobs WHERE ip=?", (ip,)
        ).fetchone()[0]
        if last and now - last < COOLDOWN_SEC:
            raise HTTPException(429, f"please wait {int(COOLDOWN_SEC - (now - last))}s before submitting another batch")
        queued = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status IN ('queued','processing')"
        ).fetchone()[0]
        if queued >= MAX_QUEUED_JOBS:
            raise HTTPException(503, "the queue is full right now — try again in a few minutes")

        job_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO jobs (id, ip, status, total, addresses, note, created_at) "
            "VALUES (?, ?, 'queued', ?, ?, ?, ?)",
            (job_id, ip, len(addresses), json.dumps(addresses), note or None, now),
        )
    log(f"Job {job_id[:8]} queued — {len(addresses)} wallet(s) from {ip}")
    return {"job_id": job_id, "total": len(addresses)}


@app.get("/api/recent")
def recent() -> dict:
    """Public activity feed without wallet addresses, IPs, or download IDs."""
    now = time.time()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT note, status, total, done, created_at, db_saved "
            "FROM jobs WHERE status != 'error' ORDER BY created_at DESC LIMIT ?",
            (RECENT_LIMIT,),
        ).fetchall()
        active, completed_24h, wallets_24h = conn.execute(
            """
            SELECT
                SUM(CASE WHEN status IN ('queued','processing') THEN 1 ELSE 0 END),
                SUM(CASE WHEN status='done' AND finished_at >= ? THEN 1 ELSE 0 END),
                SUM(CASE WHEN status='done' AND finished_at >= ? THEN total ELSE 0 END)
            FROM jobs
            """,
            (now - 86400, now - 86400),
        ).fetchone()
    return {
        "batches": [
            {
                "note": note,
                "status": job_status,
                "total": total,
                "done": done,
                "created_at": created_at,
                "db_saved": db_saved,
            }
            for note, job_status, total, done, created_at, db_saved in rows
        ],
        "stats": {
            "active": int(active or 0),
            "completed_24h": int(completed_24h or 0),
            "wallets_24h": int(wallets_24h or 0),
        },
    }


@app.get("/api/status/{job_id}")
@app.get("/api/v1/batches/{job_id}")
def status(job_id: str) -> dict:
    with _conn() as conn:
        row = conn.execute(
            "SELECT status, total, done, error, created_at FROM jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "job not found (results expire after 48h)")
        job_status, total, done, error, created_at = row
        position = 0
        if job_status == "queued":
            position = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status IN ('queued','processing') "
                "AND created_at < ?",
                (created_at,),
            ).fetchone()[0]
    response = {
        "job_id": job_id,
        "status": job_status,
        "total": total,
        "done": done,
        "queue_position": position,
        "error": error,
    }
    if job_status == "done":
        response["results_url"] = f"/api/v1/batches/{job_id}/results"
        response["download_url"] = f"/api/v1/batches/{job_id}/results.csv"
    return response


@app.get("/api/download/{job_id}")
@app.get("/api/v1/batches/{job_id}/results.csv")
def download(job_id: str) -> Response:
    with _conn() as conn:
        row = conn.execute(
            "SELECT status, addresses, results FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "job not found (results expire after 48h)")
    job_status, addresses_json, results_json = row
    if job_status != "done":
        raise HTTPException(409, f"job is not finished yet (status: {job_status})")

    addresses = json.loads(addresses_json)
    results = json.loads(results_json or "[]")

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for addr, data in zip(addresses, results):
        row_out = {"address": addr, "status": "ok" if data else "no data"}
        for col in CSV_COLUMNS[2:]:
            val = data.get(col)
            row_out[col] = "" if val in (None, "None") else val
        writer.writerow(row_out)

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="frong_batch_{job_id[:8]}.csv"'
        },
    )


@app.get("/api/v1/batches/{job_id}/results")
def json_results(job_id: str) -> dict:
    """Return completed batch data as JSON; the unguessable job ID is access."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT status, addresses, results FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "job not found (results expire after 48h)")
    job_status, addresses_json, results_json = row
    if job_status != "done":
        raise HTTPException(409, f"job is not finished yet (status: {job_status})")
    addresses = json.loads(addresses_json)
    results = json.loads(results_json or "[]")
    wallets = []
    for address, data in zip(addresses, results):
        wallets.append({
            "address": address,
            "status": "ok" if data else "no_data",
            "data": data or None,
        })
    return {"job_id": job_id, "total": len(wallets), "wallets": wallets}
