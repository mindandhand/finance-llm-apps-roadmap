import re
import asyncio
from textwrap import dedent
from agno.agent import Agent
from agno.run.agent import RunOutput
from agno.tools.mcp import MultiMCPTools
from agno.tools.googlesearch import GoogleSearchTools
from agno.models.openai import OpenAIChat
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import streamlit as st
from datetime import date
import os
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))
from llm_config import create_agno_openai_model, get_llm_model

def generate_ics_content(plan_text: str, start_date: datetime = None) -> bytes:
    """根据旅行计划文本生成 ICS 日历文件。

    参数：
        plan_text: 旅行计划文本
        start_date: 可选的行程开始日期，默认为今天

    返回：
        bytes: ICS 文件的字节内容
    """
    cal = Calendar()
    cal.add('prodid','-//AI Travel Planner//github.com//')
    cal.add('version', '2.0')

    if start_date is None:
        start_date = datetime.today()

    # 按天拆分计划
    day_pattern = re.compile(r'Day (\d+)[:\s]+(.*?)(?=Day \d+|$)', re.DOTALL)
    days = day_pattern.findall(plan_text)

    if not days:  # 未找到按天标题时，将全部内容创建为单个全天事件
        event = Event()
        event.add('summary', "旅行计划")
        event.add('description', plan_text)
        event.add('dtstart', start_date.date())
        event.add('dtend', start_date.date())
        event.add("dtstamp", datetime.now())
        cal.add_component(event)
    else:
        # 逐天创建事件
        for day_num, day_content in days:
            day_num = int(day_num)
            current_date = start_date + timedelta(days=day_num - 1)

            # 为当天创建单个事件
            event = Event()
            event.add('summary', f"第 {day_num} 天行程")
            event.add('description', day_content.strip())

            # 设置为全天事件
            event.add('dtstart', current_date.date())
            event.add('dtend', current_date.date())
            event.add("dtstamp", datetime.now())
            cal.add_component(event)

    return cal.to_ical()

