import unittest
from pathlib import Path


MCP_DEMOS = Path(__file__).resolve().parents[1]


class AgnoMigrationTest(unittest.TestCase):
    def test_filesystem_demo_uses_agno_and_deepseek(self):
        self.assert_agno_demo("01-filesystem-mcp", "deepseek-v4-flash")

    def test_firecrawl_demo_uses_agno_and_deepseek(self):
        self.assert_agno_demo("02-firecrawl-mcp", "deepseek-v4-pro")

    def test_firecrawl_demo_uses_keyless_mode(self):
        source = (MCP_DEMOS / "02-firecrawl-mcp" / "agent.py").read_text(
            encoding="utf-8"
        )
        launcher = (MCP_DEMOS / "scripts" / "run_02.sh").read_text(
            encoding="utf-8"
        )
        readme = (MCP_DEMOS / "02-firecrawl-mcp" / "README.md").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("FIRECRAWL_API_KEY", source)
        self.assertNotIn("FIRECRAWL_API_KEY", launcher)
        self.assertIn(
            'include_tools=["firecrawl_scrape", "firecrawl_search"]', source
        )
        self.assertIn("Keyless", readme)
        self.assertIn("无需注册", readme)

    def test_old_adk_directories_are_removed(self):
        self.assertFalse((MCP_DEMOS / "01-adk-filesystem-mcp").exists())
        self.assertFalse((MCP_DEMOS / "02-adk-firecrawl-mcp").exists())

    def test_overview_no_longer_lists_google_adk(self):
        overview = (MCP_DEMOS / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("Google ADK", overview)
        self.assertIn("01-filesystem-mcp", overview)
        self.assertIn("02-firecrawl-mcp", overview)

    def test_shared_model_config_is_deepseek_compatible(self):
        config = (MCP_DEMOS / "llm_config.py").read_text(encoding="utf-8")
        self.assertIn('DEFAULT_MODEL = "deepseek-v4-pro"', config)
        self.assertIn('"system": "system"', config)
        self.assertIn('"model": "assistant"', config)

    def assert_agno_demo(self, directory: str, model: str):
        demo_dir = MCP_DEMOS / directory
        source = (demo_dir / "agent.py").read_text(encoding="utf-8")
        requirements = (demo_dir / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("from agno.agent import Agent", source)
        self.assertIn("from agno.tools.mcp import MCPTools", source)
        self.assertIn("create_agno_openai_model", source)
        self.assertIn(f'default_model="{model}"', source)
        self.assertNotIn("google.adk", source)
        self.assertNotIn("gemini", source.lower())
        self.assertIn("agno", requirements)
        self.assertNotIn("google-adk", requirements)


if __name__ == "__main__":
    unittest.main()
