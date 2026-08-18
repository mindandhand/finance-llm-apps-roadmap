from __future__ import annotations

from decimal import Decimal
import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def build_query(portfolio_name: str | None = None) -> dict[str, Any]:
    query: dict[str, Any] = {
        "measures": ["portfolio_holdings.total_market_value"],
        "dimensions": [
            "portfolio_holdings.portfolio_name",
            "portfolio_holdings.asset_class",
        ],
        "order": {"portfolio_holdings.total_market_value": "desc"},
        "limit": 100,
    }
    if portfolio_name:
        query["filters"] = [
            {
                "member": "portfolio_holdings.portfolio_name",
                "operator": "equals",
                "values": [portfolio_name],
            }
        ]
    return query


def normalize_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "组合": row["portfolio_holdings.portfolio_name"],
            "资产类别": row["portfolio_holdings.asset_class"],
            "持仓市值": Decimal(row["portfolio_holdings.total_market_value"]),
        }
        for row in rows
    ]


def fetch_rows(base_url: str, query: dict[str, Any], timeout: float = 10) -> list[dict[str, str]]:
    encoded = urlencode({"query": json.dumps(query, separators=(",", ":"))})
    request = Request(f"{base_url.rstrip('/')}/cubejs-api/v1/load?{encoded}")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))["data"]
