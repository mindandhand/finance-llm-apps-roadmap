#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_DEMOS_DIR="$SCRIPT_DIR/.."
VENV_DIR="$MCP_DEMOS_DIR/.venv"
BOOTSTRAP_PYTHON="${MCP_BOOTSTRAP_PYTHON:-python3}"
DEMO_NUMBER="${1:-}"

if [[ ! "$DEMO_NUMBER" =~ ^(0[1-8]|all)$ ]]; then
  echo "用法：$0 {01|02|03|04|05|06|07|08|all}" >&2
  exit 2
fi

if ! command -v "$BOOTSTRAP_PYTHON" >/dev/null 2>&1; then
  echo "错误：找不到 Python：$BOOTSTRAP_PYTHON" >&2
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$BOOTSTRAP_PYTHON" -m venv "$VENV_DIR"
fi

requirements_for() {
  case "$1" in
    01) echo "$MCP_DEMOS_DIR/01-filesystem-mcp/requirements.txt" ;;
    02) echo "$MCP_DEMOS_DIR/02-firecrawl-mcp/requirements.txt" ;;
    03) echo "$MCP_DEMOS_DIR/03-notion-mcp-agent/requirements.txt" ;;
    04) echo "$MCP_DEMOS_DIR/04-github-mcp-agent/requirements.txt" ;;
    05) echo "$MCP_DEMOS_DIR/05-browser-mcp-agent/requirements.txt" ;;
    06) echo "$MCP_DEMOS_DIR/06-multi-mcp-agent/requirements.txt" ;;
    07) echo "$MCP_DEMOS_DIR/07-multi-mcp-agent-router/requirements.txt" ;;
    08) echo "$MCP_DEMOS_DIR/08-travel-planner-mcp-agent-team/requirements.txt" ;;
  esac
}

pip_args=(install --no-cache-dir)
if [[ "$DEMO_NUMBER" == "all" ]]; then
  for number in 01 02 03 04 05 06 07 08; do
    pip_args+=(-r "$(requirements_for "$number")")
  done
else
  pip_args+=(-r "$(requirements_for "$DEMO_NUMBER")")
fi

"$VENV_DIR/bin/python" -m pip "${pip_args[@]}"
echo "Python 环境已准备完成：$VENV_DIR"
