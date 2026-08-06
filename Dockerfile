# frong.ai — chat UI + wallets site + API
FROM node:22-bookworm-slim AS ui-chat
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.js ./
COPY public ./public
COPY src ./src
RUN npm run build

FROM node:22-bookworm-slim AS ui-wallets
WORKDIR /app
COPY apps/wallets/package.json apps/wallets/package-lock.json ./
RUN npm ci
COPY apps/wallets/ ./
# Same-origin /wallet-api proxy — browsers do not need api.* DNS.
ENV VITE_API_URL=
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8787 \
    FRONG_DATA_DIR=/data \
    FRONG_DEV_AUTH=0 \
    FRONG_DIST=/app/dist \
    FRONG_WALLETS_DIST=/app/dist-wallets \
    FRONG_UPLOAD_DIST=/app/dist-upload

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY server ./server
COPY --from=ui-chat /app/dist ./dist
COPY --from=ui-wallets /app/dist ./dist-wallets
COPY apps/upload ./dist-upload

RUN mkdir -p /data

EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

WORKDIR /app/server
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