async def run_mcp_travel_planner(destination: str, num_days: int, preferences: str, budget: int, llm_key: str, google_maps_key: str):
    """运行可访问实时数据的 MCP 旅行规划 Agent。"""

    try:
        # 设置 Google Maps API Key 环境变量
        os.environ["GOOGLE_MAPS_API_KEY"] = google_maps_key
        os.environ["DEEPSEEK_API_KEY"] = llm_key

        # 使用 Airbnb MCP 初始化工具
        mcp_tools = MultiMCPTools(
            [
            "npx -y @openbnb/mcp-server-airbnb --ignore-robots-txt",
            "npx @gongrzhe/server-travelplanner-mcp",
            ],      
            env={
                "GOOGLE_MAPS_API_KEY": google_maps_key,
            },
            timeout_seconds=60,
        )   

        # 连接 Airbnb MCP Server
        await mcp_tools.connect()


        travel_planner = Agent(
            name="旅行规划师",
            role="使用 Airbnb、Google Maps 和 Google Search 创建旅行计划",
            model=create_agno_openai_model(OpenAIChat),
            description=dedent(
                """\
                你是一名专业旅行顾问，无需反复提问，直接创建细致完整的旅行计划。

                你可以使用：
                🏨 Airbnb 的实时房源、可订状态和价格
                🗺️ Google Maps MCP 提供的位置、路线、距离计算和本地导航服务
                🔍 网页搜索获取最新信息、评价和旅行动态

                不要要求用户补充信息，应立即生成完整详细的行程。
                充分使用 Google Maps MCP 计算地点间距离并提供准确的通行时间。
                信息不足时，结合可用工具和合理判断补全内容。
                """
            ),
            instructions=[
                "重要：不要提问或要求澄清，直接生成完整行程",
                "使用所有可用工具充分研究目的地并收集最新信息",
                "通过 Airbnb MCP 查找预算内且具有真实价格和可订状态的住宿",
                "按天创建详细行程，列出具体活动、地点、准确时间和距离",
                "充分使用 Google Maps MCP 计算所有地点间距离和通行时间",
                "使用 Google Maps MCP 提供详细交通方案和导航提示",
                "列出餐厅名称、地址、价格范围及其与住宿地点的距离",
                "查询当前天气和季节因素，并给出具体行李建议",
                "准确估算旅行各项费用，确保建议符合预算",
                "列出景点开放时间、票价、最佳游览时间及其与住宿地点的距离",
                "补充当地交通费用、货币兑换、安全提示和文化习俗",
                "用清晰章节组织行程，列出各活动时间并预留缓冲时间",
                "主动使用所有可用工具，无需请求许可",
                "一次性生成完整详细的行程，不提出后续问题"
            ],
            tools=[mcp_tools, GoogleSearchTools()],
            add_datetime_to_context=True,
            markdown=True,
            debug_mode=False,
        )

        # 创建旅行规划 Prompt
        prompt = f"""
        立即为以下信息创建非常详细且完整的旅行计划：

        **目的地：** {destination}
        **时长：** {num_days} 天
        **总预算：** {budget} 美元
        **偏好：** {preferences}

        不要提问，立即使用所有可用工具生成完整详细的行程。

        **关键要求：**
        - 使用 Google Maps MCP 计算所有地点间的距离和通行时间
        - 提供每个地点、餐厅和景点的具体地址
        - 给出每项活动的详细时间，并在地点之间预留缓冲时间
        - 准确计算各地点之间的交通费用
        - 提供所有景点的开放时间、票价和最佳游览时间
        - 提供详细天气信息和具体行李建议

        **输出格式：**
        1. **旅行概览**：摘要、总费用明细和详细天气预报
        2. **住宿**：3 个 Airbnb 选项，包含真实价格、地址、设施及与市中心的距离
        3. **交通概览**：详细交通方式、费用和建议
        4. **逐日行程**：标题使用 `Day 1`、`Day 2` 等格式，并包含：
           - 每项活动的具体开始和结束时间
           - 地点间准确距离和通行时间（使用 Google Maps MCP）
           - 各地点的详细说明和地址
           - 开放时间、票价和最佳游览时间
           - 各项活动和交通的预估费用
           - 应对意外延误的缓冲时间
        5. **餐饮计划**：餐厅名称、地址、价格范围、菜系及与住宿地点的距离
        6. **详细实用信息**：
           - 天气预报和着装建议
           - 汇率和兑换费用
           - 当地交通方式和费用
           - 安全信息和紧急联系方式
           - 文化习俗和礼仪
           - 通信方案（SIM 卡、WiFi 等）
           - 健康和医疗注意事项
           - 购物和纪念品建议

        使用 Airbnb MCP 获取真实住宿数据，使用 Google Maps MCP 完成所有距离计算和位置服务，
        并通过网页搜索获取最新信息。信息缺失时作出合理假设，一次性生成完整详细的行程，不要求澄清。
        """

        response: RunOutput = await travel_planner.arun(prompt)
        return response.content

    finally:
        await mcp_tools.close()

def run_travel_planner(destination: str, num_days: int, preferences: str, budget: int, llm_key: str, google_maps_key: str):
    """异步 MCP 旅行规划器的同步包装函数。"""
    return asyncio.run(run_mcp_travel_planner(destination, num_days, preferences, budget, llm_key, google_maps_key))
    
# -------------------- Streamlit 应用 --------------------
    
# 配置页面
st.set_page_config(
    page_title="MCP AI 旅行规划师",
    page_icon="✈️",
    layout="wide"
)

# 初始化会话状态
if 'itinerary' not in st.session_state:
    st.session_state.itinerary = None

# 标题和说明
st.title("✈️ MCP AI 旅行规划师")
st.caption("通过 MCP Server 获取实时数据，使用 AI 规划下一次旅行")

