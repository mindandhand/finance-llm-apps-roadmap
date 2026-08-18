#!/usr/bin/env bash
set -euo pipefail

demo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
shared_dir="$(cd "$demo_dir/.." && pwd)"
export CUBE_MODEL_DIR="./08-pre-aggregations/model"
export COMPOSE_PROFILES="preaggregation"
export CUBE_COMPOSE_OVERRIDE="08-pre-aggregations/compose.yaml"

set -a
source "$shared_dir/.env"
set +a

query='{"measures":["transactions.count","transactions.total_amount"],"dimensions":["transactions.side"],"timeDimensions":[{"dimension":"transactions.traded_at","granularity":"day","dateRange":["2025-01-02","2025-01-03"]}],"timezone":"UTC"}'

query_cube() {
    curl --max-time 30 -fsS -G --data-urlencode "query=$query" \
        "http://127.0.0.1:${CUBE_PORT}/cubejs-api/v1/$1"
}

verify_chapter() {
    local response sql_response
    response="$(query_cube load)"
    sql_response="$(query_cube sql)"
    python3 -c '
from decimal import Decimal
import json, sys
payload = json.loads(sys.argv[1])
rows = payload["data"]
if sum(Decimal(row["transactions.total_amount"]) for row in rows) != Decimal("209350"):
    raise SystemExit(f"rollup result mismatch: {rows}")
sql_payload = json.loads(sys.stdin.read())
sql_text = json.dumps(sql_payload).lower()
if "daily_transactions" not in sql_text:
    raise SystemExit(f"generated SQL does not reference daily_transactions: {sql_payload}")
print("pre-aggregation result:", rows)
print("matched pre-aggregation: daily_transactions")
' "$response" <<<"$sql_response"
    echo "Chapter 08 passed."
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
    logs|stop) "$shared_dir/demo.sh" "$1" ;;
    *) echo "Usage: $0 [start|verify|logs|stop|reset]" >&2; exit 2 ;;
esac
