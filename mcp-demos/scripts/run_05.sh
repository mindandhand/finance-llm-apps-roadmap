#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../05-browser-mcp-agent"
PYTHON_BIN="${MCP_PYTHON:-$SCRIPT_DIR/../.venv/bin/python}"

if [[ ! -f "$DEMO_DIR/mcp_agent.secrets.yaml" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "错误：请创建 mcp_agent.secrets.yaml，或设置 OPENAI_API_KEY。" >&2
  exit 1
fi
if [[ ! -x "$PYTHON_BIN" ]] || ! "$PYTHON_BIN" -c "import streamlit, mcp_agent, openai" 2>/dev/null; then
  echo "错误：05 的 Python 环境未准备好。请运行：$SCRIPT_DIR/setup_python.sh 05" >&2
  exit 1
fi

cd "$DEMO_DIR"
exec "$PYTHON_BIN" -m streamlit run main.py "$@"
