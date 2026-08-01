import os
from pathlib import Path

import streamlit as st
from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from agno.tools.duckduckgo import DuckDuckGoTools
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
for env_path in (APP_DIR / ".env", APP_DIR.parent / ".env", APP_DIR.parent.parent / ".env"):
    load_dotenv(env_path)


def agent() -> Agent:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 DEEPSEEK_API_KEY。")
    return Agent(
        name="市场事件 Radar Agent",
        model=DeepSeek(id=os.getenv("DEEPSEEK_MODEL_ID", "deepseek-chat"), api_key=api_key, base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")),
        tools=[DuckDuckGoTools()],
        instructions=[
            "所有输出必须使用中文。",
            "检索公司公告、财报、监管、产品、融资、评级和重大新闻。",
            "按影响等级高/中/低分类，并说明来源和原因。",
            "默认 dry-run，不发送邮件或 webhook。",
        ],
        markdown=True,
    )


st.set_page_config(page_title="市场事件 Radar Agent", layout="wide")
st.title("市场事件 Radar Agent")
watchlist = st.text_area("关注列表", value="AAPL\nMSFT\nNVDA\nTSLA", height=160)
window = st.selectbox("时间范围", ["最近 24 小时", "最近 7 天", "最近 30 天"], index=1)

if st.button("生成事件摘要", use_container_width=True):
    with st.spinner("正在检索和分级市场事件..."):
        try:
            prompt = f"关注列表：\n{watchlist}\n时间范围：{window}\n请生成市场事件 Radar 摘要。"
            result = agent().run(prompt, stream=False)
            st.markdown(result.content if result else "暂无结果。")
        except Exception as exc:
            st.error(f"生成失败：{exc}")
else:
    st.info("填写关注列表后生成事件摘要。")
