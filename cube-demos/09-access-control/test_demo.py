from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class AccessControlTest(unittest.TestCase):
    def test_policy_uses_signed_context_instead_of_query_parameter(self) -> None:
        model = (ROOT / "model/portfolio_holdings.yml").read_text(encoding="utf-8")
        config = (ROOT / "cube.py").read_text(encoding="utf-8")
        demo = (ROOT / "demo.sh").read_text(encoding="utf-8")
        self.assertIn("access_policy:", model)
        self.assertIn("securityContext.tenant_id", model)
        self.assertIn("context_to_groups", config)
        self.assertIn('"alg": "HS256"', demo)
        self.assertIn("115155", demo)
        self.assertIn("84875", demo)


if __name__ == "__main__":
    unittest.main()
