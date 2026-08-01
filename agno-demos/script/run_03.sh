#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../03-structured-output"

cd "$DEMO_DIR"
python structured_output_agent.py "$@"
