#!/usr/bin/env bash
# Preflight for `make dev` (the native full-stack local run: agent + backend + Vite).
#
# The backend runs with in-memory backends and needs nothing. The AGENT sidecar,
# however, talks to Vertex AI and so needs Application Default Credentials plus a
# GCP project. This script *checks and advises* — it is deliberately NON-FATAL
# (always exits 0) so the backend + frontend still come up for pure UI work even
# when no cloud creds are present. Only the agent (and therefore live Chat) will be
# degraded in that case, and the message below says exactly how to fix it.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADC="${HOME}/.config/gcloud/application_default_credentials.json"
AGENT_ENV="${REPO_ROOT}/agent/.env"

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m•\033[0m %s\n' "$1"; }

echo "── dev preflight ──────────────────────────────────────────────"

missing=0

if [[ -f "$ADC" ]]; then
  ok "Application Default Credentials found"
else
  missing=1
  warn "No ADC at $ADC"
  warn "    → run:  gcloud auth application-default login"
fi

# `adk web` reads the agent's Vertex config (GOOGLE_GENAI_USE_VERTEXAI + project +
# region) from agent/.env, walking up from agents/assistant/. Without it the google-genai
# SDK defaults to the Developer API and the chat fails asking for a GOOGLE_API_KEY.
if [[ -f "$AGENT_ENV" ]] && grep -qE '^[[:space:]]*GOOGLE_GENAI_USE_VERTEXAI=([Tt]rue|1)' "$AGENT_ENV"; then
  ok "agent/.env present with keyless Vertex enabled"
else
  missing=1
  if [[ -f "$AGENT_ENV" ]]; then
    warn "agent/.env exists but GOOGLE_GENAI_USE_VERTEXAI is not True"
    warn "    → set:  GOOGLE_GENAI_USE_VERTEXAI=True   (else the agent asks for a GOOGLE_API_KEY)"
  else
    warn "No agent/.env — the agent will fall back to API-key mode and the chat will fail"
    warn "    → run:  cp agent/.env.sample agent/.env"
  fi
fi

if [[ "$missing" -eq 1 ]]; then
  echo
  warn "Starting anyway: backend (:8080) + Vite (:5173) work offline."
  warn "The agent (:8081) and live Chat need the items above."
else
  ok "Environment looks ready for the full stack (agent + backend + frontend)."
fi
echo "───────────────────────────────────────────────────────────────"
exit 0
