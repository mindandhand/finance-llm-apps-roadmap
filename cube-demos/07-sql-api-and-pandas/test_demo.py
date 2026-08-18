from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class SqlApiPandasTest(unittest.TestCase):
    def test_client_queries_semantic_members(self) -> None:
        client = (ROOT / "query_with_pandas.py").read_text(encoding="utf-8")
        self.assertIn("MEASURE(total_amount)", client)
        self.assertIn("FROM transactions", client)
        self.assertIn("pd.read_sql_query", client)
        self.assertNotIn("public.transactions", client)


if __name__ == "__main__":
    unittest.main()
