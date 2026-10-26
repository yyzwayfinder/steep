# ---- web UI
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- app
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STEEP_DATA_DIR=/data \
    STEEP_STATIC_DIR=/app/static \
    PUID=99 \
    PGID=100 \
    UMASK=022 \
    TZ=America/Toronto

RUN apt-get update \
 && apt-get install -y --no-install-recommends gosu curl tzdata \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/steep ./steep
COPY --from=web /web/dist ./static
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8080/healthz || exit 1

LABEL org.opencontainers.image.title="Steep" \
      org.opencontainers.image.description="Self-hosted RSS reader" \
      org.opencontainers.image.source="https://github.com/yyzwayfinder/steep"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "steep.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
