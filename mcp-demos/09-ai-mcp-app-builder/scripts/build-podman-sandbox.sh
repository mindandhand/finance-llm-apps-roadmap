#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE_NAME="${PODMAN_SANDBOX_IMAGE:-mcp-app-builder-sandbox:local}"

if ! command -v podman >/dev/null 2>&1; then
  echo "错误：找不到 podman。macOS 请先安装并启动 Podman Machine。" >&2
  exit 1
fi

if ! podman info >/dev/null 2>&1; then
  echo "错误：Podman 服务不可用。macOS 请先运行 podman machine start。" >&2
  exit 1
fi

echo "构建本地沙箱镜像：$IMAGE_NAME"

BUILD_ARGS=(
  build
  --http-proxy=false
  --file "$PROJECT_DIR/Containerfile.sandbox"
  --tag "$IMAGE_NAME"
)

if [[ -n "${PODMAN_HTTP_PROXY:-}" ]]; then
  BUILD_ARGS+=(--build-arg "HTTP_PROXY=$PODMAN_HTTP_PROXY")
  BUILD_ARGS+=(--build-arg "HTTPS_PROXY=$PODMAN_HTTP_PROXY")
fi

exec podman "${BUILD_ARGS[@]}" "$PROJECT_DIR"
