from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class AdvancedCubeChaptersTest(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def assert_chapter_implemented(self, chapter: str, files: tuple[str, ...]) -> None:
        readme = self.read(f"{chapter}/README.md")
        self.assertNotIn("尚未实现", readme)
        self.assertIn("底层", readme)
        for relative_path in files:
            self.assertTrue((ROOT / chapter / relative_path).is_file(), relative_path)

    def test_04_joins_and_view(self) -> None:
        chapter = "04-joins-and-portfolio-view"
        self.assert_chapter_implemented(chapter, ("demo.sh", "model/portfolio_holdings.yml"))
        model = self.read(f"{chapter}/model/portfolio_holdings.yml")
        for expected in ("relationship: many_to_one", "primary_key: true", "join_path:"):
            self.assertIn(expected, model)

    def test_05_calculated_measures(self) -> None:
        chapter = "05-calculated-measures"
        self.assert_chapter_implemented(chapter, ("demo.sh", "model/transactions.yml"))
        model = self.read(f"{chapter}/model/transactions.yml")
        self.assertIn("weighted_average_price", model)
        self.assertIn("NULLIF", model)

    def test_06_rest_client(self) -> None:
        chapter = "06-rest-api-client"
        self.assert_chapter_implemented(chapter, ("client.py", "demo.sh", "test_demo.py"))
        client = self.read(f"{chapter}/client.py")
        for expected in ("def meta", "def load", "CubeApiError", "timeout"):
            self.assertIn(expected, client)

    def test_07_sql_api_and_pandas(self) -> None:
        chapter = "07-sql-api-and-pandas"
        self.assert_chapter_implemented(
            chapter, ("query_with_pandas.py", "demo.sh", "requirements.txt")
        )
        compose = self.read("compose.yaml")
        self.assertIn("CUBEJS_PG_SQL_PORT", compose)
        self.assertIn("${CUBE_SQL_PORT}:15432", compose)

    def test_08_pre_aggregations(self) -> None:
        chapter = "08-pre-aggregations"
        self.assert_chapter_implemented(chapter, ("demo.sh", "model/transactions.yml"))
        model = self.read(f"{chapter}/model/transactions.yml")
        self.assertIn("pre_aggregations:", model)
        self.assertIn("type: rollup", model)
        self.assertIn("cubestore", self.read("compose.yaml"))

    def test_09_access_control(self) -> None:
        chapter = "09-access-control"
        self.assert_chapter_implemented(
            chapter, ("demo.sh", "model/portfolio_holdings.yml", "cube.py")
        )
        model = self.read(f"{chapter}/model/portfolio_holdings.yml")
        self.assertIn("access_policy:", model)
        self.assertIn("securityContext.tenant_id", model)
        self.assertIn("context_to_groups", self.read(f"{chapter}/cube.py"))

    def test_10_streamlit_dashboard(self) -> None:
        chapter = "10-streamlit-dashboard"
        self.assert_chapter_implemented(
            chapter, ("app.py", "dashboard.py", "demo.sh", "test_demo.py")
        )
        dashboard = self.read(f"{chapter}/dashboard.py")
        self.assertIn("def build_query", dashboard)
        self.assertIn("def normalize_rows", dashboard)

    def test_11_semantic_layer_for_llm(self) -> None:
        chapter = "11-semantic-layer-for-llm"
        self.assert_chapter_implemented(chapter, ("agent.py", "demo.sh", "test_demo.py"))
        agent = self.read(f"{chapter}/agent.py")
        for expected in ("ALLOWED_MEASURES", "validate_query", "fake_model"):
            self.assertIn(expected, agent)

    def test_12_complete_stack(self) -> None:
        chapter = "12-financial-analytics-stack"
        self.assert_chapter_implemented(chapter, ("demo.sh", "test_demo.py"))
        script = self.read(f"{chapter}/demo.sh")
        for expected in ("04-joins", "06-rest", "09-access", "11-semantic"):
            self.assertIn(expected, script)


if __name__ == "__main__":
    unittest.main()
