#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../10-agui-fastapi"

cd "$DEMO_DIR"
python agui_fastapi.py "$@"
