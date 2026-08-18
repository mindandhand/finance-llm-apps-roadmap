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

verify_daily() {
    local query response
    query='{"measures":["transactions.count","transactions.total_quantity","transactions.total_amount"],"timeDimensions":[{"dimension":"transactions.traded_at","granularity":"day","dateRange":["2025-01-02","2025-01-03"]}],"timezone":"UTC"}'
    response="$(query_cube "$query")"

    python3 -c '
from decimal import Decimal
import json
import sys

expected = {
    "2025-01-02": (Decimal("3"), Decimal("13500"), Decimal("113100")),
    "2025-01-03": (Decimal("5"), Decimal("14300"), Decimal("96250")),
}
rows = json.load(sys.stdin)["data"]
actual = {
    row["transactions.traded_at.day"][:10]: (
        Decimal(row["transactions.count"]),
        Decimal(row["transactions.total_quantity"]),
        Decimal(row["transactions.total_amount"]),
    )
    for row in rows
}
if actual != expected:
    raise SystemExit(f"daily mismatch: expected {expected}, got {actual}")
print("daily metrics:", actual)
' <<<"$response"
}

verify_monthly() {
    local query response
    query='{"measures":["transactions.count","transactions.total_quantity","transactions.total_amount"],"timeDimensions":[{"dimension":"transactions.traded_at","granularity":"month","dateRange":["2025-01-01","2025-01-31"]}],"timezone":"UTC"}'
    response="$(query_cube "$query")"

    python3 -c '
from decimal import Decimal
import json
import sys

rows = json.load(sys.stdin)["data"]
if len(rows) != 1:
    raise SystemExit(f"expected one monthly bucket, got {len(rows)}")
row = rows[0]
actual = (
    row["transactions.traded_at.month"][:7],
    Decimal(row["transactions.count"]),
    Decimal(row["transactions.total_quantity"]),
    Decimal(row["transactions.total_amount"]),
)
expected = ("2025-01", Decimal("8"), Decimal("27800"), Decimal("209350"))
if actual != expected:
    raise SystemExit(f"monthly mismatch: expected {expected}, got {actual}")
print("monthly metrics:", actual)
' <<<"$response"
}

verify_buy_filter() {
    local query response
    query='{"measures":["transactions.count","transactions.total_amount"],"timeDimensions":[{"dimension":"transactions.traded_at","granularity":"day","dateRange":["2025-01-02","2025-01-03"]}],"filters":[{"member":"transactions.side","operator":"equals","values":["buy"]}],"timezone":"UTC"}'
    response="$(query_cube "$query")"

    python3 -c '
from decimal import Decimal
import json
import sys

expected = {
    "2025-01-02": (Decimal("3"), Decimal("113100")),
    "2025-01-03": (Decimal("4"), Decimal("90550")),
}
rows = json.load(sys.stdin)["data"]
actual = {
    row["transactions.traded_at.day"][:10]: (
        Decimal(row["transactions.count"]),
        Decimal(row["transactions.total_amount"]),
    )
    for row in rows
}
if actual != expected:
    raise SystemExit(f"buy-filter mismatch: expected {expected}, got {actual}")
if sum(value[1] for value in actual.values()) != Decimal("203650"):
    raise SystemExit("daily BUY amounts do not add up to the filtered total 203650")
print("daily buy metrics:", actual)
' <<<"$response"
}

verify_empty_range() {
    local query response
    query='{"measures":["transactions.count","transactions.total_amount"],"timeDimensions":[{"dimension":"transactions.traded_at","granularity":"day","dateRange":["2025-02-01","2025-02-01"]}],"timezone":"UTC"}'
    response="$(query_cube "$query")"

    python3 -c '
import json
import sys

rows = json.load(sys.stdin)["data"]
if rows:
    raise SystemExit(f"expected an empty date range, got {rows}")
print("empty range: []")
' <<<"$response"
}

verify_invalid_granularity() {
    local error_file query status
    error_file="$(mktemp)"
    query='{"measures":["transactions.count"],"timeDimensions":[{"dimension":"transactions.traded_at","granularity":"not-a-granularity","dateRange":["2025-01-02","2025-01-03"]}],"timezone":"UTC"}'
    status="$(curl --max-time 10 -sS -o "$error_file" -w '%{http_code}' -G \
        --data-urlencode "query=$query" \
        "http://127.0.0.1:${CUBE_PORT}/cubejs-api/v1/load")"

    if [[ "$status" -lt 400 ]]; then
        rm -f "$error_file"
        echo "Invalid granularity unexpectedly returned HTTP $status." >&2
        return 1
    fi
    rm -f "$error_file"
    echo "invalid granularity rejected: HTTP $status"
}

verify_chapter() {
    verify_daily
    verify_monthly
    verify_buy_filter
    verify_empty_range
    verify_invalid_granularity
    echo "Chapter 03 passed."
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
