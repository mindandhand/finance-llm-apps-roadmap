#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../04-agentos-basic"

cd "$DEMO_DIR"
python agentos_basic.py "$@"
