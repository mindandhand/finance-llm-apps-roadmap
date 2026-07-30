#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../08-team-research"

cd "$DEMO_DIR"
python team_research_agentos.py "$@"
