#!/usr/bin/env bash
# Expose local Ollama to the Frong Railway backend via Cloudflare quick tunnel.
# Keep this running on the Mac that hosts the frong model.
set -euo pipefail
CLOUDFLARED="${CLOUDFLARED:-$HOME/.local/bin/cloudflared}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
LOG="${FRONG_TUNNEL_LOG:-$HOME/.frong/ollama-tunnel.log}"
mkdir -p "$(dirname "$LOG")"

if ! curl -fsS "$OLLAMA_URL/api/tags" >/dev/null; then
  echo "ollama not reachable at $OLLAMA_URL — start it first (ollama serve)" >&2
  exit 1
fi

echo "starting cloudflared tunnel -> $OLLAMA_URL" | tee -a "$LOG"
exec "$CLOUDFLARED" tunnel --url "$OLLAMA_URL" --no-autoupdate 2>&1 | tee -a "$LOG"
