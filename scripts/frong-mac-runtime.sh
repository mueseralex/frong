#!/usr/bin/env bash
# Keep Frong API + public Cloudflare quick tunnel alive on this Mac (local Ollama).
set -euo pipefail
export PATH="$HOME/.local/bin:/tmp/node-v22.14.0-darwin-arm64/bin:/usr/bin:/bin:$HOME/.railway/bin"
ROOT="/Users/alex/frong"
mkdir -p "$HOME/.frong"

cd "$ROOT/server"
# shellcheck disable=SC1091
source .venv/bin/activate
export FRONG_DIST="$ROOT/dist"
export OLLAMA_HOST="http://127.0.0.1:11434"
export FRONG_MODEL="${FRONG_MODEL:-frong}"
export FRONG_DEV_AUTH="${FRONG_DEV_AUTH:-1}"
export FRONG_SECURE_COOKIES="${FRONG_SECURE_COOKIES:-0}"
export FRONG_SITE_URL="${FRONG_SITE_URL:-http://127.0.0.1:8787}"
export FRONG_FRONTEND_URL="${FRONG_FRONTEND_URL:-http://127.0.0.1:8787}"

if [ ! -f "$FRONG_DIST/index.html" ]; then
  (cd "$ROOT" && npm run build)
fi

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null; then
  echo "start Ollama.app first" >&2
  exit 1
fi

if ! curl -fsS http://127.0.0.1:8787/health >/dev/null 2>&1; then
  nohup uvicorn app:app --host 127.0.0.1 --port 8787 >>"$HOME/.frong/api.log" 2>&1 &
  sleep 2
fi

# App tunnel for temporary public URL (stable named tunnel preferred after CF login)
if ! pgrep -f 'cloudflared tunnel --url http://127.0.0.1:8787' >/dev/null; then
  nohup cloudflared tunnel --url http://127.0.0.1:8787 --protocol http2 --no-autoupdate \
    >"$HOME/.frong/app-tunnel.log" 2>&1 &
  sleep 8
fi

URL=$(rg -o 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$HOME/.frong/app-tunnel.log" 2>/dev/null | tail -1 || true)
echo "$URL" >"$HOME/.frong/app-tunnel.url"
echo "frong api local http://127.0.0.1:8787"
echo "frong public $URL"

# Also expose Ollama for Railway via proxy+tunnel
if ! curl -fsS http://127.0.0.1:11435/api/tags >/dev/null 2>&1; then
  nohup "$HOME/.frong/proxy-venv/bin/python" "$ROOT/scripts/ollama_proxy.py" \
    >"$HOME/.frong/ollama-proxy.log" 2>&1 &
  sleep 1
fi

OLLAMA_OK=0
if [ -f "$HOME/.frong/ollama-tunnel.url" ]; then
  OU=$(cat "$HOME/.frong/ollama-tunnel.url")
  OH=${OU#https://}; IP=$(dig +short "$OH" @1.1.1.1 | head -1)
  code=$(curl -4 -sS --max-time 8 --resolve "$OH:443:$IP" -o /dev/null -w "%{http_code}" "$OU/api/tags" || echo 0)
  [ "$code" = "200" ] && OLLAMA_OK=1
fi

if [ "$OLLAMA_OK" != "1" ]; then
  pkill -f 'cloudflared tunnel --url http://127.0.0.1:11435' 2>/dev/null || true
  sleep 1
  nohup cloudflared tunnel --url http://127.0.0.1:11435 --protocol http2 --no-autoupdate \
    >"$HOME/.frong/ollama-tunnel.log" 2>&1 &
  for _ in $(seq 1 25); do
    OU=$(rg -o 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$HOME/.frong/ollama-tunnel.log" 2>/dev/null | tail -1 || true)
    [ -n "$OU" ] && break
    sleep 1
  done
  echo "$OU" >"$HOME/.frong/ollama-tunnel.url"
  sleep 2
  if [ -n "${OU:-}" ]; then
    (cd "$ROOT" && railway variables set "OLLAMA_HOST=$OU" >/dev/null 2>&1 || true)
    echo "railway OLLAMA_HOST -> $OU"
  fi
fi

# Stay alive while children run
while true; do
  curl -fsS http://127.0.0.1:8787/health >/dev/null || exit 2
  sleep 30
done
