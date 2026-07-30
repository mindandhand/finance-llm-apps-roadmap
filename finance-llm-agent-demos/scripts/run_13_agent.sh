#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/../13-knowledge_graph_rag_citations" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$APP_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="python3.11"
  else
    PYTHON_BIN="python3"
  fi
fi

cd "$APP_DIR"
"$PYTHON_BIN" - <<'PY'
missing = []
for package in ("streamlit", "neo4j", "requests", "dotenv"):
    try:
        __import__(package)
    except ModuleNotFoundError:
        missing.append(package)

if missing:
    names = ", ".join(missing)
    raise SystemExit(
        f"缺少 Python 依赖：{names}\n"
        "请先运行：pip install -r requirements.txt\n"
        "如果依赖装在其他环境里，可以用 PYTHON_BIN=/path/to/python 指定。"
    )
PY
"$PYTHON_BIN" -m streamlit run knowledge_graph_rag.py
