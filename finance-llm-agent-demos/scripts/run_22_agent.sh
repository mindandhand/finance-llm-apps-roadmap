#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/../22-agentic_knowledge_graph_construction" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$APP_DIR/.venv/bin/python}"
PORT="${PORT:-8501}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.11)"
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi

cd "$APP_DIR"
"$PYTHON_BIN" - <<'PY'
missing = []
for package in ("streamlit", "langgraph", "neo4j", "requests", "dotenv"):
    try:
        __import__(package)
    except ModuleNotFoundError:
        missing.append(package)
if missing:
    raise SystemExit(
        "缺少 Python 依赖：" + ", ".join(missing)
        + "\n请先运行：python3.11 -m pip install -r requirements.txt"
    )
PY

exec "$PYTHON_BIN" -m streamlit run app.py --server.port "$PORT"
