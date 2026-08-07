#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../01-filesystem-mcp"
PYTHON_BIN="${MCP_PYTHON:-$SCRIPT_DIR/../.venv/bin/python}"

export OPENAI_BASE_URL="${MCP_LLM_BASE_URL:-https://api.deepseek.com/v1}"
export OPENAI_MODEL="${MCP_LLM_MODEL:-deepseek-v4-flash}"

if [[ -z "${DEEPSEEK_API_KEY:-${OPENAI_API_KEY:-${LLM_API_KEY:-}}}" ]]; then
  echo "错误：请先设置 DEEPSEEK_API_KEY。" >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]] || ! "$PYTHON_BIN" -c "import agno, mcp, openai, dotenv" 2>/dev/null; then
  echo "错误：01 的 Python 环境未准备好。请运行：$SCRIPT_DIR/setup_python.sh 01" >&2
  exit 1
fi

cd "$DEMO_DIR"
exec "$PYTHON_BIN" agent.py "$@"
