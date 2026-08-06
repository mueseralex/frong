# Frong scrape workers (VMs)

Auth header everywhere: `X-Frong-Key: <FRONG_SCRAPE_SECRET>`

## Main scraper VM (`ssh -p 2222`) — CA traders

Mounted on **api.hoodwallets.com** via `public_api` + `frong_public.py`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/frong/health` | token TTL |
| POST | `/api/frong/traders` | `{ca, limit}` → trader addresses |

Uses shared Postgres `app_tokens.gmgn_jwt` (minted by `hood-token`). Prefer this host for Railway `FRONG_SCRAPE_API` (better VPN). Heavy main-scraper load can still 429/503 temporarily.

## Process VM (`ssh -p 2223`) — wallet scrape + batch

Inside **hood-process** (`worker_api` + `frong_routes.py`) on process.hoodwallets.com.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/frong/health` | token TTL |
| POST | `/api/frong/traders` | fallback traders |
| POST | `/api/frong/wallets/scrape` | sync wallet stats |
| POST | `/api/frong/analyze/ca` | traders + scrape |

Token sync: `ensure_token()` copies shared DB JWT → `~/.gmgn_token.json` every ~2 min (no second Chrome).

Chat wallet analysis still uses the public batch API (`FRONG_PROCESS_API` / `FRONG_WALLET_API`).

## Railway

```
FRONG_SCRAPE_API=https://api.hoodwallets.com
FRONG_SCRAPE_SECRET=<same secret on both VMs>
FRONG_PROCESS_API=https://process.hoodwallets.com
FRONG_WALLET_API=https://api.hoodwallets.com
```

## Refresh code on VMs

```bash
# process
scp -P 2223 deploy/vm/frong_routes.py deploy/vm/worker_api.py hood@127.0.0.1:~/robinhood/process/
ssh -p 2223 hood@127.0.0.1 'pkill -f "uvicorn worker_api:app"'

# main public API
scp -P 2222 deploy/vm/frong_public.py hood@127.0.0.1:~/robinhood/server/
ssh -p 2222 hood@127.0.0.1 'pkill -f "uvicorn public_api:app"'
```
