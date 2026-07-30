#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../07-human-confirmation"

if [[ "${1:-}" == "--print-examples" ]]; then
  cat <<'EOF'
07 Human Confirmation browser test:

1. Start the service:
   ./script/run_07.sh --serve --port 7777

2. Open the click simulation UI:
   http://127.0.0.1:7777/human-confirmation-ui

3. In the browser, click "创建待确认动作".
   Expected status: pending

4. Click "批准" or "拒绝".
   Expected status: approved or rejected

Equivalent API flow with curl:

  curl -s -X POST http://127.0.0.1:7777/risk-actions \
    -H 'Content-Type: application/json' \
    -d '{"source_symbol":"SH510300","target_symbol":"SH588000","amount_cny":10000,"reason":"模拟用户请求调仓"}'

  curl -s -X POST http://127.0.0.1:7777/risk-actions/<ACTION_ID>/approve \
    -H 'Content-Type: application/json' \
    -d '{"note":"模拟用户点击批准"}'

  curl -s -X POST http://127.0.0.1:7777/risk-actions/<ACTION_ID>/reject \
    -H 'Content-Type: application/json' \
    -d '{"note":"模拟用户点击拒绝"}'
EOF
  exit 0
fi

cd "$DEMO_DIR"
python human_confirmation_agentos.py "$@"
