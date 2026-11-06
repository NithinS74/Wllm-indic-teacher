#!/usr/bin/env bash
# LectureLens — stop processes started by ./start.sh
# Usage: ./stop.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT/.run"

ok()  { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
info(){ printf '\033[1;34m==>\033[0m %s\n' "$*"; }

stop_one() {
  local name="$1" pidfile="$RUN_DIR/$2"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      # kill the whole process group (setsid)
      kill -TERM -"$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
      sleep 0.5
      kill -KILL -"$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
      ok "Stopped $name (pid $pid)"
    else
      ok "$name was not running"
    fi
    rm -f "$pidfile"
  else
    ok "$name: no pidfile"
  fi
}

info "Stopping LectureLens"
stop_one "frontend" "frontend.pid"
stop_one "worker"   "worker.pid"
stop_one "API"      "api.pid"

# Fallback: anything still bound to our ports started from this tree
for port in 5173 8000; do
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" 2>/dev/null || true
  fi
done

ok "All stopped"
