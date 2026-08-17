#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../09-ai-mcp-app-builder"

if ! command -v pnpm >/dev/null 2>&1; then
  echo "错误：找不到 pnpm，请先安装 pnpm 10。" >&2
  exit 1
fi
if [[ ! -d "$DEMO_DIR/node_modules" ]]; then
  echo "错误：依赖未安装。请先在 $DEMO_DIR 运行 pnpm install。" >&2
  exit 1
fi

export OPENAI_BASE_URL="${MCP_LLM_BASE_URL:-https://api.deepseek.com/v1}"
export OPENAI_MODEL="${MCP_LLM_MODEL:-deepseek-v4-pro}"
export WORKSPACE_PROVIDER="${WORKSPACE_PROVIDER:-podman}"

if [[ "$WORKSPACE_PROVIDER" == "podman" ]]; then
  if ! command -v podman >/dev/null 2>&1; then
    echo "提示：未找到 podman；页面仍可启动，但创建本地工作区前必须安装 Podman。" >&2
  elif ! podman image exists "${PODMAN_SANDBOX_IMAGE:-mcp-app-builder-sandbox:local}"; then
    echo "提示：本地沙箱镜像尚未构建。运行 09-ai-mcp-app-builder/scripts/build-podman-sandbox.sh。" >&2
  fi
fi

cd "$DEMO_DIR"
exec pnpm dev "$@"
