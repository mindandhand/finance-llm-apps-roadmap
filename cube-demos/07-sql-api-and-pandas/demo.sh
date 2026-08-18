#!/usr/bin/env bash
set -euo pipefail

demo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
shared_dir="$(cd "$demo_dir/.." && pwd)"
export CUBE_MODEL_DIR="./05-calculated-measures/model"
python_bin="python3"
if [[ -x "$demo_dir/.venv/bin/python" ]]; then
    python_bin="$demo_dir/.venv/bin/python"
fi

case "${1:-start}" in
    start|reset|verify)
        "$shared_dir/demo.sh" "${1:-start}"
        set -a
        source "$shared_dir/.env"
        set +a
        "$python_bin" "$demo_dir/query_with_pandas.py"
        ;;
    logs|stop) "$shared_dir/demo.sh" "$1" ;;
    *) echo "Usage: $0 [start|verify|logs|stop|reset]" >&2; exit 2 ;;
esac
