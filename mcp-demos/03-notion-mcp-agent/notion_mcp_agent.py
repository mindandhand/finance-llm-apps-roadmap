import asyncio
import json
import os
import sys
import uuid
from textwrap import dedent
from agno.agent import Agent 
from agno.models.openai import OpenAIChat
from agno.tools.mcp import MCPTools 
from agno.db.sqlite import SqliteDb
from mcp import StdioServerParameters
from dotenv import load_dotenv
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from llm_config import create_agno_openai_model, get_llm_api_key

# 加载环境变量
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_API_KEY")
LLM_API_KEY = get_llm_api_key()

async def main():
    print("\n========================================")
    print("      Notion MCP 终端 Agent")
    print("========================================\n")
    
    # 从环境变量读取配置
    notion_token = NOTION_TOKEN
    if not LLM_API_KEY:
        print("错误：缺少 DEEPSEEK_API_KEY、OPENAI_API_KEY 或 LLM_API_KEY。")
        return
    
    # 首先获取页面 ID
    page_id = None
    if len(sys.argv) > 1:
        # 优先使用命令行参数
        page_id = sys.argv[1]
        print(f"使用命令行提供的页面 ID：{page_id}")
    else:
        # 提示用户输入页面 ID
        print("请输入 Notion 页面 ID：")
        print("（可在页面 URL 中找到，例如：https://www.notion.so/workspace/Your-Page-1f5b8a8ba283...）")
        print("ID 位于最后一个短横线之后、查询参数之前")
        
        user_input = input("> ")
        
        # 输入为空时停止运行
        if user_input.strip():
            page_id = user_input.strip()
            print(f"使用页面 ID：{page_id}")
        else:
            print("❌ 错误：页面 ID 不能为空，请提供 Notion 页面 ID。")
            return
    
    # 为当前终端会话生成唯一的用户 ID 和会话 ID
    user_id = f"user_{uuid.uuid4().hex[:8]}"
    session_id = f"session_{uuid.uuid4().hex[:8]}"
    print(f"用户 ID：{user_id}")
    print(f"会话 ID：{session_id}")
    
    print("\n正在连接 Notion MCP Server……\n")
    
    # 配置 MCP 工具
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@notionhq/notion-mcp-server"],
        env={
            "OPENAPI_MCP_HEADERS": json.dumps(
                {"Authorization": f"Bearer {notion_token}", "Notion-Version": "2022-06-28"}
            )
        }
    )
    
    # 启动 MCP 工具会话
    async with MCPTools(server_params=server_params) as mcp_tools:
        print("已成功连接 Notion MCP Server！")
        db = SqliteDb(db_file="agno.db") # 使用 SQLite 保存记忆
        # 创建 Agent
        agent = Agent(
            name="NotionDocsAgent",
            model=create_agno_openai_model(OpenAIChat),
            tools=[mcp_tools],
            description="通过 MCP 查询和修改 Notion 文档的 Agent",
            instructions=dedent(f"""
                你是一名专业的 Notion 助手，负责帮助用户操作 Notion 页面。
                
                重要指令：
                1. 你可以通过 MCP 工具直接访问 Notion 文档，请充分使用这些工具。
                2. 除非用户明确提供其他 ID，否则所有操作必须使用页面 ID：{page_id}。
                3. 用户要求更新、读取或搜索页面时，必须调用合适的 MCP 工具。
                4. 主动建议用户可对 Notion 文档执行的操作。
                5. 修改页面后说明具体操作，并确认修改结果。
                6. 工具调用失败时，解释原因并给出替代方案。
                
                你可以帮助完成以下任务：
                - 读取页面内容
                - 搜索特定信息
                - 添加新内容或更新现有内容
                - 创建列表、表格及其他 Notion 块
                - 解释页面结构
                - 为指定块添加评论
                
                用户当前的页面 ID：{page_id}
            """),
            markdown=True,
            retries=3,
            db=db,
            enable_user_memories=True, # 启用 Agent 记忆
            add_history_to_context=True,  # 将对话历史加入上下文
            num_history_runs=5,  # 保留最近 5 轮交互
        )
        
        print("\n\nNotion MCP Agent 已就绪，可以开始操作 Notion 页面。\n")
        print("输入 exit、quit 或退出结束对话。\n")
        
        # 启动带记忆和会话管理的交互式命令行
        await agent.acli_app(
            user_id=user_id,
            session_id=session_id,
            user="你",
            emoji="🤖",
            stream=True,
            markdown=True,
            exit_on=["exit", "quit", "bye", "goodbye", "退出"]
        )

if __name__ == "__main__":
    asyncio.run(main())
