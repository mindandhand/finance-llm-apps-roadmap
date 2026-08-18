from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ALLOWED_MEASURES = {
    "transactions.count",
    "transactions.total_quantity",
    "transactions.total_amount",
}
ALLOWED_DIMENSIONS = {"transactions.side"}
ALLOWED_GRANULARITIES = {"day", "week", "month"}


class QueryRejected(ValueError):
    pass


class ClarificationRequired(ValueError):
    pass


def fake_model(question: str) -> dict[str, Any]:
    if "收益" in question:
        raise ClarificationRequired("请明确收益公式、日期范围、币种和基准。")
    if "成交金额" in question and "方向" in question:
        return {
            "measures": ["transactions.total_amount"],
            "dimensions": ["transactions.side"],
            "order": {"transactions.total_amount": "desc"},
            "limit": 20,
        }
    raise ClarificationRequired("请明确要查询的指标和分组方式。")


def validate_query(query: dict[str, Any]) -> dict[str, Any]:
    if not set(query.get("measures", [])).issubset(ALLOWED_MEASURES):
        raise QueryRejected("query contains a measure outside the allowlist")
    if not set(query.get("dimensions", [])).issubset(ALLOWED_DIMENSIONS):
        raise QueryRejected("query contains a dimension outside the allowlist")
    if not query.get("measures"):
        raise QueryRejected("at least one measure is required")
    if int(query.get("limit", 100)) > 100:
        raise QueryRejected("limit cannot exceed 100")
    for item in query.get("timeDimensions", []):
        if item.get("granularity") not in ALLOWED_GRANULARITIES:
            raise QueryRejected("unsupported time granularity")
    return query


def execute_query(query: dict[str, Any]) -> list[dict[str, str]]:
    encoded = urlencode({"query": json.dumps(query, separators=(",", ":"))})
    url = f"http://127.0.0.1:{os.getenv('CUBE_PORT', '4000')}/cubejs-api/v1/load?{encoded}"
    with urlopen(Request(url), timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))["data"]


if __name__ == "__main__":
    semantic_query = validate_query(fake_model("按交易方向统计成交金额"))
    rows = execute_query(semantic_query)
    print("validated Cube Query:", semantic_query)
    print("deterministic result:", rows)
    print("Chapter 11 passed.")
