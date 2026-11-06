#!/usr/bin/env bash
# LectureLens — single entry point.
# Usage:
#   ./run.sh setup     # one-time install (venv, deps, database, npm)
#   ./run.sh start     # start API + frontend (inline jobs)
#   ./run.sh start -w  # start API + RQ worker + frontend
#   ./run.sh stop      # stop everything
#   ./run.sh status    # show what's running
#   ./run.sh test      # backend + frontend tests
#   ./run.sh logs      # tail API/frontend logs
#   ./run.sh restart   # stop + start
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-}" in
  setup)   exec "$ROOT/setup.sh" ;;
  start)   shift; exec "$ROOT/start.sh" "$@" ;;
  stop)    exec "$ROOT/stop.sh" ;;
  restart) "$ROOT/stop.sh"; shift || true; exec "$ROOT/start.sh" "$@" ;;
  status)  exec "$ROOT/status.sh" ;;
  test)    shift || true; exec "$ROOT/test.sh" "$@" ;;
  logs)
    RUN_DIR="$ROOT/.run"
    if [[ -t 1 ]]; then
      tail -n 50 -f "$RUN_DIR"/api.log "$RUN_DIR"/frontend.log 2>/dev/null \
        || tail -n 50 -f "$RUN_DIR"/api.log
    else
      for f in api frontend worker; do
        [[ -f "$RUN_DIR/$f.log" ]] && { echo "----- $f.log -----"; tail -n 50 "$RUN_DIR/$f.log"; }
      done
    fi
    ;;
  ""|-h|--help|help)
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
    ;;
  *)
    echo "Unknown command: $1" >&2
    echo "Try: setup | start | stop | restart | status | test | logs" >&2
    exit 1
    ;;
esac
