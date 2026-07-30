import os
from pathlib import Path

import streamlit as st
from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools
from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
WORKSPACE_DIR = REPO_DIR.parent
for env_path in (APP_DIR / ".env", REPO_DIR / ".env", WORKSPACE_DIR / ".env"):
    load_dotenv(env_path)


def model() -> DeepSeek:
    """创建统一的 DeepSeek 模型实例，供四类金融 Agent 复用。"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 DEEPSEEK_API_KEY。")
    return DeepSeek(
        id=os.getenv("DEEPSEEK_MODEL_ID", "deepseek-chat"),
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )


def route_task(query: str) -> str:
    """根据任务中的关键词选择最合适的金融工具 Agent。"""
    text = query.lower()
    if any(word in text for word in ["price", "stock", "股价", "行情", "估值", "pe", "市值"]):
        return "行情数据"
    if any(word in text for word in ["news", "公告", "新闻", "监管", "事件", "发布"]):
        return "公告新闻"
    if any(word in text for word in ["risk", "风险", "下跌", "不确定", "护城河"]):
        return "风险审查"
    return "综合报告"


st.set_page_config(page_title="金融工具路由 Agent", layout="wide")
st.title("金融工具路由 Agent")
st.caption("根据任务自动选择行情、新闻、风险或综合报告 Agent。")

query = st.text_area("输入任务", value="请分析 NVDA 的当前行情、最新新闻和主要风险，并给出中文报告。", height=120)

if st.button("路由并执行", use_container_width=True, type="primary"):
    with st.spinner("正在路由任务并调用对应工具 Agent..."):
        try:
            m = model()
            # 每个 Agent 只绑定完成自身任务所需的工具，减少无关工具调用。
            agents = {
                "行情数据": Agent(
                    name="行情数据 Agent",
                    model=m,
                    tools=[YFinanceTools(enable_stock_price=True, enable_company_info=True, enable_company_news=True)],
                    instructions=["所有输出必须使用中文。金融数据优先用表格展示。不要编造缺失数据。"],
                    markdown=True,
                ),
                "公告新闻": Agent(
                    name="公告新闻 Agent",
                    model=m,
                    tools=[DuckDuckGoTools()],
                    instructions=["所有输出必须使用中文。检索公开新闻、公告、监管和市场事件，并附来源链接。"],
                    markdown=True,
                ),
                "风险审查": Agent(
                    name="风险审查 Agent",
                    model=m,
                    tools=[DuckDuckGoTools()],
                    instructions=["所有输出必须使用中文。重点审查市场、财务、监管、竞争和执行风险。"],
                    markdown=True,
                ),
                "综合报告": Agent(
                    name="综合报告 Agent",
                    model=m,
                    tools=[DuckDuckGoTools(), YFinanceTools(enable_stock_price=True, enable_company_info=True)],
                    instructions=["所有输出必须使用中文。整合行情、新闻、风险和结论，并提示不构成投资建议。"],
                    markdown=True,
                ),
            }
            selected = route_task(query)
            st.info(f"路由结果：{selected}")
            response = agents[selected].run(query, stream=False)
            st.markdown(response.content if response else "暂无结果。")
        except Exception as exc:
            st.error(f"执行失败：{exc}")
else:
    st.info("输入任务后点击“路由并执行”。")
