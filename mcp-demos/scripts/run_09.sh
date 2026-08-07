#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../09-mcp-apps-generative-ui-showcase"
MCP_SERVER_DIR="$DEMO_DIR/mcp-server"

if ! command -v npm >/dev/null 2>&1; then
  echo "错误：找不到 npm，请先安装 Node.js。" >&2
  exit 1
fi
if [[ ! -d "$DEMO_DIR/node_modules" || ! -d "$MCP_SERVER_DIR/node_modules" ]]; then
  echo "错误：依赖未安装。请分别在 $DEMO_DIR 和 $MCP_SERVER_DIR 运行 npm install。" >&2
  exit 1
fi

export MCP_SERVER_URL="${MCP_SERVER_URL:-http://localhost:3001/mcp}"

cleanup() {
  if kill -0 "$MCP_SERVER_PID" 2>/dev/null; then
    kill "$MCP_SERVER_PID"
    wait "$MCP_SERVER_PID" 2>/dev/null || true
  fi
}

cd "$MCP_SERVER_DIR"
npm run dev &
MCP_SERVER_PID=$!
trap cleanup EXIT INT TERM

cd "$DEMO_DIR"
npm run dev "$@"
