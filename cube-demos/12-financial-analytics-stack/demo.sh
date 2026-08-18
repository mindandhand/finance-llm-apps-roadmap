#!/usr/bin/env bash
set -euo pipefail

demo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cube_demos="$(cd "$demo_dir/.." && pwd)"

"$cube_demos/04-joins-and-portfolio-view/demo.sh" start
"$cube_demos/06-rest-api-client/demo.sh" start
"$cube_demos/09-access-control/demo.sh" start
"$cube_demos/11-semantic-layer-for-llm/demo.sh" start
python3 -m unittest "$cube_demos/10-streamlit-dashboard/test_demo.py" -v

if [[ "${FULL_STACK:-0}" == "1" ]]; then
    "$cube_demos/07-sql-api-and-pandas/demo.sh" start
    "$cube_demos/08-pre-aggregations/demo.sh" start
fi

echo "Chapter 12 passed."
