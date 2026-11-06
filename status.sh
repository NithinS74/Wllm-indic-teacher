#!/usr/bin/env bash
# LectureLens — show what's running
# Usage: ./status.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/.run"

green() { printf '\033[1;32m%s\033[0m' "$1"; }
red()   { printf '\033[1;31m%s\033[0m' "$1"; }
dim()   { printf '\033[2m%s\033[0m' "$1"; }

is_running() { [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null; }

echo "LectureLens status"
echo "------------------"

if is_running "$RUN_DIR/api.pid"; then
  echo "API       $(green UP)   pid $(cat "$RUN_DIR/api.pid")  http://127.0.0.1:8000"
else
  echo "API       $(red DOWN)"
fi

if is_running "$RUN_DIR/worker.pid"; then
  echo "Worker    $(green UP)   pid $(cat "$RUN_DIR/worker.pid")"
else
  echo "Worker    $(dim "down (fine if INLINE_JOBS=true)")"
fi

if is_running "$RUN_DIR/frontend.pid"; then
  echo "Frontend  $(green UP)   pid $(cat "$RUN_DIR/frontend.pid")  http://127.0.0.1:5173"
else
  echo "Frontend  $(red DOWN)"
fi

echo
if curl -fsS -m 1 http://127.0.0.1:8000/api/v1/health 2>/dev/null; then
  echo
else
  echo "API health check failed"
fi

echo
echo "Providers:"
curl -fsS -m 1 http://127.0.0.1:8000/api/v1/settings/providers 2>/dev/null \
  | python3 -m json.tool 2>/dev/null || echo "  (API not reachable)"
