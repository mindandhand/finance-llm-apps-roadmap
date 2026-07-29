#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../05-session-memory"

cd "$DEMO_DIR"
python session_memory_agentos.py "$@"
