#!/usr/bin/env bash
set -euo pipefail

demo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
shared_dir="$(cd "$demo_dir/.." && pwd)"
export CUBE_MODEL_DIR="./05-calculated-measures/model"

"$shared_dir/demo.sh" "${1:-start}"
set -a
source "$shared_dir/.env"
set +a
python3 "$demo_dir/agent.py"
