#!/usr/bin/env bash
# LectureLens — run all tests (backend pytest + frontend typecheck/build)
# Usage: ./test.sh [--backend] [--frontend] [--e2e]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

RUN_BACKEND=1
RUN_FRONTEND=1
RUN_E2E=0
if [[ $# -gt 0 ]]; then
  RUN_BACKEND=0; RUN_FRONTEND=0
  for arg in "$@"; do
    case "$arg" in
      --backend)  RUN_BACKEND=1 ;;
      --frontend) RUN_FRONTEND=1 ;;
      --e2e)      RUN_E2E=1 ;;
      -h|--help)  grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
      *) die "Unknown flag: $arg" ;;
    esac
  done
fi

FAILED=0

if [[ "$RUN_BACKEND" -eq 1 ]]; then
  log "Backend tests (pytest)"
  cd "$ROOT/backend"
  if INLINE_JOBS=true .venv/bin/pytest tests/ -q; then
    ok "Backend: all passed"
  else
    FAILED=1
    ok "Backend: FAILED"
  fi
  cd "$ROOT"
fi

if [[ "$RUN_FRONTEND" -eq 1 ]]; then
  log "Frontend typecheck + build"
  cd "$ROOT/frontend"
  if npm run build; then
    ok "Frontend: build passed"
  else
    FAILED=1
    echo "Frontend: FAILED"
  fi
  cd "$ROOT"
fi

if [[ "$RUN_E2E" -eq 1 ]]; then
  log "Browser E2E (Playwright)"
  if [[ -f /tmp/opencode/e2e.js ]]; then
    if curl -fsS -m 1 http://127.0.0.1:5173/ >/dev/null 2>&1 \
       && curl -fsS -m 1 http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1; then
      if node /tmp/opencode/e2e.js; then
        ok "E2E: passed"
      else
        FAILED=1
        echo "E2E: FAILED"
      fi
    else
      echo "E2E: skipped — start services first with ./start.sh"
      FAILED=1
    fi
  else
    echo "E2E: /tmp/opencode/e2e.js not found — skipped"
  fi
fi

echo
if [[ "$FAILED" -eq 0 ]]; then
  ok "All requested tests passed"
else
  die "Some tests failed"
fi
