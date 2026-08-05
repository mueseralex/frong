# Deploy frong.ai

## Live right now

| Surface | URL |
|---------|-----|
| Railway (UI + API) | https://frong-production.up.railway.app |
| Custom domain | `frong.ai` — add DNS in [DNS.md](DNS.md) |
| Mac runtime | local API `:8787` + Ollama; LaunchAgent `com.frong.runtime` |

Chat needs the Mac Ollama bridge (`OLLAMA_HOST` on Railway). Keep the Mac awake with:

```bash
bash /Users/alex/Downloads/frong/scripts/frong-mac-runtime.sh
# or
launchctl load ~/Library/LaunchAgents/com.frong.runtime.plist
```

## Architecture

1. **Railway** hosts the website + API + SQLite volume.
2. **Your Mac** runs Ollama (`frong` model) and a Cloudflare quick tunnel so Railway can call it.
3. **Cloudflare DNS** points `frong.ai` → Railway (see DNS.md).
4. **X OAuth / bot tokens** — see [CREDENTIALS.md](CREDENTIALS.md).

## After X OAuth is set

```
FRONG_DEV_AUTH=0
FRONG_SITE_URL=https://frong.ai
FRONG_FRONTEND_URL=https://frong.ai
X_CLIENT_ID=...
X_CLIENT_SECRET=...
X_CALLBACK_URL=https://frong.ai/auth/x/callback
```

## Bot

```bash
cd /Users/alex/Downloads/frong/server && source .venv/bin/activate
python -m bot.worker
```

## Dune (`frong_ai`)

`DUNE_API_KEY` is already on Railway. Sync:

```bash
cd /Users/alex/Downloads/frong/server && source .venv/bin/activate
python sync_dune.py
```
