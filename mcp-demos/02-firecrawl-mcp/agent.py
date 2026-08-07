"""DeepSeek + Agno + Firecrawl MCP 网页研究示例。"""

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


async def main():
    load_dotenv()
    if not get_llm_api_key():
        print("错误：请设置 DEEPSEEK_API_KEY、OPENAI_API_KEY 或 LLM_API_KEY。")
        return

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "firecrawl-mcp"],
    )

    async with MCPTools(
        server_params=server_params,
        include_tools=["firecrawl_scrape", "firecrawl_search"],
    ) as mcp_tools:
        agent = Agent(
            name="FirecrawlMCPAgent",
            model=create_agno_openai_model(
                OpenAIChat,
                default_model="deepseek-v4-pro",
            ),
            tools=[mcp_tools],
            instructions=[
                "只使用免费的 firecrawl_scrape 和 firecrawl_search 工具。",
                "根据任务选择单页抓取或网页搜索。",
                "输出中文结果，并保留来源链接。",
                "区分网页原文、工具返回数据和你的归纳判断。",
            ],
            markdown=True,
        )

        print("Firecrawl Keyless MCP 已连接。输入网页研究任务，输入 exit 退出。")
        await agent.acli_app(
            user="你",
            emoji="🔥",
            stream=True,
            markdown=True,
            exit_on=["exit", "quit", "退出"],
        )


if __name__ == "__main__":
    asyncio.run(main())
