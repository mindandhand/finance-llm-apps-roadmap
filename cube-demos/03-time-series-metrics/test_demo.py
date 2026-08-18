from pathlib import Path
import unittest


DEMO_DIR = Path(__file__).resolve().parent
SHARED_DIR = DEMO_DIR.parent


class TimeSeriesMetricsDemoTest(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (DEMO_DIR / relative_path).read_text(encoding="utf-8")

    def test_demo_reuses_the_shared_runtime_and_transactions_model(self) -> None:
        self.assertTrue((DEMO_DIR / "demo.sh").is_file())
        self.assertTrue((SHARED_DIR / "compose.yaml").is_file())
        self.assertTrue(
            (SHARED_DIR / "02-first-financial-cube/model/transactions.yml").is_file()
        )

        script = self.read("demo.sh")
        self.assertIn("../demo.sh", script)
        self.assertIn("./02-first-financial-cube/model", script)

    def test_entrypoint_covers_time_buckets_filters_and_boundaries(self) -> None:
        script = self.read("demo.sh")

        self.assertIn('"granularity":"day"', script)
        self.assertIn('"granularity":"month"', script)
        self.assertIn('"dateRange":["2025-01-02","2025-01-03"]', script)
        self.assertIn('"timezone":"UTC"', script)
        self.assertIn('"member":"transactions.side"', script)
        self.assertIn('"operator":"equals"', script)
        self.assertIn('"values":["buy"]', script)
        self.assertIn('"dateRange":["2025-02-01","2025-02-01"]', script)
        self.assertIn('"granularity":"not-a-granularity"', script)

    def test_entrypoint_asserts_exact_daily_and_monthly_results(self) -> None:
        script = self.read("demo.sh")

        for expected in (
            "113100",
            "96250",
            "209350",
            "203650",
            "13500",
            "14300",
            "27800",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, script)

        self.assertNotIn("trap 'rm -f", script)
        self.assertNotRegex(script, r"sleep\s+(?:[1-9]\d*|0*[1-9])")


if __name__ == "__main__":
    unittest.main()
