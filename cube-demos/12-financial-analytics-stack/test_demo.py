from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class CompleteStackTest(unittest.TestCase):
    def test_entrypoint_reuses_verified_chapters(self) -> None:
        script = (ROOT / "demo.sh").read_text(encoding="utf-8")
        for chapter in (
            "04-joins-and-portfolio-view",
            "06-rest-api-client",
            "09-access-control",
            "11-semantic-layer-for-llm",
        ):
            self.assertIn(chapter, script)
        self.assertNotRegex(script, r"sleep\s+[1-9]")


if __name__ == "__main__":
    unittest.main()
