import os
from pathlib import Path

import streamlit as st
from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.newspaper4k import Newspaper4kTools
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


def build_model() -> DeepSeek:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 DEEPSEEK_API_KEY。请在 .env 文件中添加该变量。")
    return DeepSeek(
        id=os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat")),
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )


def build_agents(model: DeepSeek, use_online_sources: bool) -> tuple[Agent, Agent, Agent]:
    research_tools = [DuckDuckGoTools()] if use_online_sources else []
    article_tools = (
        [Newspaper4kTools(enable_read_article=True, include_summary=True)]
        if use_online_sources
        else []
    )
    news_collector = Agent(
        name="新闻收集 Agent",
        role="检索创业、融资、技术和市场相关新闻",
        tools=research_tools,
        model=model,
        instructions=[
            "所有输出必须使用中文。",
            "围绕用户给定主题整理创业新闻、融资事件、产品发布、市场报告和监管变化。",
            "优先给出可核验来源链接。",
            "不要编造公司、融资金额、投资机构或市场数据。",
            "输出 8 到 12 条候选线索，每条包含标题、来源、链接和为什么值得关注。",
        ],
        markdown=True,
    )

    summary_writer = Agent(
        name="资料摘要 Agent",
        role="读取并总结新闻文章，提取可用于趋势判断的信息",
        tools=article_tools,
        model=model,
        instructions=[
            "所有输出必须使用中文。",
            "将收集到的文章线索整理成简洁摘要。",
            "每条摘要要包含：公司或赛道、事件、证据、潜在影响和不确定性。",
            "如果文章无法读取，保留原始链接并说明无法读取。",
        ],
        markdown=True,
    )

    trend_analyzer = Agent(
        name="趋势分析 Agent",
        role="从新闻摘要中识别创业趋势、市场空白和可行动机会",
        model=model,
        instructions=[
            "所有输出必须使用中文。",
            "从摘要中识别 3 到 5 个创业趋势。",
            "每个趋势必须包含：趋势名称、核心证据、为什么现在发生、潜在创业机会、商业模式、目标客户、风险和验证实验。",
            "输出必须包含一个表格，对比趋势、机会、目标客户、进入难度和风险。",
            "结尾给出 3 个最适合小团队启动的具体创业想法。",
            "明确区分公开事实和推断，不要编造数据。",
            "结尾必须提示：本内容仅用于技术学习与研究参考，不构成投资或创业建议。",
        ],
        markdown=True,
    )
    return news_collector, summary_writer, trend_analyzer


st.set_page_config(page_title="AI 创业趋势分析 Agent", layout="wide")
st.title("AI 创业趋势分析 Agent")
st.caption("基于 DeepSeek、DuckDuckGo 和新闻摘要工具，发现创业趋势、市场空白和可验证机会。")

with st.sidebar:
    st.header("配置")
    if os.getenv("DEEPSEEK_API_KEY"):
        st.success("已检测到 DEEPSEEK_API_KEY")
    else:
        st.warning("未检测到 DEEPSEEK_API_KEY，请先配置 .env")
    st.caption("支持在当前项目目录、finance-llm-agent-demos 根目录或工作区根目录放置 .env。")

default_topic = "AI Agent 在金融投研和企业自动化中的创业机会"
topic = st.text_input("关注的赛道或技术方向", value=default_topic)
region = st.selectbox("关注市场", ["全球", "中国", "美国", "东南亚", "欧洲"], index=0)
stage = st.selectbox("偏好阶段", ["早期机会", "成长期机会", "成熟市场再创新", "不限"], index=0)
use_online_sources = st.checkbox(
    "使用联网搜索和文章读取",
    value=False,
    help="联网模式依赖 DuckDuckGo 和新闻站点；默认关闭以保证本地 DeepSeek 流程可用。",
)

if st.button("生成趋势分析", use_container_width=True):
    if not topic.strip():
        st.warning("请先输入关注的赛道或技术方向。")
    else:
        with st.spinner("Agent 正在检索新闻、整理摘要并分析趋势..."):
            try:
                model = build_model()
                news_collector, summary_writer, trend_analyzer = build_agents(model, use_online_sources)

                research_prompt = (
                    f"主题：{topic}\n"
                    f"关注市场：{region}\n"
                    f"偏好阶段：{stage}\n"
                    "请整理与这个主题相关的创业、融资、产品、客户采用和监管变化线索。"
                    + ("请使用联网搜索获取近期公开资料。" if use_online_sources else "请明确标注无法实时核验的内容，不要虚构近期事件。")
                )
                news_response = news_collector.run(research_prompt, stream=False)
                articles = news_response.content if news_response else ""

                summary_response = summary_writer.run(
                    "请总结下面的创业趋势线索，并提取可用于趋势判断的证据：\n"
                    f"{articles}",
                    stream=False,
                )
                summaries = summary_response.content if summary_response else ""

                trend_response = trend_analyzer.run(
                    "请基于以下摘要生成创业趋势分析和机会建议：\n"
                    f"主题：{topic}\n关注市场：{region}\n偏好阶段：{stage}\n\n{summaries}",
                    stream=False,
                )
                analysis = trend_response.content if trend_response else "暂无分析结果。"

                tabs = st.tabs(["趋势分析", "新闻线索", "资料摘要"])
                with tabs[0]:
                    st.markdown(analysis)
                with tabs[1]:
                    st.markdown(articles or "暂无新闻线索。")
                with tabs[2]:
                    st.markdown(summaries or "暂无资料摘要。")
            except Exception as exc:
                st.error(f"分析失败：{exc}")
else:
    st.info("填写关注方向后点击“生成趋势分析”。")
