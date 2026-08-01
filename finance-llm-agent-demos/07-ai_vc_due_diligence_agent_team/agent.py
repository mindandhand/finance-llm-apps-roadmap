"""AI VC 尽职调查 Agent 团队。"""

from __future__ import annotations

import os
from pathlib import Path

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.deepseek import DeepSeek
from agno.os import AgentOS
from agno.team import Team
from agno.tools.duckduckgo import DuckDuckGoTools
from dotenv import load_dotenv

try:
    from tools import generate_financial_chart, generate_html_report, generate_infographic
except ImportError:
    from .tools import generate_financial_chart, generate_html_report, generate_infographic


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


company_research_agent = Agent(
    name="公司研究员",
    role="检索并整理创业公司基本信息、团队、融资、产品和近期动态",
    model=model,
    tools=[DuckDuckGoTools()],
    instructions=[
        "所有输出必须使用中文。",
        "优先检索公司官网、公开新闻、融资数据库页面、创始人访谈和产品发布信息。",
        "区分已确认事实、公开传闻和基于同类公司的估计。",
        "如果公开资料有限，要明确说明缺口，不要编造融资金额、客户或收入。",
        "输出应包含：公司概况、创始团队、产品技术、融资历史、牵引力、近期动态、信息缺口。",
    ],
    db=db,
    add_history_to_context=True,
    markdown=True,
)

market_analysis_agent = Agent(
    name="市场分析师",
    role="分析市场规模、竞争格局、定位和行业趋势",
    model=model,
    tools=[DuckDuckGoTools()],
    instructions=[
        "所有输出必须使用中文。",
        "基于公司研究结果和网页检索，分析 TAM/SAM、增长率、竞争对手和差异化。",
        "涉及市场规模时必须说明来源、年份和口径；无法确认时使用区间并标注为估计。",
        "输出应包含：市场机会、主要竞品、定位差异、趋势驱动、监管或平台风险。",
    ],
    db=db,
    add_history_to_context=True,
    markdown=True,
)

financial_modeling_agent = Agent(
    name="财务建模师",
    role="建立收入情景预测并调用本地图表工具",
    model=model,
    tools=[generate_financial_chart],
    instructions=[
        "所有输出必须使用中文。",
        "根据公司阶段估计当前 ARR，并清楚标注估计依据。",
        "给出保守、基准、乐观三种 5 年收入增长情景。",
        "调用 generate_financial_chart 生成收入预测图。",
        "输出应包含：当前 ARR 假设、增长率假设、退出倍数、MOIC/IRR 的粗略估算和关键敏感性。",
    ],
    db=db,
    add_history_to_context=True,
    markdown=True,
)

risk_assessment_agent = Agent(
    name="风险分析师",
    role="评估市场、执行、财务、监管和退出风险",
    model=model,
    instructions=[
        "所有输出必须使用中文。",
        "从市场风险、执行风险、财务风险、监管风险、退出风险五类评估。",
        "每个风险必须包含严重程度、证据或依据、缓释方式。",
        "给出 1 到 10 的总体风险评分，10 表示风险最高。",
        "列出最可能导致投资失败的前三个风险。",
    ],
    db=db,
    add_history_to_context=True,
    markdown=True,
)

memo_agent = Agent(
    name="投资备忘录撰写员",
    role="综合前序研究，输出投资备忘录，并生成本地报告文件",
    model=model,
    tools=[generate_html_report, generate_infographic],
    instructions=[
        "所有输出必须使用中文。",
        "综合公司研究、市场分析、财务建模和风险评估，写一份 VC 投资备忘录。",
        "备忘录结构必须包含：执行摘要、公司概况、融资与估值、市场机会、财务分析、风险分析、投资逻辑、建议和下一步尽调清单。",
        "投资建议只能使用：强烈建议跟进、建议跟进、观察、放弃。",
        "明确区分公开确认信息和估计信息。",
        "调用 generate_html_report 保存 HTML 报告。",
        "调用 generate_infographic 保存 SVG 摘要卡片。",
        "结尾必须提示：本内容仅用于技术学习与研究参考，不构成投资建议。",
    ],
    db=db,
    add_history_to_context=True,
    markdown=True,
)

due_diligence_team = Team(
    name="VC 尽职调查团队",
    model=model,
    members=[
        company_research_agent,
        market_analysis_agent,
        financial_modeling_agent,
        risk_assessment_agent,
        memo_agent,
    ],
    instructions=[
        "所有输出必须使用中文。",
        "你是 VC 尽调团队负责人，负责协调成员完成创业公司投资分析。",
        "当用户给出公司名、官网或融资轮次时，依次完成公司研究、市场分析、财务建模、风险评估和投资备忘录。",
        "需要生成图表、HTML 报告和 SVG 摘要时，委托对应 Agent 调用本地工具。",
        "不要编造事实；无法确认的数据必须标记为估计或缺失。",
        "最终回答包含：结论、关键依据、主要风险、已生成文件路径、下一步尽调建议。",
        "结尾必须提示：本内容仅用于技术学习与研究参考，不构成投资建议。",
    ],
    db=db,
    add_history_to_context=True,
    debug_mode=os.getenv("AGNO_DEBUG", "").lower() in {"1", "true", "yes"},
    markdown=True,
)

root_agent = due_diligence_team

agent_os = AgentOS(teams=[due_diligence_team])
app = agent_os.get_app()


if __name__ == "__main__":
    agent_os.serve(app="agent:app", reload=False)
