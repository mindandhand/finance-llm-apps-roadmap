#!/usr/bin/env bash
set -euo pipefail

demo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
shared_dir="$(cd "$demo_dir/.." && pwd)"
shared_demo="$demo_dir/../demo.sh"
export CUBE_MODEL_DIR="./02-first-financial-cube/model"

load_shared_env() {
    set -a
    source "$shared_dir/.env"
    set +a
}

query_cube() {
    curl --max-time 10 -fsS -G \
        --data-urlencode "query=$1" \
        "http://127.0.0.1:${CUBE_PORT}/cubejs-api/v1/load"
}

verify_totals() {
    local query response
    query='{"measures":["transactions.count","transactions.total_quantity","transactions.total_amount"]}'
    response="$(query_cube "$query")"

    python3 -c '
from decimal import Decimal
import json
import sys

row = json.load(sys.stdin)["data"][0]
expected = {
    "transactions.count": Decimal("8"),
    "transactions.total_quantity": Decimal("27800"),
    "transactions.total_amount": Decimal("209350"),
}
actual = {key: Decimal(row[key]) for key in expected}
if actual != expected:
    raise SystemExit(f"total mismatch: expected {expected}, got {actual}")
print("transaction totals:", {key: str(value) for key, value in actual.items()})
' <<<"$response"
}

verify_by_side() {
    local query response
    query='{"measures":["transactions.count","transactions.total_quantity","transactions.total_amount"],"dimensions":["transactions.side"]}'
    response="$(query_cube "$query")"

    python3 -c '
from decimal import Decimal
import json
import sys

expected = {
    "buy": (Decimal("7"), Decimal("26800"), Decimal("203650")),
    "sell": (Decimal("1"), Decimal("1000"), Decimal("5700")),
}
rows = json.load(sys.stdin)["data"]
actual = {
    row["transactions.side"]: (
        Decimal(row["transactions.count"]),
        Decimal(row["transactions.total_quantity"]),
        Decimal(row["transactions.total_amount"]),
    )
    for row in rows
}
if actual != expected:
    raise SystemExit(f"side breakdown mismatch: expected {expected}, got {actual}")
print("side breakdown:", actual)
' <<<"$response"
}

verify_invalid_member() {
    local error_file query status
    error_file="$(mktemp)"
    query='{"measures":["transactions.not_a_member"]}'
    status="$(curl --max-time 10 -sS -o "$error_file" -w '%{http_code}' -G \
        --data-urlencode "query=$query" \
        "http://127.0.0.1:${CUBE_PORT}/cubejs-api/v1/load")"

    if [[ "$status" -lt 400 ]]; then
        rm -f "$error_file"
        echo "Invalid member unexpectedly returned HTTP $status." >&2
        return 1
    fi
    if ! grep -q "not_a_member" "$error_file"; then
        rm -f "$error_file"
        echo "Invalid-member response did not identify the rejected member." >&2
        return 1
    fi
    rm -f "$error_file"
    echo "invalid member rejected: HTTP $status"
}

verify_chapter() {
    verify_totals
    verify_by_side
    verify_invalid_member
    echo "Chapter 02 passed."
}

case "${1:-start}" in
    start|verify|reset)
        "$shared_demo" "${1:-start}"
        load_shared_env
        verify_chapter
        ;;
    logs|stop)
        "$shared_demo" "$1"
        ;;
    *)
        echo "Usage: $0 [start|verify|logs|stop|reset]" >&2
        exit 2
        ;;
esac
