#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../13-custom-data-provider"
source "$SCRIPT_DIR/../qlib_env.sh"

# This demo does not use qlib init; it demonstrates raw data validation and
# transformation before loading into qlib.
"$QLIB_PYTHON" "$DEMO_DIR/custom_data_provider.py"
