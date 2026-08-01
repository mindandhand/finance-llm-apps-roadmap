from textwrap import dedent
import os
from pathlib import Path

from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from agno.run.agent import RunOutput
from agno.tools.duckduckgo import DuckDuckGoTools
from dotenv import load_dotenv
import streamlit as st


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
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")


st.title("AI 个人财务规划师")
st.caption("使用 DeepSeek 和 DuckDuckGo 研究，为你生成预算、储蓄和投资规划建议。")

deepseek_api_key = st.text_input("DeepSeek API Key", value=deepseek_api_key or "", type="password")

if deepseek_api_key:
    model = DeepSeek(id=model_id, api_key=deepseek_api_key, base_url=base_url)
    researcher = Agent(
        name="财务研究员",
        role="根据用户偏好搜索财务建议、投资机会和储蓄策略",
        model=model,
        description=dedent(
            """\
        你是一名专业的中文财务研究员。根据用户的财务目标和当前财务状况，
        生成相关搜索词，检索财务建议、投资机会和储蓄策略。
        分析搜索结果后，返回最相关、最可执行的信息。
        所有输出必须使用中文。
        """
        ),
        instructions=[
            "根据用户的财务目标和当前财务状况，先生成 3 个相关搜索词。",
            "对每个搜索词使用网页搜索，并分析搜索结果。",
            "从全部搜索结果中提取最符合用户偏好的 10 条关键信息。",
            "输出必须使用中文，结构要清晰，并尽量标注信息来源或来源类型。",
            "不要编造事实；不确定的信息要明确说明。",
        ],
        tools=[DuckDuckGoTools()],
        add_datetime_to_context=True,
    )
    planner = Agent(
        name="财务规划师",
        role="根据用户偏好和研究结果生成个性化财务规划",
        model=model,
        description=dedent(
            """\
        你是一名资深中文财务规划师。根据用户的财务目标、当前财务状况和研究结果，
        生成符合用户需求的个性化财务规划。
        所有输出必须使用中文。
        """
        ),
        instructions=[
            "根据用户的财务目标、当前财务状况和研究结果，生成个性化财务规划。",
            "输出必须使用中文。",
            "计划应包含预算建议、储蓄策略、债务或现金流建议、投资方向和后续行动清单。",
            "金融和数值信息优先使用表格展示。",
            "给出平衡、审慎的分析；能引用研究结果时要说明依据。",
            "不要编造事实，不要给出确定收益承诺。",
            "结尾必须包含风险提示：本内容仅用于技术学习与规划参考，不构成投资、税务、保险或法律建议。",
        ],
        add_datetime_to_context=True,
    )

    default_goals = "三年内攒够 30 万元首付，同时保留 6 个月应急金。"
    default_situation = "月收入 25000 元，房租 6000 元，日常支出 8000 元，已有存款 120000 元，没有信用卡债务。"

    financial_goals = st.text_input("财务目标", value=default_goals)
    current_situation = st.text_area("当前财务状况", value=default_situation, height=120)

    if st.button("生成财务规划"):
        with st.spinner("正在研究并生成规划..."):
            research: RunOutput = researcher.run(
                f"财务目标：{financial_goals}\n当前财务状况：{current_situation}\n请用中文输出研究结果。",
                stream=False,
            )
            response: RunOutput = planner.run(
                dedent(
                    f"""\
                    财务目标：{financial_goals}
                    当前财务状况：{current_situation}
                    研究结果：
                    {research.content}

                    请基于以上信息生成中文财务规划。
                    """
                ),
                stream=False,
            )
            st.write(response.content)
else:
    st.info("请先填写 DeepSeek API Key。")
