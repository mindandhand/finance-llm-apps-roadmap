#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../10-agui-fastapi"

cd "$DEMO_DIR"

# 10 是给 11/12 使用的后端服务；无参数时直接启动默认 AG-UI server。
# 需要查看帮助或覆盖端口时，仍可把参数原样传给 Python 入口。
if [[ "$#" -eq 0 ]]; then
  python agui_fastapi.py --serve --port 7777
else
  python agui_fastapi.py "$@"
fi
