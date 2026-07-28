import os
from pathlib import Path

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.deepseek import DeepSeek
from agno.os import AgentOS
from agno.team import Team
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools
from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
SHARED_WORKSPACE_DIR = REPO_DIR.parent

for env_path in (
    APP_DIR / ".env",
    REPO_DIR / ".env",
    SHARED_WORKSPACE_DIR / ".env",
):
    load_dotenv(env_path)

model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat"))
base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")

model = DeepSeek(id=model_id, api_key=api_key, base_url=base_url)

db = SqliteDb(db_file=str(APP_DIR / "agents.db"))

web_agent = Agent(
    name="网页研究员",
    role="搜索网页信息并总结关键事实",
    model=model,
    tools=[DuckDuckGoTools()],
    db=db,
    add_history_to_context=True,
    markdown=True,
)

finance_agent = Agent(
    name="金融数据分析师",
    role="获取并分析股票行情、公司信息、新闻和分析师建议",
    model=model,
    tools=[
        YFinanceTools(
            enable_stock_price=True,
            enable_company_info=True,
            enable_analyst_recommendations=True,
            enable_company_news=True,
        )
    ],
    instructions=[
        "所有输出必须使用中文。",
        "金融和数值数据必须优先用表格展示。",
        "明确说明数据来源和不确定性。",
    ],
    db=db,
    add_history_to_context=True,
    markdown=True,
)

agent_team = Team(
    name="金融研究团队",
    model=model,
    members=[web_agent, finance_agent],
    instructions=[
        "所有输出必须使用中文。",
        "协调网页研究员和金融数据分析师完成公司研究与金融分析。",
        "最终回答应包含关键数据表、新闻或背景摘要、风险点和谨慎结论。",
        "不要编造事实；如果工具没有返回数据，要明确说明。",
        "结尾必须提示：本内容仅用于技术学习与研究参考，不构成投资建议。",
    ],
    debug_mode=os.getenv("AGNO_DEBUG", "").lower() in {"1", "true", "yes"},
    markdown=True,
)

agent_os = AgentOS(teams=[agent_team])
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="finance_agent_team:app", reload=False)
