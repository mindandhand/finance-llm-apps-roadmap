from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class CalculatedMeasuresTest(unittest.TestCase):
    def test_model_reuses_additive_measures_and_guards_zero(self) -> None:
        model = (ROOT / "model/transactions.yml").read_text(encoding="utf-8")
        self.assertIn("weighted_average_price", model)
        self.assertIn("{total_amount}", model)
        self.assertIn("{total_quantity}", model)
        self.assertIn("NULLIF", model)


if __name__ == "__main__":
    unittest.main()
