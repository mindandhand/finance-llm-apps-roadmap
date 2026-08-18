from pathlib import Path
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("agent", ROOT / "agent.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class SemanticAgentTest(unittest.TestCase):
    def test_fake_model_produces_an_allowed_query(self) -> None:
        query = MODULE.validate_query(MODULE.fake_model("按交易方向统计成交金额"))
        self.assertEqual(query["measures"], ["transactions.total_amount"])

    def test_unknown_member_and_large_limit_are_rejected(self) -> None:
        with self.assertRaises(MODULE.QueryRejected):
            MODULE.validate_query({"measures": ["transactions.secret"], "limit": 20})
        with self.assertRaises(MODULE.QueryRejected):
            MODULE.validate_query({"measures": ["transactions.count"], "limit": 1000})

    def test_ambiguous_financial_question_requires_clarification(self) -> None:
        with self.assertRaises(MODULE.ClarificationRequired):
            MODULE.fake_model("今年收益最好的组合")


if __name__ == "__main__":
    unittest.main()
