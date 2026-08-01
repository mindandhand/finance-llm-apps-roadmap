#!/usr/bin/env bash
set -euo pipefail

MODEL="${MODEL:-llama3.2}"
# 默认使用镜像代理；可通过 NEO4J_IMAGE 和 OLLAMA_IMAGE 替换镜像来源。
NEO4J_IMAGE="${NEO4J_IMAGE:-docker.m.daocloud.io/library/neo4j:latest}"
OLLAMA_IMAGE="${OLLAMA_IMAGE:-docker.m.daocloud.io/ollama/ollama:latest}"

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

# Ollama 保存模型到独立 volume，避免重复下载模型。
podman run -d --replace \
  --name kg-rag-ollama \
  -p 11434:11434 \
  -v kg_rag_ollama_data:/root/.ollama \
  "$OLLAMA_IMAGE"

# 容器启动后等待服务就绪，再从容器内部下载模型。
echo "等待 Ollama 服务启动..."
sleep 5
podman exec kg-rag-ollama ollama pull "$MODEL"

echo "依赖服务已启动："
echo "- Neo4j Browser: http://localhost:7474"
echo "- Neo4j Bolt:    bolt://localhost:7687"
echo "- Ollama Host:   http://localhost:11434"
echo "- Model:         $MODEL"
