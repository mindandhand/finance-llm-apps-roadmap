"""DeepSeek + Agno + Filesystem MCP 的最小示例。"""

import asyncio
import sys
from pathlib import Path

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.mcp import MCPTools
from dotenv import load_dotenv
from mcp import StdioServerParameters

sys.path.append(str(Path(__file__).resolve().parents[1]))
from llm_config import create_agno_openai_model, get_llm_api_key


DEMO_FOLDER = Path(__file__).resolve().parent / "data"


async def main():
    load_dotenv()
    if not get_llm_api_key():
        print("错误：请设置 DEEPSEEK_API_KEY、OPENAI_API_KEY 或 LLM_API_KEY。")
        return

    DEMO_FOLDER.mkdir(exist_ok=True)
    sample_file = DEMO_FOLDER / "sample.txt"
    if not sample_file.exists():
        sample_file.write_text(
            "这是 Filesystem MCP 示例文件。\n可以通过 MCP 工具读取和修改。\n",
            encoding="utf-8",
        )

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", str(DEMO_FOLDER)],
    )

    async with MCPTools(server_params=server_params) as mcp_tools:
        agent = Agent(
            name="FilesystemMCPAgent",
            model=create_agno_openai_model(
                OpenAIChat,
                default_model="deepseek-v4-flash",
            ),
            tools=[mcp_tools],
            instructions=[
                f"只在授权目录 {DEMO_FOLDER} 内操作文件。",
                "处理文件请求时使用 MCP 工具，并说明执行结果。",
                "覆盖或删除文件前，必须先向用户确认。",
            ],
            markdown=True,
        )

        print(f"Filesystem MCP 已连接，授权目录：{DEMO_FOLDER}")
        await agent.acli_app(
            user="你",
            emoji="📁",
            stream=True,
            markdown=True,
            exit_on=["exit", "quit", "退出"],
        )


if __name__ == "__main__":
    asyncio.run(main())
