from decimal import Decimal
from pathlib import Path
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("dashboard", ROOT / "dashboard.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class DashboardTest(unittest.TestCase):
    def test_filter_is_translated_to_a_cube_query(self) -> None:
        query = MODULE.build_query("Alpha Growth")
        self.assertEqual(query["filters"][0]["values"], ["Alpha Growth"])
        self.assertEqual(query["limit"], 100)

    def test_rows_preserve_decimal_values(self) -> None:
        rows = MODULE.normalize_rows([{
            "portfolio_holdings.portfolio_name": "Alpha Growth",
            "portfolio_holdings.asset_class": "equity_etf",
            "portfolio_holdings.total_market_value": "68750.00",
        }])
        self.assertEqual(rows[0]["持仓市值"], Decimal("68750.00"))


if __name__ == "__main__":
    unittest.main()
