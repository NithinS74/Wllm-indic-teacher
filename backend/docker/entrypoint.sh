#!/bin/sh
set -e

echo "Waiting for database..."
python - <<'PY'
import os, re, sys, time
import psycopg2

url = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://lecturelens:lecturelens@db:5432/lecturelens",
)
m = re.match(
    r"postgresql(?:\+\w+)?://([^:/]+):([^@]+)@([^:/]+):(\d+)/([^?\s]+)", url
)
if not m:
    print("Unrecognized DATABASE_URL, skipping wait:", url)
    sys.exit(0)
user, pw, host, port, db = m.groups()
for i in range(60):
    try:
        psycopg2.connect(user=user, password=pw, host=host,
                         port=port, dbname=db).close()
        print("Database ready.")
        break
    except Exception as exc:
        print(f"db wait {i}: {exc}")
        time.sleep(1)
else:
    print("Database never became ready", file=sys.stderr)
    sys.exit(1)
PY

echo "Running migrations..."
alembic upgrade head

echo "Starting API..."
exec uvicorn app.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}"
