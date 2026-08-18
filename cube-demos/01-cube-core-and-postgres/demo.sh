#!/usr/bin/env bash
set -euo pipefail

demo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
shared_dir="$(cd "$demo_dir/.." && pwd)"
shared_demo="$demo_dir/../demo.sh"
cd "$demo_dir"
export CUBE_MODEL_DIR="./01-cube-core-and-postgres/model"

load_shared_env() {
    set -a
    source "$shared_dir/.env"
    set +a
}

verify_fixture() {
    local query response
    query='{"dimensions":["fixture_health.table_name","fixture_health.row_count"]}'
    response="$(curl --max-time 10 -fsS -G \
        --data-urlencode "query=$query" \
        "http://127.0.0.1:${CUBE_PORT}/cubejs-api/v1/load")"

    python3 -c '
import json
import sys

expected = {
    "users": 3,
    "securities": 4,
    "daily_prices": 8,
    "portfolios": 3,
    "positions": 6,
    "transactions": 8,
}
payload = json.load(sys.stdin)
actual = {
    row["fixture_health.table_name"]: int(row["fixture_health.row_count"])
    for row in payload["data"]
}
if actual != expected:
    raise SystemExit(f"fixture mismatch: expected {expected}, got {actual}")
print("fixture rows:", actual)
' <<<"$response"
}

case "${1:-start}" in
    start|verify|reset)
        "$shared_demo" "${1:-start}"
        load_shared_env
        verify_fixture
        echo "Chapter 01 passed."
        ;;
    logs|stop)
        "$shared_demo" "$1"
        ;;
    *)
        echo "Usage: $0 [start|verify|logs|stop|reset]" >&2
        exit 2
        ;;
esac
