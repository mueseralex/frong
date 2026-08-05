# frong.ai — API + built frontend
FROM node:22-bookworm-slim AS ui
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.js ./
COPY public ./public
COPY src ./src
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8787 \
    FRONG_DATA_DIR=/data \
    FRONG_DEV_AUTH=0

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY server ./server
COPY --from=ui /app/dist ./dist

RUN mkdir -p /data

EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

WORKDIR /app/server
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
