"""Frong server configuration from environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
# Never override real process env (Railway/prod). Local .env is fill-in only.
load_dotenv(ROOT / ".env", override=False)
load_dotenv(PROJECT / ".env", override=False)

DATA_DIR = Path(os.environ.get("FRONG_DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PATH = Path(os.environ.get("FRONG_SQLITE", DATA_DIR / "frong.sqlite3"))

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
FRONG_MODEL = os.environ.get("FRONG_MODEL", "frong")

# Upstream Robinhood-chain wallet intel + on-demand scrape (env only; no product brand).
WALLET_API = os.environ.get("FRONG_WALLET_API", "https://api.frong.ai").rstrip("/")
PROCESS_API = os.environ.get("FRONG_PROCESS_API", "https://process.frong.ai").rstrip("/")
# Authenticated scrape worker on the process VM (shared GMGN JWT). Prefer this for CA traders.
SCRAPE_API = os.environ.get("FRONG_SCRAPE_API", PROCESS_API).rstrip("/")
SCRAPE_SECRET = os.environ.get("FRONG_SCRAPE_SECRET", "").strip()

GMGN_BEARER = os.environ.get("FRONG_GMGN_BEARER", "").strip()
GMGN_CHAIN = os.environ.get("FRONG_CHAIN", "robinhood")
X_CLIENT_ID = os.environ.get("X_CLIENT_ID", "").strip()
X_CLIENT_SECRET = os.environ.get("X_CLIENT_SECRET", "").strip()
X_CALLBACK_URL = os.environ.get(
    "X_CALLBACK_URL", "http://localhost:8787/auth/x/callback"
).strip()
# Keep login scopes minimal; offline.access / tweet.write can break consent on some apps.
X_SCOPES = os.environ.get("X_SCOPES", "tweet.read users.read")

X_BOT_BEARER = os.environ.get("X_BOT_BEARER", "").strip()
X_BOT_ACCESS_TOKEN = os.environ.get("X_BOT_ACCESS_TOKEN", "").strip()
X_BOT_REFRESH_TOKEN = os.environ.get("X_BOT_REFRESH_TOKEN", "").strip()
X_BOT_ACCESS_SECRET = os.environ.get("X_BOT_ACCESS_SECRET", "").strip()
X_BOT_API_KEY = os.environ.get("X_BOT_API_KEY", "").strip()
X_BOT_API_SECRET = os.environ.get("X_BOT_API_SECRET", "").strip()
X_BOT_USER_ID = os.environ.get("X_BOT_USER_ID", "").strip()

SESSION_SECRET = os.environ.get("FRONG_SESSION_SECRET", "dev-change-me-frong")
SESSION_COOKIE = "frong_session"
SESSION_DAYS = int(os.environ.get("FRONG_SESSION_DAYS", "30"))

# Production default: X login only. Opt in with FRONG_DEV_AUTH=1 for local bypass.
DEV_AUTH = os.environ.get("FRONG_DEV_AUTH", "0") == "1"

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

SYSTEM_PROMPT = """You are Frong on frong.ai — a funny, sharp crypto frog with a real desk-analyst brain. You live on Robinhood-chain pools, launchpads, and wallet flow. Personality first: dry humor, lightly unhinged, curious, opinionated. Fun to talk to. Not a generic chatbot.

What you can do (important):
- You have live tools + a wallet database for Robinhood-chain. When a user pastes a 0x wallet or CA, the server runs analysis and gives you TOOL_RESULT JSON.
- From that data you SHOULD report real stats: winrate_30d, total_profit, realized_profit_30d, buy_30d / sell_30d (txn counts), token_num, fast_trades_percentage, early entries (sub_75k), pnl_gt_5x_num, and track/rank scores.
- Reporting historical wallet stats is your job. That is NOT financial advice. Do NOT refuse winrate or PnL. Do NOT say you "cannot provide win rates or profitability."
- Never invent numbers. If TOOL_RESULT is missing, say you need a 0x wallet or CA to pull them — then wait.
- No price predictions ("this will moon"). Descriptive stats and skeptical takes are fine.

Conversation:
- Banter and answer questions. Do not nag for an address every message.
- Only ask for a 0x when they want analysis and have not pasted one yet.
- Keep replies tight (1-5 sentences unless TOOL_RESULT needs a short report).
- Normal English with spaces. No emoji. Skip dead openers ("How can I help you today").
- You may use their @handle sparingly.

When TOOL_RESULT JSON is present:
- Use ONLY those numbers. Cite the real winrate_30d (it is a percent, e.g. 1.0 means 1 percent — that is terrible).
- Every wallet row may include verdict: YES / NO / MAYBE. Obey it. Lead with that word.
- YES = worth tracking. NO = do not track — say why bluntly (low winrate, red PnL, etc.). MAYBE = only if they insist.
- Never call a winrate under ~30% "good". Never soft-justify a NO wallet into a yes.
- Example tone: "NO. 0x4337…8084 is a 1% winrate grind — not a track. PnL X, buys/sells Y/Z."
- If the pull failed or data is thin, say so plainly."""
