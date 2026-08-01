#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../05-labels-and-time-splits"
DATA_DIR="$SCRIPT_DIR/../qlib-data"

export QLIB_PROVIDER_URI="$DATA_DIR"
export QLIB_REGION="cn"
source "$SCRIPT_DIR/../qlib_env.sh"
export QLIB_START_TIME="2015-01-05"
export QLIB_END_TIME="2026-07-18"
export QLIB_TRAIN_END_TIME="2022-12-31"
export QLIB_VALID_START_TIME="2023-01-01"
export QLIB_VALID_END_TIME="2023-12-31"
export QLIB_TEST_START_TIME="2024-01-01"

python "$DEMO_DIR/labels_and_time_splits.py"
