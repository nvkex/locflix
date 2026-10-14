#!/usr/bin/env bash
# Start Locflix backend + frontend (assumes deps already installed).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    kill "${FRONTEND_PID}" 2>/dev/null || true
  fi
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

cd "${ROOT}/backend"
if [[ -f .venv/Scripts/activate ]]; then
  # Windows (Git Bash)
  # shellcheck disable=SC1091
  source .venv/Scripts/activate
elif [[ -f .venv/bin/activate ]]; then
  # macOS / Linux / WSL
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  echo "Missing backend/.venv — create and install deps first." >&2
  exit 1
fi

uvicorn app.main:app --host 127.0.0.1 --port 8787 &
BACKEND_PID=$!

cd "${ROOT}/frontend"
npm run dev &
FRONTEND_PID=$!

echo "Locflix backend  → http://127.0.0.1:8787"
echo "Locflix frontend → http://localhost:5173"
echo "Press Ctrl+C to stop both."

wait
