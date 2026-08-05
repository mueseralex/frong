"""SQLite store: users, sessions, one chat per user, bot state, activity."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Any

from config import DATA_DIR, MAX_CHAT_MESSAGES, SQLITE_PATH


def _connect() -> sqlite3.Connection:
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SQLITE_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def db() -> sqlite3.Connection:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                x_user_id   TEXT PRIMARY KEY,
                handle      TEXT NOT NULL,
                name        TEXT,
                avatar_url  TEXT,
                created_at  REAL NOT NULL,
                last_seen   REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token       TEXT PRIMARY KEY,
                x_user_id   TEXT NOT NULL REFERENCES users(x_user_id),
                created_at  REAL NOT NULL,
                expires_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chats (
                x_user_id   TEXT PRIMARY KEY REFERENCES users(x_user_id),
                messages    TEXT NOT NULL DEFAULT '[]',
                updated_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tool_jobs (
                id          TEXT PRIMARY KEY,
                x_user_id   TEXT,
                kind        TEXT,
                payload     TEXT,
                status      TEXT,
                created_at  REAL
            );

            CREATE TABLE IF NOT EXISTS bot_state (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL,
                updated_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS activity (
                id          TEXT PRIMARY KEY,
                kind        TEXT NOT NULL,
                ca          TEXT,
                summary     TEXT,
                stats_json  TEXT,
                created_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rate_limits (
                key         TEXT PRIMARY KEY,
                window_start REAL NOT NULL,
                count       INTEGER NOT NULL
            );
            """
        )


def upsert_user(
    x_user_id: str,
    handle: str,
    name: str | None = None,
    avatar_url: str | None = None,
) -> dict[str, Any]:
    now = time.time()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO users (x_user_id, handle, name, avatar_url, created_at, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(x_user_id) DO UPDATE SET
                handle=excluded.handle,
                name=COALESCE(excluded.name, users.name),
                avatar_url=COALESCE(excluded.avatar_url, users.avatar_url),
                last_seen=excluded.last_seen
            """,
            (x_user_id, handle, name, avatar_url, now, now),
        )
    return get_user(x_user_id)  # type: ignore[return-value]


def get_user(x_user_id: str) -> dict[str, Any] | None:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE x_user_id=?", (x_user_id,)
        ).fetchone()
    return dict(row) if row else None


def create_session(x_user_id: str, ttl_days: int = 30) -> str:
    token = uuid.uuid4().hex
    now = time.time()
    with db() as conn:
        conn.execute(
            "INSERT INTO sessions (token, x_user_id, created_at, expires_at) VALUES (?,?,?,?)",
            (token, x_user_id, now, now + ttl_days * 86400),
        )
    return token


def session_user(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    now = time.time()
    with db() as conn:
        row = conn.execute(
            """
            SELECT u.* FROM sessions s
            JOIN users u ON u.x_user_id = s.x_user_id
            WHERE s.token=? AND s.expires_at > ?
            """,
            (token, now),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET last_seen=? WHERE x_user_id=?",
                (now, row["x_user_id"]),
            )
    return dict(row) if row else None


def delete_session(token: str | None) -> None:
    if not token:
        return
    with db() as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))


def get_chat(x_user_id: str) -> list[dict[str, Any]]:
    with db() as conn:
        row = conn.execute(
            "SELECT messages FROM chats WHERE x_user_id=?", (x_user_id,)
        ).fetchone()
    if not row:
        return []
    try:
        return json.loads(row["messages"] or "[]")
    except json.JSONDecodeError:
        return []


def save_chat(x_user_id: str, messages: list[dict[str, Any]]) -> None:
    trimmed = messages[-MAX_CHAT_MESSAGES:]
    now = time.time()
    payload = json.dumps(trimmed)
    with db() as conn:
        conn.execute(
            """
            INSERT INTO chats (x_user_id, messages, updated_at) VALUES (?,?,?)
            ON CONFLICT(x_user_id) DO UPDATE SET messages=excluded.messages, updated_at=excluded.updated_at
            """,
            (x_user_id, payload, now),
        )


def clear_chat(x_user_id: str) -> None:
    save_chat(x_user_id, [])


def bot_get(key: str, default: str = "") -> str:
    with db() as conn:
        row = conn.execute(
            "SELECT value FROM bot_state WHERE key=?", (key,)
        ).fetchone()
    return row["value"] if row else default


def bot_set(key: str, value: str) -> None:
    with db() as conn:
        conn.execute(
            """
            INSERT INTO bot_state (key, value, updated_at) VALUES (?,?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key, value, time.time()),
        )


def log_activity(
    kind: str,
    summary: str,
    ca: str | None = None,
    stats: dict | list | None = None,
) -> str:
    aid = uuid.uuid4().hex
    with db() as conn:
        conn.execute(
            """
            INSERT INTO activity (id, kind, ca, summary, stats_json, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (
                aid,
                kind,
                ca,
                summary,
                json.dumps(stats) if stats is not None else None,
                time.time(),
            ),
        )
    return aid


def recent_activity(limit: int = 50) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM activity ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("stats_json"):
            try:
                d["stats"] = json.loads(d["stats_json"])
            except json.JSONDecodeError:
                d["stats"] = None
        out.append(d)
    return out


def check_rate(key: str, limit: int, window_sec: float) -> bool:
    """Return True if allowed; increments counter."""
    now = time.time()
    with db() as conn:
        row = conn.execute(
            "SELECT window_start, count FROM rate_limits WHERE key=?", (key,)
        ).fetchone()
        if not row or now - row["window_start"] >= window_sec:
            conn.execute(
                """
                INSERT INTO rate_limits (key, window_start, count) VALUES (?,?,1)
                ON CONFLICT(key) DO UPDATE SET window_start=excluded.window_start, count=1
                """,
                (key, now),
            )
            return True
        if row["count"] >= limit:
            return False
        conn.execute(
            "UPDATE rate_limits SET count=count+1 WHERE key=?", (key,)
        )
        return True
