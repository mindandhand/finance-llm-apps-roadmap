import asyncio
import os
import uuid
from textwrap import dedent
from agno.agent import Agent 
from agno.models.openai import OpenAIChat
from agno.tools.mcp import MultiMCPTools
from agno.db.sqlite import SqliteDb
from dotenv import load_dotenv
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))
from llm_config import create_agno_openai_model, get_llm_api_key, get_llm_model

# 加载环境变量
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
LLM_API_KEY = get_llm_api_key()
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

async def main():
    print("\n" + "="*60)
    print("           🚀 多 MCP 智能助手 🚀")
    print("="*60)
    print("🔗 已连接服务：GitHub • Perplexity • Calendar")
    print(f"💡 使用 OpenAI 兼容模型：{get_llm_model()}")
    print("="*60 + "\n")
    
    # 校验必需的环境变量
    required_vars = {
        "GITHUB_PERSONAL_ACCESS_TOKEN": GITHUB_TOKEN,
        "DEEPSEEK_API_KEY、OPENAI_API_KEY 或 LLM_API_KEY": LLM_API_KEY,
        "PERPLEXITY_API_KEY": PERPLEXITY_API_KEY,
    }
    
    missing_vars = [name for name, value in required_vars.items() if not value]
    if missing_vars:
        print("❌ 错误：缺少必需的环境变量：")
        for var in missing_vars:
            print(f"   • {var}")
        print("\n请检查 .env 文件，确保所有必需变量均已设置。")
        return
    
    # 为当前终端会话生成唯一的用户 ID 和会话 ID
    user_id = f"user_{uuid.uuid4().hex[:8]}"
    session_id = f"session_{uuid.uuid4().hex[:8]}"
    print(f"👤 用户 ID：{user_id}")
    print(f"🔑 会话 ID：{session_id}")
    
    print("\n🔌 正在初始化 MCP Server 连接……\n")
    
    # 为 MCP Server 设置环境变量
    env = {
        **os.environ,
        "GITHUB_PERSONAL_ACCESS_TOKEN": GITHUB_TOKEN,
        "PERPLEXITY_API_KEY": PERPLEXITY_API_KEY
    }

    mcp_servers = [
        "npx -y @modelcontextprotocol/server-github",
        "npx -y @chatmcp/server-perplexity-ask",
        "npx @gongrzhe/server-calendar-autoauth-mcp",
        "npx @gongrzhe/server-gmail-autoauth-mcp"
    ]
    
    # 配置用于保存记忆的数据库
    db = SqliteDb(db_file="tmp/multi_mcp_agent.db")
    
    # 启动 MCP 工具会话
    async with MultiMCPTools(mcp_servers, env=env) as mcp_tools:
        print("✅ 已成功连接所有 MCP Server！")
        
        # 使用完整指令创建 Agent
        agent = Agent(
            name="MultiMCPAgent",
            model=create_agno_openai_model(OpenAIChat),
            tools=[mcp_tools],
            description="集成 GitHub、Perplexity 和 Calendar 的高级 AI 助手",
            instructions=dedent(f"""
                你是一名集成多个平台的智能助手，目标是帮助用户提升数字工作空间中的效率。

                🎯 核心能力与指令：

                1. 🔧 工具使用
                   • 你可以通过 MCP 工具直接访问 GitHub、Notion、Perplexity 和 Calendar
                   • 处理这些平台相关请求时，必须调用合适的 MCP 工具
                   • 主动建议有效的工作流和自动化方案
                   • 复杂任务应组合使用多个工具调用

                2. 📋 GITHUB 能力
                   • 仓库管理：创建、克隆、派生和搜索仓库
                   • Issue 与 PR：创建、更新、审查、合并和评论
                   • 代码分析：搜索代码、审查差异并提出改进建议
                   • 分支管理：创建、切换和合并分支
                   • 协作：管理团队、审查和项目工作流

                4. 🔍 PERPLEXITY 研究
                   • 实时网页搜索和研究
                   • 当前事件和趋势信息
                   • 技术文档和学习资源
                   • 事实核查与验证

                5. 📅 日历集成
                   • 日程安排和管理
                   • 会议协调和空闲时间查询
                   • 截止日期跟踪和提醒

                6. 🎨 交互原则
                   • 保持自然、主动且有帮助的沟通方式
                   • 解释正在执行的操作及其原因
                   • 建议后续操作和优化方案
                   • 出错时提供可行的替代方案
                   • 必要时提出澄清问题
                   • 使用 Markdown 输出结构清晰的回答

                7. 🚀 高级工作流
                   • 跨平台自动化，例如 GitHub Issue → Notion 任务
                   • 研究驱动开发，例如 Perplexity → GitHub
                   • 项目管理集成
                   • 文档与知识共享

                会话信息：
                • 用户 ID：{user_id}
                • 会话 ID：{session_id}
                • 活跃服务：GitHub、Notion、Perplexity、Calendar

                请记住：不要只回答问题，还要主动设计工作流，帮助用户更高效地完成任务。
            """),
            markdown=True,
            debug_mode=True,
            retries=3,
            db=db,
            enable_user_memories=True,
            add_history_to_context=True,
            num_history_runs=10,  # 增加历史轮数以保留更多上下文
        )
        
        print("\n" + "🎉 " + "="*54 + " 🎉")
        print("   多 MCP 助手已就绪！")
        print("🎉 " + "="*54 + " 🎉\n")
        
        print("💡 可以尝试以下示例指令：")
        print("   • 显示我最近的 GitHub 仓库")
        print("   • 搜索最新的 AI 发展动态")
        print("   • 安排下周的会议")
        
        print("⚡ 输入 exit、quit、bye 或退出结束会话\n")
        
        # 启动交互式命令行会话
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