# API Key 侧边栏
with st.sidebar:
    st.header("🔑 API Key 配置")
    st.warning("⚠️ 以下服务需要 API Key：")

    llm_api_key = st.text_input("大语言模型 API Key", type="password", help="旅行规划使用的 DeepSeek/OpenAI 兼容密钥")
    st.caption(f"模型：{get_llm_model()}")
    google_maps_key = st.text_input("Google Maps API Key", type="password", help="位置服务必需")

    # 检查是否已提供 API Key
    api_keys_provided = llm_api_key and google_maps_key

    if api_keys_provided:
        st.success("✅ 所有 API Key 已配置！")
    else:
        st.warning("⚠️ 请输入两个 API Key 后再使用旅行规划师。")
        st.info("""
        **必需的 API Key：**
        - **大语言模型 API Key**：DeepSeek/OpenAI 兼容服务商密钥
        - **Google Maps API Key**：https://console.cloud.google.com/apis/credentials（用于位置服务）
        """)

# 主体内容，仅在已提供 API Key 时显示
if api_keys_provided:
    # 主要输入区域
    st.header("🌍 旅行详情")

    col1, col2 = st.columns(2)

    with col1:
        destination = st.text_input("目的地", placeholder="例如：巴黎、东京、纽约")
        num_days = st.number_input("旅行天数", min_value=1, max_value=30, value=7)

    with col2:
        budget = st.number_input("预算（美元）", min_value=100, max_value=10000, step=100, value=2000)
        start_date = st.date_input("开始日期", min_value=date.today(), value=date.today())

    # 旅行偏好区域
    st.subheader("🎯 旅行偏好")
    preferences_input = st.text_area(
        "描述你的旅行偏好",
        placeholder="例如：探险活动、文化景点、美食、休闲、夜生活……",
        height=100
    )

    # 快速偏好选项
    quick_prefs = st.multiselect(
        "快速偏好（可选）",
        ["探险", "休闲", "观光", "文化体验", "海滩", "山地", "奢华",
         "经济实惠", "美食", "购物", "夜生活", "亲子友好"],
        help="可选择多个偏好，或在上方输入详细描述"
    )

    # 合并旅行偏好
    all_preferences = []
    if preferences_input:
        all_preferences.append(preferences_input)
    if quick_prefs:
        all_preferences.extend(quick_prefs)

    preferences = "、".join(all_preferences) if all_preferences else "常规观光"

    # 生成按钮
    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🎯 生成行程", type="primary"):
            if not destination:
                st.error("请输入目的地。")
            elif not preferences:
                st.warning("请描述旅行偏好或选择快速偏好。")
            else:
                tools_message = "🏨 正在连接 Airbnb MCP"
                if google_maps_key:
                    tools_message += " 和 Google Maps MCP"
                tools_message += "，正在创建行程……"

                with st.spinner(tools_message):
                    try:
                        # 根据开始日期生成行程
                        response = run_travel_planner(
                            destination=destination,
                            num_days=num_days,
                            preferences=preferences,
                            budget=budget,
                            llm_key=llm_api_key,
                            google_maps_key=google_maps_key or ""
                        )

                        # 将回答保存到会话状态
                        st.session_state.itinerary = response

                        # 显示 MCP 连接状态
                        if "Airbnb" in response and ("listing" in response.lower() or "accommodation" in response.lower()):
                            st.success("✅ 已使用 Airbnb 数据生成旅行计划！")
                            st.info("🏨 住宿建议使用了真实 Airbnb 房源")
                        else:
                            st.success("✅ 旅行计划已生成！")
                            st.info("📝 住宿建议使用了通用知识，Airbnb MCP 可能连接失败")

                    except Exception as e:
                        st.error(f"错误：{str(e)}")
                        st.info("请重试或检查网络连接。")

    with col2:
        if st.session_state.itinerary:
            # 生成 ICS 文件
            ics_content = generate_ics_content(st.session_state.itinerary, datetime.combine(start_date, datetime.min.time()))

            # 提供文件下载
            st.download_button(
                label="📅 下载日历文件",
                data=ics_content,
                file_name="travel_itinerary.ics",
                mime="text/calendar"
            )

    # 显示旅行计划
    if st.session_state.itinerary:
        st.header("📋 你的旅行计划")
        st.markdown(st.session_state.itinerary)
