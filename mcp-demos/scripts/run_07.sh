#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../07-multi-mcp-agent-router"
PYTHON_BIN="${MCP_PYTHON:-python3}"

if ! "$PYTHON_BIN" -c "import streamlit, anthropic, mcp" 2>/dev/null; then
  echo "错误：Python 依赖未安装。请运行：$PYTHON_BIN -m pip install -r $DEMO_DIR/requirements.txt" >&2
  exit 1
fi

cd "$DEMO_DIR"
exec "$PYTHON_BIN" -m streamlit run agent_forge.py "$@"
