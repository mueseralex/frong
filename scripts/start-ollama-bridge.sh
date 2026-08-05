#!/usr/bin/env bash
# Keep local Ollama reachable from Railway via Cloudflare quick tunnel.
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/bin:/bin"
mkdir -p "$HOME/.frong"
PROXY_PY="/Users/alex/frong/scripts/ollama_proxy.py"
PROXY_BIN="$HOME/.frong/proxy-venv/bin/python"
CLOUDFLARED="$HOME/.local/bin/cloudflared"
URL_FILE="$HOME/.frong/ollama-tunnel.url"
RAILWAY_BIN="$HOME/.railway/bin/railway"
FRONG_DIR="/Users/alex/frong"

# Ensure proxy
if ! curl -fsS http://127.0.0.1:11435/api/tags >/dev/null 2>&1; then
  pkill -f ollama_proxy.py 2>/dev/null || true
  nohup "$PROXY_BIN" "$PROXY_PY" >"$HOME/.frong/ollama-proxy.log" 2>&1 &
  sleep 1
fi

# Ensure ollama up
if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "waiting for ollama on :11434" >&2
  sleep 5
fi

pkill -f 'cloudflared tunnel --url http://127.0.0.1:11435' 2>/dev/null || true
sleep 1
rm -f "$HOME/.frong/ollama-tunnel.log"
"$CLOUDFLARED" tunnel --url http://127.0.0.1:11435 --protocol http2 --no-autoupdate \
  >"$HOME/.frong/ollama-tunnel.log" 2>&1 &
CFPID=$!

URL=""
for _ in $(seq 1 30); do
  URL=$(rg -o 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$HOME/.frong/ollama-tunnel.log" 2>/dev/null | tail -1 || true)
  if [ -n "$URL" ]; then break; fi
  sleep 1
done
echo "$URL" >"$URL_FILE"
echo "tunnel $URL"

# Push OLLAMA_HOST to Railway when linked
if [ -n "$URL" ] && [ -x "$RAILWAY_BIN" ] && [ -f "$FRONG_DIR/.railway/config.json" ] || [ -f "$FRONG_DIR/railway.toml" ]; then
  (
    cd "$FRONG_DIR"
    "$RAILWAY_BIN" variables set "OLLAMA_HOST=$URL" --skip-deploys >/dev/null 2>&1 || true
  )
fi

wait "$CFPID"
