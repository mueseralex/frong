# frong.ai

Chat with Frong — Robinhood-chain wallet / CA intel with a frog desk personality.

Standalone product. Site is the LLM surface; analysis is live via tools (not a public DB browser).

## Stack

- Vite frontend (`src/`) — pink/white chat over frog video
- FastAPI backend (`server/`) — X auth, one chat per account, Ollama, analysis tools
- Ollama model `frong` (`Modelfile`)
- X bot worker (`server/bot/worker.py`) — mentions, migration tweets, Dune KPIs
- Dune sync (`server/sync_dune.py`) — namespace **frong_ai**, table **frong_activity**

## Local

```bash
# model
ollama create frong -f Modelfile

# API
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app:app --host 127.0.0.1 --port 8787 --reload

# UI (other terminal)
cd ..
npm install
npm run dev
```

Open http://localhost:5175 — use **Dev login** until X OAuth is configured.

## Production notes

- Domain: **frong.ai** (Cloudflare)
- Point Ollama at your box via Tailscale / private tunnel (`OLLAMA_HOST`)
- Set `X_CLIENT_ID` / `X_CLIENT_SECRET`, `FRONG_DEV_AUTH=0`
- Callback: `https://frong.ai/auth/x/callback`
- Bot: `python -m bot.worker` from `server/` with X bot tokens
- Dune: `DUNE_API_KEY=... python sync_dune.py` (account/namespace `frong_ai`)

## Chat features

- Talk to Frong (persona, no emoji)
- Paste wallet(s) → stats + verbal report + track card
- Paste CA (`analyze ca 0x…`) → live top traders → rank → worth tracking
- `/clear` resets your one saved thread
- `/dune` loads activity snapshot

## Repo

This project lives on its own at the repo root (not inside other products).
