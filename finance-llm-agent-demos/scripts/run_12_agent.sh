#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/../12-ai_financial_data_analysis_agent" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$APP_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="python3.11"
  else
    PYTHON_BIN="python3"
  fi
fi

cd "$APP_DIR"
"$PYTHON_BIN" -m streamlit run app.py
