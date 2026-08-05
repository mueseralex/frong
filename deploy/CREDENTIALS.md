# Credentials you still need to paste

Site is already deployed. Only these secrets are missing for full production.

## 1. X OAuth (website login) — required to drop Dev login

Create an app at https://developer.x.com for **frong.ai** / @frong_ai.

Callback URL:
```
https://frong.ai/auth/x/callback
```
(also add temporary `https://frong-production.up.railway.app/auth/x/callback` until DNS is live)

Then set on Railway service `frong`:
```
X_CLIENT_ID=...
X_CLIENT_SECRET=...
X_CALLBACK_URL=https://frong.ai/auth/x/callback
FRONG_DEV_AUTH=0
FRONG_SITE_URL=https://frong.ai
FRONG_FRONTEND_URL=https://frong.ai
```

## 2. X bot tokens (auto tweets / mentions) — build is ready, not live-tested

```
X_BOT_BEARER=...
X_BOT_ACCESS_TOKEN=...
X_BOT_USER_ID=...
```

Run on the Mac (or a worker box):
```
cd /Users/alex/Downloads/frong/server
source .venv/bin/activate
python -m bot.worker
```

## 3. Cloudflare DNS for frong.ai

See [DNS.md](DNS.md). Add the CNAME + TXT records, then flip site URLs to `https://frong.ai`.

## 4. Optional: GMGN bearer for live CA trader pulls

```
FRONG_GMGN_BEARER=...
```

Without it, CA analysis may fail when GMGN blocks anonymous calls; wallet lookup via the public wallet API still works.

## Already configured

- Railway project `frong` + volume `/data`
- `DUNE_API_KEY` (from existing Dune env) + namespace `frong_ai`
- Mac Ollama bridge (proxy :11435 + Cloudflare quick tunnel) → `OLLAMA_HOST`
- Dev login enabled until X OAuth is set (`FRONG_DEV_AUTH=1`)
