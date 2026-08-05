"""Frong server configuration from environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
load_dotenv(ROOT / ".env")
load_dotenv(PROJECT / ".env")

DATA_DIR = Path(os.environ.get("FRONG_DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PATH = Path(os.environ.get("FRONG_SQLITE", DATA_DIR / "frong.sqlite3"))

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
FRONG_MODEL = os.environ.get("FRONG_MODEL", "frong")

# Upstream Robinhood-chain wallet intel + on-demand scrape (env only; no product brand).
WALLET_API = os.environ.get("FRONG_WALLET_API", "https://api.hoodwallets.com").rstrip("/")
PROCESS_API = os.environ.get("FRONG_PROCESS_API", "https://process.hoodwallets.com").rstrip("/")

GMGN_BEARER = os.environ.get("FRONG_GMGN_BEARER", "").strip()
GMGN_CHAIN = os.environ.get("FRONG_CHAIN", "robinhood")

X_CLIENT_ID = os.environ.get("X_CLIENT_ID", "").strip()
X_CLIENT_SECRET = os.environ.get("X_CLIENT_SECRET", "").strip()
X_CALLBACK_URL = os.environ.get(
    "X_CALLBACK_URL", "http://localhost:8787/auth/x/callback"
).strip()
X_SCOPES = os.environ.get("X_SCOPES", "tweet.read users.read offline.access")

X_BOT_BEARER = os.environ.get("X_BOT_BEARER", "").strip()
X_BOT_ACCESS_TOKEN = os.environ.get("X_BOT_ACCESS_TOKEN", "").strip()
X_BOT_ACCESS_SECRET = os.environ.get("X_BOT_ACCESS_SECRET", "").strip()
X_BOT_API_KEY = os.environ.get("X_BOT_API_KEY", "").strip()
X_BOT_API_SECRET = os.environ.get("X_BOT_API_SECRET", "").strip()
X_BOT_USER_ID = os.environ.get("X_BOT_USER_ID", "").strip()

SESSION_SECRET = os.environ.get("FRONG_SESSION_SECRET", "dev-change-me-frong")
SESSION_COOKIE = "frong_session"
SESSION_DAYS = int(os.environ.get("FRONG_SESSION_DAYS", "30"))

DEV_AUTH = os.environ.get("FRONG_DEV_AUTH", "1" if not X_CLIENT_ID else "0") == "1"

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "FRONG_CORS_ORIGINS",
        "http://localhost:5175,http://127.0.0.1:5175,https://frong.ai,https://www.frong.ai",
    ).split(",")
    if o.strip()
]

MAX_CHAT_MESSAGES = int(os.environ.get("FRONG_MAX_CHAT_MESSAGES", "40"))
MAX_WALLETS_PER_REQUEST = int(os.environ.get("FRONG_MAX_WALLETS", "25"))
CA_TRADER_LIMIT = int(os.environ.get("FRONG_CA_TRADER_LIMIT", "20"))
CHAT_RATE_PER_MIN = int(os.environ.get("FRONG_CHAT_RATE", "20"))
SCRAPE_RATE_PER_HOUR = int(os.environ.get("FRONG_SCRAPE_RATE", "10"))

DUNE_API_KEY = os.environ.get("DUNE_API_KEY", "").strip()
DUNE_TABLE = os.environ.get("FRONG_DUNE_TABLE", "frong_activity")
DUNE_NAMESPACE = os.environ.get("FRONG_DUNE_NAMESPACE", "frong_ai")
FRONG_SITE_URL = os.environ.get("FRONG_SITE_URL", "https://frong.ai").rstrip("/")

SYSTEM_PROMPT = """You are Frong.

You are an intelligent crypto frog on frong.ai who sits on Robinhood-chain pools, launchpads, and wallet flow. Same brain as a serious wallet-analysis desk: precise, skeptical, number-aware. Personality is dry, sharp, a little unhinged — never a corporate chatbot, never a hype mascot.

Hard rules:
- NEVER use emoji, emoticons, kaomoji, smilies, or decorative unicode. ASCII / plain text only.
- No "Hey there", "What's up", "metaverse", "crypto beach", "gm fren" filler, or generic AI small talk.
- No financial advice. No price predictions. No promises.
- When TOOL_RESULT JSON is provided, use ONLY those numbers. Never invent wallet addresses, PnL, winrates, or ranks.
- If the user has not given a wallet (0x…) or CA and analysis needs one, ask for it plainly.
- Prefer concrete takes: liquidity, launchpad mechanics, wallet behavior, risk flags. Short paragraphs.
- Humor only as a sharp aside — not the whole reply.
- Sound like a competent desk analyst who happens to be a frog.

When tools already ran, write a clear verbal report and name who is worth tracking (by short address prefix) with why, using the stats given."""
