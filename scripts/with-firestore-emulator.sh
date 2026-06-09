#!/usr/bin/env bash
# Run a command with a throwaway Firestore emulator on localhost.
#
# Used by `make ci` in libs/core and agent so Firestore-backed code is covered for
# REAL (no mocks). Starts the emulator, exports FIRESTORE_EMULATOR_HOST, runs the
# given command, and always tears the emulator down on exit.
#
#   scripts/with-firestore-emulator.sh uv run pytest -q
#
# Fails loud (does NOT skip) if gcloud / the emulator component is unavailable — a
# silently-skipped Firestore test would drop coverage below the gate anyway, but the
# explicit error tells you what to install.
set -euo pipefail

PORT="${FIRESTORE_EMULATOR_PORT:-8089}"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "ERROR: gcloud is required to run the Firestore emulator." >&2
  echo "  Install: brew install --cask google-cloud-sdk" >&2
  echo "  Then:    gcloud components install cloud-firestore-emulator" >&2
  exit 1
fi

LOG="$(mktemp)"
gcloud emulators firestore start --host-port="localhost:${PORT}" --quiet >"$LOG" 2>&1 &
EMU_PID=$!
disown "$EMU_PID" 2>/dev/null || true  # detach from job control so teardown is quiet

cleanup() {
  pkill -P "$EMU_PID" 2>/dev/null || true
  kill "$EMU_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Wait for the listener (component install on first run can take ~60s).
for _ in $(seq 1 90); do
  if nc -z localhost "$PORT" 2>/dev/null; then break; fi
  sleep 1
done
if ! nc -z localhost "$PORT" 2>/dev/null; then
  echo "ERROR: Firestore emulator did not start on localhost:${PORT}" >&2
  cat "$LOG" >&2
  exit 1
fi

export FIRESTORE_EMULATOR_HOST="localhost:${PORT}"
echo "FIRESTORE_EMULATOR_HOST=${FIRESTORE_EMULATOR_HOST}" >&2
"$@"
