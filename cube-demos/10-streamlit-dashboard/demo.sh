#!/usr/bin/env bash
set -euo pipefail

demo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
shared_dir="$(cd "$demo_dir/.." && pwd)"
export CUBE_MODEL_DIR="./04-joins-and-portfolio-view/model"

if [[ "${1:-start}" == "ui" ]]; then
    exec streamlit run "$demo_dir/app.py"
fi

"$shared_dir/demo.sh" "${1:-start}"
set -a
source "$shared_dir/.env"
set +a
PYTHONPATH="$demo_dir" python3 -c '
import os
from dashboard import build_query, fetch_rows, normalize_rows
rows = normalize_rows(fetch_rows(f"http://127.0.0.1:{os.environ["CUBE_PORT"]}", build_query()))
if sum(row["持仓市值"] for row in rows) != 200030:
    raise SystemExit(f"dashboard total mismatch: {rows}")
print("dashboard rows:", rows)
print("Chapter 10 passed.")
'
