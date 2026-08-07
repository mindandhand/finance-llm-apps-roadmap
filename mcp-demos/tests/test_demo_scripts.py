import os
import subprocess
import unittest
from pathlib import Path


MCP_DEMOS = Path(__file__).resolve().parents[1]
SCRIPTS = MCP_DEMOS / "scripts"

EXPECTED_COMMANDS = {
    "01": "agent.py",
    "02": "agent.py",
    "03": "notion_mcp_agent.py",
    "04": "streamlit run github_agent.py",
    "05": "streamlit run main.py",
    "06": "multi_mcp_agent.py",
    "07": "streamlit run agent_forge.py",
    "08": "streamlit run app.py",
    "09": "npm run dev",
    "10": "pnpm dev",
}


class DemoScriptsTest(unittest.TestCase):
    def test_numbered_launchers_exist_and_are_executable(self):
        for number in EXPECTED_COMMANDS:
            script = SCRIPTS / f"run_{number}.sh"
            with self.subTest(script=script.name):
                self.assertTrue(script.is_file())
                self.assertTrue(os.access(script, os.X_OK))

    def test_launchers_use_safe_bash_and_expected_entrypoint(self):
        for number, command in EXPECTED_COMMANDS.items():
            script = SCRIPTS / f"run_{number}.sh"
            with self.subTest(script=script.name):
                source = script.read_text(encoding="utf-8")
                self.assertTrue(source.startswith("#!/usr/bin/env bash\n"))
                self.assertIn("set -euo pipefail", source)
                self.assertIn('SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"', source)
                self.assertIn("DEMO_DIR=", source)
                self.assertIn(command, source)

    def test_launchers_pass_bash_syntax_check(self):
        for number in EXPECTED_COMMANDS:
            script = SCRIPTS / f"run_{number}.sh"
            with self.subTest(script=script.name):
                result = subprocess.run(
                    ["bash", "-n", str(script)],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_overview_documents_numbered_launchers(self):
        overview = (MCP_DEMOS / "README.md").read_text(encoding="utf-8")
        self.assertIn("scripts/run_01.sh", overview)
        self.assertIn("scripts/run_10.sh", overview)
        self.assertIn("MCP_PYTHON", overview)
        self.assertIn("MCP_LLM_MODEL", overview)


if __name__ == "__main__":
    unittest.main()
