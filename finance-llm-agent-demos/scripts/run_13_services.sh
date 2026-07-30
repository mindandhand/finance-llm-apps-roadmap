#!/usr/bin/env bash
set -euo pipefail

# 默认使用镜像代理；远端模型不需要本地模型容器。
NEO4J_IMAGE="${NEO4J_IMAGE:-docker.m.daocloud.io/library/neo4j:latest}"

if ! command -v podman >/dev/null 2>&1; then
  echo "未找到 podman。请先安装 Podman，并确认 podman machine 已启动。"
  exit 1
fi

# Neo4j 保存图谱数据到 Podman volume，删除容器后数据仍会保留。
podman run -d --replace \
  --name kg-rag-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  -v kg_rag_neo4j_data:/data \
  "$NEO4J_IMAGE"

echo "Neo4j 依赖服务已启动："
echo "- Neo4j Browser: http://localhost:7474"
echo "- Neo4j Bolt:    bolt://localhost:7687"
