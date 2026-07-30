import asyncio
import os
import streamlit as st
from textwrap import dedent
from dotenv import load_dotenv

APP_DIR = os.path.dirname(os.path.abspath(__file__))
for env_path in (
    os.path.join(APP_DIR, ".env"),
    os.path.join(os.path.dirname(APP_DIR), ".env"),
    os.path.join(os.path.dirname(os.path.dirname(APP_DIR)), ".env"),
):
    load_dotenv(env_path)

# mcp-agent 的 OpenAI workflow 会读取 OPENAI_API_KEY。
# 项目统一使用 DEEPSEEK_API_KEY，因此只在未设置 OPENAI_API_KEY 时做兼容映射。
if os.getenv("DEEPSEEK_API_KEY") and not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]

from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams

# Page config
st.set_page_config(page_title="浏览器 MCP Agent", page_icon="🌐", layout="wide")

# Title and description
st.markdown("<h1 class='main-header'>🌐 浏览器 MCP Agent</h1>", unsafe_allow_html=True)
st.markdown("使用自然语言控制浏览器访问网页、点击元素、滚动页面并提取内容。")

# Setup sidebar with example commands
with st.sidebar:
    st.markdown("### 示例指令")
    
    st.markdown("**导航**")
    st.markdown("- 打开 github.com/Shubhamsaboo/awesome-llm-apps")
    
    st.markdown("**交互**")
    st.markdown("- 点击页面中的 mcp_ai_agents")
    st.markdown("- 向下滚动查看更多内容")
    
    st.markdown("**多步骤任务**")
    st.markdown("- 打开 github.com/Shubhamsaboo/awesome-llm-apps，向下滚动并汇报页面信息")
    st.markdown("- 向下滚动并总结 GitHub README")
    
    st.markdown("---")
    st.caption("Agent 通过 Playwright 控制真实浏览器。")

# Query input
query = st.text_area(
    "浏览器指令",
    placeholder="例如：打开一个网页，向下滚动，提取页面主要内容并总结。",
)

# Initialize app and agent
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.mcp_app = MCPApp(name="streamlit_mcp_agent")
    st.session_state.mcp_context = None
    st.session_state.mcp_agent_app = None
    st.session_state.browser_agent = None
    st.session_state.llm = None
    st.session_state.loop = asyncio.new_event_loop()
    asyncio.set_event_loop(st.session_state.loop)
    st.session_state.is_processing = False

# Setup function that runs only once
async def setup_agent():
    if not st.session_state.initialized:
        try:
            # Create context manager and store it in session state
            st.session_state.mcp_context = st.session_state.mcp_app.run()
            st.session_state.mcp_agent_app = await st.session_state.mcp_context.__aenter__()
            
            # Create and initialize agent
            st.session_state.browser_agent = Agent(
                name="browser",
                instruction="""You are a helpful web browsing assistant that can interact with websites using playwright.
                    - Navigate to websites and perform browser actions (click, scroll, type)
                    - Extract information from web pages 
                    - Take screenshots of page elements when useful
                    - Provide concise summaries of web content using markdown
                    - Follow multi-step browsing sequences to complete tasks
                    
                Respond back with a status update on completing the commands.""",
                server_names=["playwright"],
            )
            
            # Initialize agent and attach LLM
            await st.session_state.browser_agent.initialize()
            st.session_state.llm = await st.session_state.browser_agent.attach_llm(OpenAIAugmentedLLM)
            
            # List tools once
            logger = st.session_state.mcp_agent_app.logger
            tools = await st.session_state.browser_agent.list_tools()
            logger.info("Tools available:", data=tools)
            
            # Mark as initialized
            st.session_state.initialized = True
        except Exception as e:
            return f"Error during initialization: {str(e)}"
    return None

# Main function to run agent
async def run_mcp_agent(message):
    if not os.getenv("DEEPSEEK_API_KEY") and not os.path.exists(
        os.path.join(os.path.dirname(__file__), "mcp_agent.secrets.yaml")
    ):
        return (
            "错误：未找到 DeepSeek API Key。请配置 DEEPSEEK_API_KEY，"
            "或从 mcp_agent.secrets.yaml.example 创建未跟踪的密钥文件。"
        )

    try:
        # Make sure agent is initialized
        error = await setup_agent()
        if error:
            return error
        
        # Generate response without recreating agents
        # Switch use_history to False to reduce the passed context
        result = await st.session_state.llm.generate_str(
            message=message, 
            request_params=RequestParams(use_history=True, maxTokens=10000)
            )
        return result
    except Exception as e:
        return f"错误：{str(e)}"

# Defaults
if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False
if 'last_result' not in st.session_state:
    st.session_state.last_result = None

def start_run():
    st.session_state.is_processing = True

# Button (use a callback so the click just flips state)
st.button(
    "🚀 执行指令",
    type="primary",
    use_container_width=True,
    disabled=st.session_state.is_processing,
    on_click=start_run,
)

# If we’re in a processing run, do the work now
if st.session_state.is_processing:
    with st.spinner("正在执行浏览器任务..."):
        result = st.session_state.loop.run_until_complete(run_mcp_agent(query))
    # persist result across the next rerun
    st.session_state.last_result = result
    # unlock the button and refresh UI
    st.session_state.is_processing = False
    st.rerun()

# Render the most recent result (after the rerun)
if st.session_state.last_result:
    st.markdown("### 执行结果")
    st.markdown(st.session_state.last_result)
else:
    # (your existing help text here)
    pass

# Display help text for first-time users
if 'result' not in locals():
    st.markdown(
        """<div style='padding: 20px; background-color: #f0f2f6; border-radius: 10px;'>
        <h4>使用步骤</h4>
        <ol>
            <li>配置 DEEPSEEK_API_KEY 或 mcp_agent.secrets.yaml</li>
            <li>输入浏览器导航和交互指令</li>
            <li>点击“执行指令”查看结果</li>
        </ol>
        <p><strong>支持能力：</strong></p>
        <ul>
            <li>使用 Playwright 打开网页</li>
            <li>点击元素、滚动页面并输入文本</li>
            <li>截取指定页面区域</li>
            <li>提取网页信息</li>
            <li>执行多步骤浏览任务</li>
        </ul>
        </div>""", 
        unsafe_allow_html=True
    )

# Footer
st.markdown("---")
st.write("基于 Streamlit、Playwright 和 [MCP-Agent](https://www.github.com/lastmile-ai/mcp-agent) 构建")
