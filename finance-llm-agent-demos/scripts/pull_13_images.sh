#!/usr/bin/env bash
set -euo pipefail

# 默认使用镜像代理，避免 Podman 直接访问 Docker Hub 超时。
# 如果当前网络有其他可用仓库，可通过环境变量覆盖这两个地址。
NEO4J_IMAGE="${NEO4J_IMAGE:-docker.m.daocloud.io/library/neo4j:latest}"
OLLAMA_IMAGE="${OLLAMA_IMAGE:-docker.m.daocloud.io/ollama/ollama:latest}"

if ! command -v podman >/dev/null 2>&1; then
  echo "未找到 podman。请先安装 Podman，并确认 podman machine 已启动。"
  exit 1
fi

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

pull_image "$NEO4J_IMAGE"
pull_image "$OLLAMA_IMAGE"

echo "Podman 镜像已准备完成。"
echo "Neo4j:  $NEO4J_IMAGE"
echo "Ollama: $OLLAMA_IMAGE"
