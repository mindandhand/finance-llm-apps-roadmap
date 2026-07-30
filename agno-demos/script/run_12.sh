#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../12-finance-research-console"

cd "$DEMO_DIR"
python research_console.py "$@"
