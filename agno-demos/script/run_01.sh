#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../01-hello-agent"

cd "$DEMO_DIR"
python hello_agent.py "$@"
