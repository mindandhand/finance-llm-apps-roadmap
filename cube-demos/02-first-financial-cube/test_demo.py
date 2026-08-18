from pathlib import Path
import unittest


DEMO_DIR = Path(__file__).resolve().parent
SHARED_DIR = DEMO_DIR.parent


class FirstFinancialCubeDemoTest(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (DEMO_DIR / relative_path).read_text(encoding="utf-8")

    def read_shared(self, relative_path: str) -> str:
        return (SHARED_DIR / relative_path).read_text(encoding="utf-8")

    def test_demo_contains_the_runnable_contract(self) -> None:
        for relative_path in ("demo.sh", "model/transactions.yml"):
            with self.subTest(relative_path=relative_path):
                self.assertTrue((DEMO_DIR / relative_path).is_file())

        for relative_path in (".env.example", "compose.yaml", "demo.sh"):
            with self.subTest(relative_path=relative_path):
                self.assertTrue((SHARED_DIR / relative_path).is_file())

    def test_compose_reuses_chapter_one_database(self) -> None:
        compose = self.read_shared("compose.yaml")

        self.assertIn("image: cubejs/cube:v1.7.11", compose)
        self.assertIn("image: postgres:16.14-alpine", compose)
        self.assertIn("CUBEJS_DB_HOST: postgres", compose)
        self.assertIn("${CUBE_MODEL_DIR:-./01-cube-core-and-postgres/model}:/cube/conf/model:ro", compose)
        self.assertIn('"${CUBE_PORT}:4000"', compose)

    def test_transactions_model_defines_dimensions_and_measures(self) -> None:
        model = self.read("model/transactions.yml")

        self.assertIn("name: transactions", model)
        self.assertIn("sql_table: public.transactions", model)
        self.assertIn("name: id", model)
        self.assertIn("primary_key: true", model)
        self.assertIn("name: side", model)
        self.assertIn("name: traded_at", model)
        self.assertIn("name: count", model)
        self.assertIn("name: total_quantity", model)
        self.assertIn("sql: quantity", model)
        self.assertIn("name: total_amount", model)
        self.assertIn('sql: "quantity * price"', model)

    def test_entrypoint_asserts_totals_groups_and_invalid_member(self) -> None:
        script = self.read("demo.sh")

        self.assertIn("../demo.sh", script)
        self.assertIn("02-first-financial-cube/model", script)
        self.assertIn("transactions.count", script)
        self.assertIn("transactions.total_quantity", script)
        self.assertIn("transactions.total_amount", script)
        self.assertIn("transactions.side", script)
        self.assertIn("transactions.not_a_member", script)
        self.assertIn("209350", script)
        self.assertIn("27800", script)
        self.assertNotRegex(script, r"sleep\s+(?:[1-9]\d*|0*[1-9])")


if __name__ == "__main__":
    unittest.main()
