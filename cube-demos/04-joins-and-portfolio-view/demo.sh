#!/usr/bin/env bash
set -euo pipefail

demo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
shared_dir="$(cd "$demo_dir/.." && pwd)"
export CUBE_MODEL_DIR="./04-joins-and-portfolio-view/model"

set -a
source "$shared_dir/.env"
set +a

query_cube() {
    curl --max-time 10 -fsS -G --data-urlencode "query=$1" \
        "http://127.0.0.1:${CUBE_PORT}/cubejs-api/v1/load"
}

verify_chapter() {
    local query response
    query='{"measures":["portfolio_holdings.total_market_value"],"dimensions":["portfolio_holdings.portfolio_name","portfolio_holdings.asset_class"],"order":{"portfolio_holdings.portfolio_name":"asc","portfolio_holdings.asset_class":"asc"}}'
    response="$(query_cube "$query")"
    python3 -c '
from decimal import Decimal
import json, sys
rows = json.load(sys.stdin)["data"]
actual = {
    (row["portfolio_holdings.portfolio_name"], row["portfolio_holdings.asset_class"]):
        Decimal(row["portfolio_holdings.total_market_value"])
    for row in rows
}
expected = {
    ("Alpha Growth", "equity_etf"): Decimal("68750"),
    ("Alpha Balanced", "equity_etf"): Decimal("16000"),
    ("Alpha Balanced", "bond_etf"): Decimal("30405"),
    ("Beta Reserve", "bond_etf"): Decimal("50675"),
    ("Beta Reserve", "commodity_etf"): Decimal("34200"),
}
if actual != expected:
    raise SystemExit(f"portfolio holdings mismatch: expected {expected}, got {actual}")
if sum(actual.values()) != Decimal("200030"):
    raise SystemExit("fan-out detected: grouped market value no longer totals 200030")
print("portfolio holdings:", actual)
print("fan-out guard total: 200030")
' <<<"$response"
    echo "Chapter 04 passed."
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
    *)
        echo "Usage: $0 [start|verify|logs|stop|reset]" >&2
        exit 2
        ;;
esac
