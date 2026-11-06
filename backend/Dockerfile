# LectureLens backend — lightweight image (mock providers by default).
# Heavy ML deps are intentionally excluded; see requirements.txt extras and
# docs/model-selection.md for real-provider installation.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

ENV PYTHONUNBUFFERED=1 \
    STORAGE_ROOT=/data/storage

RUN mkdir -p /data/storage
VOLUME ["/data/storage"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

COPY docker/entrypoint.sh docker/worker-entrypoint.sh /docker/
RUN chmod +x /docker/entrypoint.sh /docker/worker-entrypoint.sh
ENTRYPOINT ["/docker/entrypoint.sh"]
