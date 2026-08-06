# GMGN token + worker layout (Frong)

## Goal

One browser-minted JWT, many request workers. Workers do **not** each open Chrome; they share the token file/DB and run HTTP in separate processes so CA lookup, chat scrapes, reply bot, and the main scraper don’t serialize on one queue.

## Token source (single mint)

Reuse the existing minter pattern from the Robinhood scraper:

- `token_minter.py` (browser) → writes JWT every ~25 min  
- Shared store: `~/.gmgn_token.json` and/or Postgres `app_tokens` (`gmgn_jwt`)

Frong reads only:

```
FRONG_GMGN_BEARER=...          # override
# or
GMGN_TOKEN_FILE=~/.gmgn_token.json
```

Mint stays on the scraper VM / Mac with Chrome+Xvfb. Frong never mints in Railway.

## Workers (separate processes, shared token)

| Worker | Job | Where |
|--------|-----|--------|
| **main scraper** | trending CAs + wallet refresh loop | existing scraper VM |
| **process/batch** | on-demand wallet batches | process.frong.ai |
| **frong-chat** | user chat tool calls (wallet/CA) | Railway API (rate-limited) |
| **frong-ca / frong-scrape** | CA traders + on-demand wallet scrape | process VM `/api/frong/*` |
| **frong-reply** | X mention replies | `python -m bot.worker` (later) |
| **frong-migrate** | migration auto-tweets | same bot process, later |

Railway calls `https://process.frong.ai/api/frong/*` with `FRONG_SCRAPE_SECRET`. The process worker syncs `app_tokens.gmgn_jwt` from the main minter into `~/.gmgn_token.json` — Frong never mints Chrome tokens itself.

## Rate budgets (per worker)

Suggested defaults (env):

- `FRONG_CHAT_SCRAPE_RATE` — chat tool scrapes / user / hour  
- `FRONG_BOT_SCRAPE_RATE` — mention+migration pulls / hour  
- `FRONG_CA_CONCURRENCY` — parallel CA trader fetches (low, e.g. 1–2)

## Failure mode

401 / “token” in GMGN message → Frong marks token stale, returns “token refreshing” to the user/bot, and the **minter** (not Frong) refreshes the shared file.
