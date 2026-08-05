# Deploy frong.ai (Cloudflare)

Domain already on Cloudflare: **frong.ai**

## Suggested layout

1. **API + static** — run FastAPI on a VPS/Railway box; `npm run build` and serve `dist/` from the same app (already mounts `dist/` in `server/app.py`).
2. **Ollama** — stays on your Mac/home box. Expose only privately (Tailscale IP or Cloudflare Tunnel to `8787` for the API, **not** public `:11434`).
3. **DNS (Cloudflare)** — `frong.ai` / `www` → your origin (proxied).
4. **X OAuth** — callback `https://frong.ai/auth/x/callback`; set `FRONG_DEV_AUTH=0`, `FRONG_SITE_URL=https://frong.ai`, `FRONG_FRONTEND_URL=https://frong.ai`.
5. **Bot** — systemd/cron: `python -m bot.worker` with X bot tokens.
6. **Dune** — account namespace `frong_ai`; schedule `python sync_dune.py`.

## Env

Copy `.env.example` → production secrets. Never commit `.env`.
