#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
AGNO_DEMO_DIR="$ROOT_DIR/agno-demos/05-session-memory"
AGENT_UI_DIR="$ROOT_DIR/tools/agent-ui"
AGENTOS_HOST="${AGENTOS_HOST:-127.0.0.1}"
AGENTOS_PORT="${AGENTOS_PORT:-7778}"

cleanup() {
  if [ -n "${AGENTOS_PID:-}" ]; then
    kill "$AGENTOS_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

# The local proxy variables on this machine can route DeepSeek requests to a
# closed local port. Keep this script self-contained by clearing them only for
# the processes it starts.
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

cd "$AGNO_DEMO_DIR"
python session_memory_agentos.py --host "$AGENTOS_HOST" --port "$AGENTOS_PORT" &
AGENTOS_PID="$!"

echo "AgentOS 05 starting at http://$AGENTOS_HOST:$AGENTOS_PORT"
echo "Agent UI will open at the Next.js dev server URL."
echo "In Agent UI, set endpoint to: http://$AGENTOS_HOST:$AGENTOS_PORT"

cd "$AGENT_UI_DIR"
if [ ! -d node_modules ]; then
  npm install
fi

npm run dev
