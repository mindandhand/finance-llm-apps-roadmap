#!/usr/bin/env bash
set -euo pipefail

demo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
shared_dir="$(cd "$demo_dir/.." && pwd)"
export CUBE_MODEL_DIR="./05-calculated-measures/model"

set -a
source "$shared_dir/.env"
set +a

query_cube() {
    curl --max-time 10 -fsS -G --data-urlencode "query=$1" \
        "http://127.0.0.1:${CUBE_PORT}/cubejs-api/v1/load"
}

verify_chapter() {
    local response
    response="$(query_cube '{"measures":["transactions.total_amount","transactions.total_quantity","transactions.weighted_average_price"]}')"
    python3 -c '
from decimal import Decimal
import json, sys
row = json.load(sys.stdin)["data"][0]
amount = Decimal(row["transactions.total_amount"])
quantity = Decimal(row["transactions.total_quantity"])
average = Decimal(row["transactions.weighted_average_price"])
expected = amount / quantity
if amount != Decimal("209350") or quantity != Decimal("27800"):
    raise SystemExit(f"unexpected base measures: {row}")
if abs(average - expected) > Decimal("0.00000001"):
    raise SystemExit(f"weighted average mismatch: expected {expected}, got {average}")
print("calculated measures:", {"amount": amount, "quantity": quantity, "weighted_average_price": average})
' <<<"$response"
    echo "Chapter 05 passed."
}

case "${1:-start}" in
    start|reset)
        "$shared_dir/demo.sh" "${1:-start}"
        verify_chapter
        ;;
    verify)
        "$shared_dir/demo.sh" verify
        verify_chapter
        ;;
    logs|stop)
        "$shared_dir/demo.sh" "$1"
        ;;
    *) echo "Usage: $0 [start|verify|logs|stop|reset]" >&2; exit 2 ;;
esac
