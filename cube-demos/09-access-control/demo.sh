#!/usr/bin/env bash
set -euo pipefail

demo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
shared_dir="$(cd "$demo_dir/.." && pwd)"
export CUBE_MODEL_DIR="./09-access-control/model"
export CUBE_CONFIG_PATH="./09-access-control/cube.py"
unset COMPOSE_PROFILES CUBEJS_CUBESTORE_HOST

set -a
source "$shared_dir/.env"
set +a

make_token() {
    python3 -c '
import base64, hashlib, hmac, json, sys, time
secret, tenant = sys.argv[1:]
encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=")
header = encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
payload = encode(json.dumps({"tenant_id": tenant, "groups": ["portfolio_user"], "exp": int(time.time()) + 600}, separators=(",", ":")).encode())
signing_input = header + b"." + payload
signature = encode(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
print((signing_input + b"." + signature).decode())
' "$CUBEJS_API_SECRET" "$1"
}

query_tenant() {
    local token="$1"
    local query='{"measures":["portfolio_holdings.total_market_value"],"dimensions":["portfolio_holdings.tenant_id"]}'
    curl --max-time 15 -fsS -G -H "Authorization: $token" \
        --data-urlencode "query=$query" \
        "http://127.0.0.1:${CUBE_PORT}/cubejs-api/v1/load"
}

verify_chapter() {
    local alpha beta
    alpha="$(query_tenant "$(make_token alpha)")"
    beta="$(query_tenant "$(make_token beta)")"
    python3 -c '
from decimal import Decimal
import json, sys
expected = {"alpha": Decimal("115155"), "beta": Decimal("84875")}
for tenant, raw in zip(("alpha", "beta"), sys.argv[1:], strict=True):
    rows = json.loads(raw)["data"]
    if len(rows) != 1 or rows[0]["portfolio_holdings.tenant_id"] != tenant:
        raise SystemExit(f"tenant isolation failed for {tenant}: {rows}")
    value = Decimal(rows[0]["portfolio_holdings.total_market_value"])
    if value != expected[tenant]:
        raise SystemExit(f"unexpected {tenant} value: {value}")
    print(f"{tenant} visible market value:", value)
' "$alpha" "$beta"
    echo "Chapter 09 passed."
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
