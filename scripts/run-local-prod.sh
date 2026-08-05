#!/usr/bin/env bash
# Run production-shaped Frong locally (built UI + API) on :8787
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="/tmp/node-v22.14.0-darwin-arm64/bin:$PATH"
cd "$ROOT"
npm run build
cd "$ROOT/server"
source .venv/bin/activate
export FRONG_DIST="$ROOT/dist"
export FRONG_SITE_URL="${FRONG_SITE_URL:-http://127.0.0.1:8787}"
export FRONG_FRONTEND_URL="${FRONG_FRONTEND_URL:-http://127.0.0.1:8787}"
export FRONG_DEV_AUTH="${FRONG_DEV_AUTH:-1}"
exec uvicorn app:app --host 0.0.0.0 --port 8787
