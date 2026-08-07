"""DeepSeek + Agno + Firecrawl MCP 网页研究示例。"""

import asyncio
import os
import sys
from pathlib import Path

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.mcp import MCPTools
from dotenv import load_dotenv
from mcp import StdioServerParameters

sys.path.append(str(Path(__file__).resolve().parents[1]))
from llm_config import create_agno_openai_model, get_llm_api_key


async def main():
    load_dotenv()
    firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")

    missing = []
    if not get_llm_api_key():
        missing.append("DEEPSEEK_API_KEY、OPENAI_API_KEY 或 LLM_API_KEY")
    if not firecrawl_api_key:
        missing.append("FIRECRAWL_API_KEY")
    if missing:
        print(f"错误：缺少环境变量：{'；'.join(missing)}。")
        return

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "firecrawl-mcp"],
        env={**os.environ, "FIRECRAWL_API_KEY": firecrawl_api_key},
    )

    async with MCPTools(server_params=server_params) as mcp_tools:
        agent = Agent(
            name="FirecrawlMCPAgent",
            model=create_agno_openai_model(
                OpenAIChat,
                default_model="deepseek-v4-pro",
            ),
            tools=[mcp_tools],
            instructions=[
                "根据任务选择单页抓取、搜索、站点发现、批量抓取或深度研究工具。",
                "抓取多个页面前先说明范围，避免无边界爬取。",
                "输出中文结果，并保留来源链接。",
                "区分网页原文、工具返回数据和你的归纳判断。",
            ],
            markdown=True,
        )

        print("Firecrawl MCP 已连接。输入网页研究任务，输入 exit 退出。")
        await agent.acli_app(
            user="你",
            emoji="🔥",
            stream=True,
            markdown=True,
            exit_on=["exit", "quit", "退出"],
        )


if __name__ == "__main__":
    asyncio.run(main())
