import unittest
from pathlib import Path


MAIN_SOURCE = (
    Path(__file__).resolve().parents[1] / "05-browser-mcp-agent" / "main.py"
).read_text(encoding="utf-8")
MCP_DEMOS = Path(__file__).resolve().parents[1]


class BrowserDemoLocalizationTest(unittest.TestCase):
    def test_prompts_and_user_interface_are_chinese(self):
        for text in (
            "示例指令",
            "导航操作",
            "交互操作",
            "多步骤任务",
            "你的指令",
            "运行指令",
            "使用方法",
            "功能说明",
            "你是一名网页浏览助手",
        ):
            with self.subTest(text=text):
                self.assertIn(text, MAIN_SOURCE)

        for text in (
            "Example Commands",
            "Your Command",
            "Run Command",
            "How to use this app",
            "You are a helpful web browsing assistant",
        ):
            with self.subTest(text=text):
                self.assertNotIn(text, MAIN_SOURCE)

    def test_remaining_demo_entrypoints_use_chinese_prompts_and_comments(self):
        cases = {
            "03-notion-mcp-agent/notion_mcp_agent.py": (
                ("请输入 Notion 页面 ID", "加载环境变量"),
                ("Please enter your Notion page ID", "Load environment variables"),
            ),
            "04-github-mcp-agent/github_agent.py": (
                ("示例查询", "你是 GitHub 助手"),
                ("Example Queries", "You are a GitHub assistant"),
            ),
            "06-multi-mcp-agent/multi_mcp_agent.py": (
                ("多 MCP 智能助手", "校验必需的环境变量"),
                ("Multi-MCP Intelligent Assistant", "Validate required environment variables"),
            ),
            "07-multi-mcp-agent-router/agent_forge.py": (
                ("代码审查员", "根据关键词将查询路由"),
                ("Code Reviewer", "Route a query to the best agent"),
            ),
            "08-travel-planner-mcp-agent-team/app.py": (
                ("立即为以下信息创建", "配置页面"),
                ("IMMEDIATELY create", "Configure the page"),
            ),
            "09-mcp-apps-generative-ui-showcase/src/app/page.tsx": (
                ("预订从纽约到洛杉矶", "发送消息并运行 Agent"),
                ("Book a flight from New York", "Send a message to the chat"),
            ),
            "10-ai-mcp-app-builder/apps/web/app/constants/chatStarters.ts": (
                ("井字棋", "四个起始 Prompt"),
                ("Tic tac toe", "Four starter prompts"),
            ),
        }

        for relative_path, (required, forbidden) in cases.items():
            source = (MCP_DEMOS / relative_path).read_text(encoding="utf-8")
            for text in required:
                with self.subTest(file=relative_path, required=text):
                    self.assertIn(text, source)
            for text in forbidden:
                with self.subTest(file=relative_path, forbidden=text):
                    self.assertNotIn(text, source)


if __name__ == "__main__":
    unittest.main()
