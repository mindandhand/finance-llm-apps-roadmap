import unittest
from pathlib import Path


MAIN_SOURCE = (
    Path(__file__).resolve().parents[1] / "05-browser-mcp-agent" / "main.py"
).read_text(encoding="utf-8")


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


if __name__ == "__main__":
    unittest.main()
