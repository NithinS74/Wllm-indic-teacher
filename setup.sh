#!/usr/bin/env bash
# LectureLens — one-time setup (venv, deps, database, npm).
# Usage: ./setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- preflight
log "Checking prerequisites"
command -v python3 >/dev/null || die "python3 not found"
command -v node    >/dev/null || die "node not found (need Node 22+)"
command -v npm     >/dev/null || die "npm not found"
command -v ffmpeg  >/dev/null || die "ffmpeg not found — install with: sudo apt-get install -y ffmpeg"
command -v psql    >/dev/null || warn "psql not on PATH — will still try DB setup via socket"
command -v redis-cli >/dev/null || warn "redis-cli not on PATH"
ok "python3 $(python3 --version | awk '{print $2}'), node $(node --version)"

# ---------------------------------------------------------------- .env
if [[ ! -f .env ]]; then
  cp .env.example .env
  ok "Created .env from .env.example (mock providers by default)"
else
  ok ".env already exists"
fi

# ---------------------------------------------------------------- backend venv
log "Setting up backend virtualenv"
cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  ok "Created backend/.venv"
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
ok "Python dependencies installed"
cd "$ROOT"

# ---------------------------------------------------------------- services
log "Checking PostgreSQL"
if pg_isready -q -h localhost 2>/dev/null; then
  ok "PostgreSQL accepting connections"
else
  warn "PostgreSQL not ready — trying to start…"
  if command -v systemctl >/dev/null && systemctl list-unit-files postgresql.service >/dev/null 2>&1; then
    sudo systemctl start postgresql 2>/dev/null || service postgresql start 2>/dev/null || true
  fi
  sleep 2
  pg_isready -q -h localhost || die "PostgreSQL is not running. Install/start it first."
fi

log "Ensuring database role + databases"
# Use peer/local postgres user if available, else try lecturelens
run_psql() {
  if [[ "$(id -u)" -eq 0 ]] && command -v sudo >/dev/null; then
    sudo -u postgres psql -v ON_ERROR_STOP=0 "$@" 2>/dev/null || psql -U postgres "$@" 2>/dev/null || true
  else
    psql -U postgres "$@" 2>/dev/null || sudo -u postgres psql -v ON_ERROR_STOP=0 "$@" 2>/dev/null || true
  fi
}
run_psql -tc "SELECT 1 FROM pg_roles WHERE rolname='lecturelens'" | grep -q 1 \
  || run_psql -c "CREATE USER lecturelens WITH PASSWORD 'lecturelens' CREATEDB;"
run_psql -tc "SELECT 1 FROM pg_database WHERE datname='lecturelens'" | grep -q 1 \
  || run_psql -c "CREATE DATABASE lecturelens OWNER lecturelens;"
run_psql -tc "SELECT 1 FROM pg_database WHERE datname='lecturelens_test'" | grep -q 1 \
  || run_psql -c "CREATE DATABASE lecturelens_test OWNER lecturelens;"
ok "Role lecturelens + databases lecturelens / lecturelens_test ready"

# ---------------------------------------------------------------- migrations
log "Running database migrations"
cd "$ROOT/backend"
.venv/bin/alembic upgrade head
ok "Schema up to date"
cd "$ROOT"

# ---------------------------------------------------------------- redis
log "Checking Redis"
if redis-cli ping >/dev/null 2>&1; then
  ok "Redis responding"
else
  warn "Redis not ready — trying to start…"
  if command -v systemctl >/dev/null; then
    sudo systemctl start redis-server 2>/dev/null || sudo systemctl start redis 2>/dev/null || true
  fi
  redis-server --daemonize yes --port 6379 2>/dev/null || true
  sleep 1
  redis-cli ping >/dev/null 2>&1 && ok "Redis started" || warn "Redis still down (OK if INLINE_JOBS=true)"
fi

# ---------------------------------------------------------------- frontend
log "Installing frontend dependencies"
cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  npm install --silent
  ok "node_modules installed"
else
  ok "node_modules already present"
fi
cd "$ROOT"

# ---------------------------------------------------------------- playwright (optional)
if [[ ! -d "$HOME/.cache/ms-playwright" ]]; then
  warn "Playwright browser not installed (only needed for browser E2E):"
  warn "  npx playwright install chromium --with-deps"
fi

echo
ok "Setup complete. Next:  ./start.sh"
