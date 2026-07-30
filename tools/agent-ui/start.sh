#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-3000}"
HOST="${HOST:-127.0.0.1}"

if ! [[ "$PORT" =~ ^[0-9]+$ ]] || ((PORT < 1 || PORT > 65535)); then
  echo "错误：PORT 必须是 1 到 65535 之间的整数（当前值：$PORT）。" >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "错误：未找到 Node.js，请先安装 Node.js 18.18 或更高版本。" >&2
  exit 1
fi

if [[ ! -x node_modules/.bin/next ]]; then
  if command -v pnpm >/dev/null 2>&1; then
    echo "首次启动，正在使用 pnpm 安装依赖..."
    pnpm install --frozen-lockfile
  elif command -v npm >/dev/null 2>&1; then
    echo "首次启动，正在使用 npm 安装依赖..."
    npm ci
  else
    echo "错误：未找到 pnpm 或 npm，无法安装项目依赖。" >&2
    exit 1
  fi
fi

echo "正在启动 Agent UI：http://${HOST}:${PORT}"
exec node_modules/.bin/next dev --hostname "$HOST" --port "$PORT"
