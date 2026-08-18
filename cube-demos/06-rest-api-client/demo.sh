#!/usr/bin/env bash
set -euo pipefail

demo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
shared_dir="$(cd "$demo_dir/.." && pwd)"
export CUBE_MODEL_DIR="./05-calculated-measures/model"

case "${1:-start}" in
    start|reset|verify)
        "$shared_dir/demo.sh" "${1:-start}"
        set -a
        source "$shared_dir/.env"
        set +a
        python3 "$demo_dir/client.py"
        echo "Chapter 06 passed."
        ;;
    logs|stop) "$shared_dir/demo.sh" "$1" ;;
    *) echo "Usage: $0 [start|verify|logs|stop|reset]" >&2; exit 2 ;;
esac
