#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../09-workflow-report"

cd "$DEMO_DIR"
python workflow_report_agentos.py "$@"
