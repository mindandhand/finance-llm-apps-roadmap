#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../14-factor-evaluation-service"
DATA_DIR="$SCRIPT_DIR/../qlib-data"

export QLIB_PROVIDER_URI="${QLIB_PROVIDER_URI:-$DATA_DIR}"
export QLIB_REGION="${QLIB_REGION:-cn}"
source "$SCRIPT_DIR/../qlib_env.sh"
export QLIB_START_TIME="${QLIB_START_TIME:-2015-01-05}"
export QLIB_END_TIME="${QLIB_END_TIME:-2026-07-18}"

# Optional: write metrics to a JSON file
# OUTPUT="$DEMO_DIR/artifacts/metrics.json"

"$QLIB_PYTHON" "$DEMO_DIR/factor_evaluation_service.py" \
  --expression '$close / Ref($close, 20) - 1' \
  --label 'Ref($close, -5) / $close - 1'
  # --output "$OUTPUT"
