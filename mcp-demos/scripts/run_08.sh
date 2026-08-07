#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../08-travel-planner-mcp-agent-team"
PYTHON_BIN="${MCP_PYTHON:-$SCRIPT_DIR/../.venv/bin/python}"

export OPENAI_BASE_URL="${MCP_LLM_BASE_URL:-https://api.deepseek.com/v1}"
export OPENAI_MODEL="${MCP_LLM_MODEL:-deepseek-v4-pro}"

if [[ ! -x "$PYTHON_BIN" ]] || ! "$PYTHON_BIN" -c "import streamlit, agno, mcp, openai, icalendar" 2>/dev/null; then
  echo "错误：08 的 Python 环境未准备好。请运行：$SCRIPT_DIR/setup_python.sh 08" >&2
  exit 1
fi

cd "$DEMO_DIR"
exec "$PYTHON_BIN" -m streamlit run app.py "$@"
