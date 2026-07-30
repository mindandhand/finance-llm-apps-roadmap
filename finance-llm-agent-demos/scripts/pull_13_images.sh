#!/usr/bin/env bash
set -euo pipefail

# 默认使用镜像代理，避免 Podman 直接访问 Docker Hub 超时。
# 远端模型通过 DeepSeek API 调用，不需要拉取本地模型镜像。
NEO4J_IMAGE="${NEO4J_IMAGE:-docker.m.daocloud.io/library/neo4j:latest}"
PODMAN_MACHINE="${PODMAN_MACHINE:-podman-machine-default}"

if ! command -v podman >/dev/null 2>&1; then
  echo "未找到 podman。请先安装 Podman Desktop 或 Podman CLI。"
  exit 1
fi

ensure_podman_ready() {
  if podman info >/dev/null 2>&1; then
    echo "Podman machine 已连接。"
    return
  fi

  local machine_state
  machine_state="$(podman machine inspect "$PODMAN_MACHINE" --format '{{.State}}' 2>/dev/null || true)"
  if [ "$machine_state" = "running" ]; then
    echo "Podman machine 显示为 running，但 Podman socket 不可用。" >&2
    echo "请先停止残留的 podman machine start/vfkit 进程，再修复或重建 machine。" >&2
    exit 1
  fi

  echo "Podman 当前未连接，尝试启动 machine：$PODMAN_MACHINE"
  if ! podman machine start "$PODMAN_MACHINE"; then
    echo "Podman machine 启动失败：$PODMAN_MACHINE" >&2
    echo "请先执行：podman machine list && podman machine start $PODMAN_MACHINE" >&2
    exit 1
  fi

  if ! podman info >/dev/null 2>&1; then
    echo "Podman machine 已启动，但 Podman socket 仍不可用。" >&2
    exit 1
  fi
  echo "Podman machine 已就绪：$PODMAN_MACHINE"
}

pull_image() {
  local image="$1"
  local started_at
  local pull_pid
  local elapsed

  echo "开始拉取镜像：$image"
  # 后台拉取，主进程可以定期输出心跳，避免大镜像下载时看起来像卡死。
  podman --log-level=info pull "$image" &
  pull_pid=$!
  started_at="$(date +%s)"

  # Podman 的详细层进度可能因终端或网络而不刷新，因此额外输出等待时间。
  while kill -0 "$pull_pid" 2>/dev/null; do
    elapsed=$(( $(date +%s) - started_at ))
    echo "仍在拉取 $image，已等待 ${elapsed}s..."
    sleep 10
  done

  wait "$pull_pid"
  echo "镜像拉取完成：$image"
}

ensure_podman_ready
pull_image "$NEO4J_IMAGE"

echo "Neo4j Podman 镜像已准备完成。"
echo "Neo4j:  $NEO4J_IMAGE"
