#!/usr/bin/env bash
# LectureLens — start API (+ optional worker) and frontend.
# Usage:
#   ./start.sh              # API + frontend, jobs run inline (default, simplest)
#   ./start.sh --worker     # also start RQ worker and set INLINE_JOBS=false
#   ./start.sh --no-frontend
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
RUN_DIR="$ROOT/.run"
mkdir -p "$RUN_DIR"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

USE_WORKER=0
USE_FRONTEND=1
for arg in "$@"; do
  case "$arg" in
    --worker)      USE_WORKER=1 ;;
    --no-frontend) USE_FRONTEND=0 ;;
    -h|--help)     grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown flag: $arg" ;;
  esac
done

[[ -d backend/.venv ]] || die "backend/.venv missing — run ./setup.sh first"
[[ -d frontend/node_modules ]] || die "frontend/node_modules missing — run ./setup.sh first"

# Already running?
is_running() { [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null; }

if is_running "$RUN_DIR/api.pid"; then
  ok "API already running (pid $(cat "$RUN_DIR/api.pid")) on :8000"
else
  log "Starting API on http://127.0.0.1:8000"
  cd "$ROOT/backend"
  if [[ "$USE_WORKER" -eq 1 ]]; then
    export INLINE_JOBS=false
  else
    export INLINE_JOBS=true
  fi
  # shellcheck disable=SC2086
  setsid .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    > "$RUN_DIR/api.log" 2>&1 < /dev/null &
  echo $! > "$RUN_DIR/api.pid"
  cd "$ROOT"
  for i in $(seq 1 30); do
    if curl -fsS -m 1 http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1; then
      ok "API healthy (INLINE_JOBS=$INLINE_JOBS)"
      break
    fi
    [[ $i -eq 30 ]] && die "API failed to start — see $RUN_DIR/api.log"
    sleep 0.5
  done
fi

if [[ "$USE_WORKER" -eq 1 ]]; then
  if is_running "$RUN_DIR/worker.pid"; then
    ok "Worker already running (pid $(cat "$RUN_DIR/worker.pid"))"
  else
    log "Starting RQ worker (queue: lecturelens)"
    cd "$ROOT/backend"
    REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
    setsid .venv/bin/rq worker --url "$REDIS_URL" lecturelens \
      > "$RUN_DIR/worker.log" 2>&1 < /dev/null &
    echo $! > "$RUN_DIR/worker.pid"
    cd "$ROOT"
    sleep 1
    is_running "$RUN_DIR/worker.pid" && ok "Worker started" || die "Worker failed — see $RUN_DIR/worker.log"
  fi
fi

if [[ "$USE_FRONTEND" -eq 1 ]]; then
  if is_running "$RUN_DIR/frontend.pid"; then
    ok "Frontend already running (pid $(cat "$RUN_DIR/frontend.pid")) on :5173"
  else
    log "Starting frontend on http://127.0.0.1:5173"
    cd "$ROOT/frontend"
    setsid npm run dev > "$RUN_DIR/frontend.log" 2>&1 < /dev/null &
    echo $! > "$RUN_DIR/frontend.pid"
    cd "$ROOT"
    for i in $(seq 1 40); do
      if curl -fsS -m 1 http://127.0.0.1:5173/ >/dev/null 2>&1; then
        ok "Frontend ready"
        break
      fi
      [[ $i -eq 40 ]] && die "Frontend failed to start — see $RUN_DIR/frontend.log"
      sleep 0.5
    done
  fi
fi

echo
ok "LectureLens is up"
echo "   App  →  http://localhost:5173"
echo "   API  →  http://localhost:8000/docs"
echo "   Logs →  $RUN_DIR/{api,frontend,worker}.log"
echo "   Stop →  ./stop.sh"
