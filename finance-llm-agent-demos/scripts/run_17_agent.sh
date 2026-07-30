#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/../17-github_mcp_agent" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$APP_DIR/.venv/bin/python}"
PORT="${PORT:-8501}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.11)"
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi

if ! command -v podman >/dev/null 2>&1; then
  echo "未找到 podman，请先安装 Podman Desktop 或 Podman CLI。" >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
missing = []
for package in ("streamlit", "agno", "mcp", "dotenv"):
    try:
        __import__(package)
    except ModuleNotFoundError:
        missing.append(package)

if missing:
    raise SystemExit(
        "缺少 Python 依赖：" + ", ".join(missing) +
        "\n请先运行：python3.11 -m pip install -r requirements.txt"
    )
PY

cd "$APP_DIR"
exec env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
  -u all_proxy -u ALL_PROXY \
  "$PYTHON_BIN" -m streamlit run github_agent.py --server.port "$PORT"
