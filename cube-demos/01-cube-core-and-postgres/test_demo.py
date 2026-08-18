from pathlib import Path
import re
import unittest


DEMO_DIR = Path(__file__).resolve().parent
SHARED_DIR = DEMO_DIR.parent
TABLES = (
    "users",
    "securities",
    "daily_prices",
    "portfolios",
    "positions",
    "transactions",
)


class CubeCorePostgresDemoTest(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (DEMO_DIR / relative_path).read_text(encoding="utf-8")

    def read_shared(self, relative_path: str) -> str:
        return (SHARED_DIR / relative_path).read_text(encoding="utf-8")

    def test_demo_contains_the_runnable_contract(self) -> None:
        for relative_path in (
            "model/fixture_health.yml",
            "demo.sh",
        ):
            with self.subTest(relative_path=relative_path):
                self.assertTrue((DEMO_DIR / relative_path).is_file())

        for relative_path in (
            ".env.example",
            "compose.yaml",
            "demo.sh",
            "data/schema.sql",
            "data/seed.sql",
        ):
            with self.subTest(relative_path=relative_path):
                self.assertTrue((SHARED_DIR / relative_path).is_file())

    def test_compose_uses_pinned_images_and_the_service_hostname(self) -> None:
        compose = self.read_shared("compose.yaml")

        self.assertIn("image: postgres:16.14-alpine", compose)
        self.assertIn("image: cubejs/cube:v1.7.11", compose)
        self.assertNotIn(":latest", compose)
        self.assertIn("CUBEJS_DB_HOST: postgres", compose)
        self.assertIn("CUBEJS_DEV_MODE: \"true\"", compose)
        self.assertIn("${CUBE_MODEL_DIR:-./01-cube-core-and-postgres/model}:/cube/conf/model:ro", compose)

    def test_example_ports_do_not_collide_with_the_existing_postgres(self) -> None:
        env_example = self.read_shared(".env.example")

        self.assertIn("POSTGRES_PORT=55432", env_example)

    def test_fixture_defines_and_seeds_every_shared_table(self) -> None:
        schema = self.read_shared("data/schema.sql")
        seed = self.read_shared("data/seed.sql")

        for table in TABLES:
            with self.subTest(table=table):
                self.assertRegex(
                    schema,
                    rf"CREATE TABLE public\.{re.escape(table)}\b",
                )
                self.assertRegex(
                    seed,
                    rf"INSERT INTO public\.{re.escape(table)}\b",
                )

    def test_health_model_checks_all_fixture_tables(self) -> None:
        model = self.read("model/fixture_health.yml")

        self.assertIn("name: fixture_health", model)
        for table in TABLES:
            with self.subTest(table=table):
                self.assertIn(f"public.{table}", model)

    def test_entrypoint_checks_database_readiness_and_cube_query(self) -> None:
        script = self.read("demo.sh")

        self.assertNotIn("--project-directory", script)
        self.assertIn('cd "$demo_dir"', script)
        self.assertIn("../demo.sh", script)
        self.assertIn("/cubejs-api/v1/load", script)
        self.assertIn("fixture_health.row_count", script)
        self.assertNotRegex(script, r"sleep\s+(?:[1-9]\d*|0*[1-9])")

    def test_shared_entrypoint_checks_database_and_cube_readiness(self) -> None:
        script = self.read_shared("demo.sh")

        self.assertIn("pg_isready", script)
        self.assertIn("/readyz", script)


if __name__ == "__main__":
    unittest.main()
