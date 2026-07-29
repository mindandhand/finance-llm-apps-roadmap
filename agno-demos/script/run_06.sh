#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../06-streaming-events"

cd "$DEMO_DIR"
python3 streaming_events_agent.py "$@"
