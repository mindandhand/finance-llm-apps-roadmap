#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/../22-agentic_knowledge_graph_construction" && pwd)"
cd "$APP_DIR"
exec podman compose up -d neo4j
