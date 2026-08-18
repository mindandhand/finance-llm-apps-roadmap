from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class PreAggregationTest(unittest.TestCase):
    def test_rollup_and_evidence_contract(self) -> None:
        model = (ROOT / "model/transactions.yml").read_text(encoding="utf-8")
        demo = (ROOT / "demo.sh").read_text(encoding="utf-8")
        for text in ("type: rollup", "daily_transactions", "granularity: day"):
            self.assertIn(text, model)
        self.assertIn("cubejs-api/v1/$1", demo)
        self.assertIn("daily_transactions", demo)


if __name__ == "__main__":
    unittest.main()
