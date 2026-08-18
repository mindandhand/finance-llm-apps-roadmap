from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class JoinAndViewTest(unittest.TestCase):
    def test_model_and_demo_contract(self) -> None:
        model = (ROOT / "model/portfolio_holdings.yml").read_text(encoding="utf-8")
        demo = (ROOT / "demo.sh").read_text(encoding="utf-8")
        for text in ("relationship: many_to_one", "primary_key: true", "join_path:"):
            self.assertIn(text, model)
        for text in ("portfolio_holdings.total_market_value", "200030", "fan-out"):
            self.assertIn(text, demo)


if __name__ == "__main__":
    unittest.main()
