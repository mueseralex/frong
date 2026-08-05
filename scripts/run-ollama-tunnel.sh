#!/bin/bash
export PATH="$HOME/.local/bin:/Users/alex/.railway/bin:/usr/bin:/bin:/usr/sbin:/sbin"
mkdir -p "$HOME/.frong"
LOG="$HOME/.frong/ollama-tunnel.log"
URL_FILE="$HOME/.frong/ollama-tunnel.url"

for i in $(seq 1 60); do
  curl -fsS http://127.0.0.1:11435/api/tags >/dev/null 2>&1 && break
  sleep 1
done

: >"$LOG"
cloudflared tunnel --url http://127.0.0.1:11435 --protocol http2 --no-autoupdate >>"$LOG" 2>&1 &
CPID=$!

URL=""
for i in $(seq 1 60); do
  URL=$(tr -cd '\11\12\15\40-\176' <"$LOG" | grep -Eo 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' | tail -1)
  if [ -n "$URL" ]; then
    break
  fi
  sleep 1
done

printf '%s\n' "$URL" >"$URL_FILE"
echo "tunnel url: $URL" >>"$HOME/.frong/tunnel.out"

if [ -n "$URL" ]; then
  (
    cd /Users/alex/frong
    railway link --project 1f3098da-6a1e-40dd-a1c8-574b0d735731 --environment b4a7e0bc-275f-41a3-85b4-8946a1259abf --service 4f787e12-c151-4ba1-98ec-e02a9791ad44 >/dev/null 2>&1 || true
    railway variables set "OLLAMA_HOST=$URL" >>"$HOME/.frong/tunnel.out" 2>&1 || true
  )
fi

wait "$CPID"
