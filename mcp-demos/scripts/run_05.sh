#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../05-browser-mcp-agent"
PYTHON_BIN="${MCP_PYTHON:-python3}"

if [[ ! -f "$DEMO_DIR/mcp_agent.secrets.yaml" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "错误：请创建 mcp_agent.secrets.yaml，或设置 OPENAI_API_KEY。" >&2
  exit 1
fi
if ! "$PYTHON_BIN" -c "import streamlit, mcp_agent, openai" 2>/dev/null; then
  echo "错误：Python 依赖未安装。请运行：$PYTHON_BIN -m pip install -r $DEMO_DIR/requirements.txt" >&2
  exit 1
fi

cd "$DEMO_DIR"
exec "$PYTHON_BIN" -m streamlit run main.py "$@"
