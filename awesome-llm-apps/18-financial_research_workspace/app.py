import os
from pathlib import Path

import streamlit as st
from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
for env_path in (APP_DIR / ".env", APP_DIR.parent / ".env", APP_DIR.parent.parent / ".env"):
    load_dotenv(env_path)


def make_agent() -> Agent:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 DEEPSEEK_API_KEY。")
    return Agent(
        name="金融研究工作台 Agent",
        model=DeepSeek(
            id=os.getenv("DEEPSEEK_MODEL_ID", "deepseek-chat"),
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        ),
        tools=[DuckDuckGoTools(), YFinanceTools(enable_stock_price=True, enable_company_info=True, enable_company_news=True)],
        instructions=[
            "所有输出必须使用中文。",
            "按研究备忘录格式输出：结论、关键事实、数据表、风险、待核验问题、下一步。",
            "不要编造事实；缺失数据要明确标记。",
            "结尾提示不构成投资建议。",
        ],
        markdown=True,
    )


st.set_page_config(page_title="金融研究工作台", layout="wide")
st.title("金融研究工作台")
st.caption("把公司研究、行情、新闻和风险问题整理成投研备忘录。")

symbols = st.text_input("股票或公司", value="NVDA, MSFT")
focus = st.text_area("研究重点", value="增长驱动、估值风险、AI 资本开支和未来 12 个月风险。", height=120)

if st.button("生成研究备忘录", use_container_width=True):
    with st.spinner("正在整理研究备忘录..."):
        try:
            prompt = f"研究对象：{symbols}\n研究重点：{focus}\n请生成结构化投研备忘录。"
            result = make_agent().run(prompt, stream=False)
            st.markdown(result.content if result else "暂无结果。")
        except Exception as exc:
            st.error(f"生成失败：{exc}")
else:
    st.info("填写研究对象和重点后生成备忘录。")
