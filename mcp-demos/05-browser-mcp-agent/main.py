import asyncio
import os
import streamlit as st
from textwrap import dedent

from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams

# 页面配置
st.set_page_config(page_title="浏览器 MCP Agent", page_icon="🌐", layout="wide")

# 标题和说明
st.markdown("<h1 class='main-header'>🌐 浏览器 MCP Agent</h1>", unsafe_allow_html=True)
st.markdown("使用浏览器 Agent 访问网页并与页面交互")

# 在侧边栏显示示例指令
with st.sidebar:
    st.markdown("### 示例指令")
    
    st.markdown("**导航操作**")
    st.markdown("- 打开 github.com/Shubhamsaboo/awesome-llm-apps")
    
    st.markdown("**交互操作**")
    st.markdown("- 点击 mcp_ai_agents")
    st.markdown("- 向下滚动查看更多内容")
    
    st.markdown("**多步骤任务**")
    st.markdown("- 打开 github.com/Shubhamsaboo/awesome-llm-apps，向下滚动并报告详细信息")
    st.markdown("- 向下滚动并总结 GitHub README")
    
    st.markdown("---")
    st.caption("说明：Agent 使用 Playwright 控制真实浏览器。")

# 指令输入框
query = st.text_area("你的指令",
                   placeholder="例如：打开一个网页并提取其中的主要信息")

# 初始化应用和 Agent
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

# 仅执行一次的 Agent 初始化函数
async def setup_agent():
    if not st.session_state.initialized:
        try:
            # 创建上下文管理器并保存到会话状态
            st.session_state.mcp_context = st.session_state.mcp_app.run()
            st.session_state.mcp_agent_app = await st.session_state.mcp_context.__aenter__()
            
            # 创建并初始化 Agent
            st.session_state.browser_agent = Agent(
                name="browser",
                instruction="""你是一名网页浏览助手，可以使用 Playwright 与网页交互。
                    - 打开网页并执行点击、滚动和输入等浏览器操作
                    - 提取网页中的信息
                    - 必要时截取页面元素的截图
                    - 使用 Markdown 简洁总结网页内容
                    - 按顺序执行多步骤浏览任务
                    
                完成指令后，说明执行结果和当前状态。""",
                server_names=["playwright"],
            )
            
            # 初始化 Agent 并连接大语言模型
            await st.session_state.browser_agent.initialize()
            st.session_state.llm = await st.session_state.browser_agent.attach_llm(OpenAIAugmentedLLM)
            
            # 获取一次可用工具列表
            logger = st.session_state.mcp_agent_app.logger
            tools = await st.session_state.browser_agent.list_tools()
            logger.info("可用工具：", data=tools)
            
            # 标记为已初始化
            st.session_state.initialized = True
        except Exception as e:
            return f"初始化失败：{str(e)}"
    return None

# 运行 Agent 的主函数
async def run_mcp_agent(message):
    # 凭证来自 mcp_agent.secrets.yaml（api_key），模型配置来自
    # mcp_agent.config.yaml（base_url、default_model）。OpenAI 及兼容
    # OpenAI API 的服务（如 Ollama）均使用同一个 `openai:` 配置段，详见 README。
    if not os.getenv("OPENAI_API_KEY") and not os.path.exists(
        os.path.join(os.path.dirname(__file__), "mcp_agent.secrets.yaml")
    ):
        return (
            "错误：未找到大语言模型凭证。请设置环境变量 OPENAI_API_KEY，"
            "或根据示例创建 mcp_agent.secrets.yaml。"
        )

    try:
        # 确保 Agent 已初始化
        error = await setup_agent()
        if error:
            return error
        
        # 复用现有 Agent 生成回答；如需减少上下文，可将 use_history 改为 False
        result = await st.session_state.llm.generate_str(
            message=message, 
            request_params=RequestParams(use_history=True, maxTokens=10000)
            )
        return result
    except Exception as e:
        return f"错误：{str(e)}"

# 默认状态
if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False
if 'last_result' not in st.session_state:
    st.session_state.last_result = None

def start_run():
    st.session_state.is_processing = True

# 按钮回调只负责切换处理状态
st.button(
    "🚀 运行指令",
    type="primary",
    use_container_width=True,
    disabled=st.session_state.is_processing,
    on_click=start_run,
)

# 处于处理状态时执行任务
if st.session_state.is_processing:
    with st.spinner("正在处理你的指令……"):
        result = st.session_state.loop.run_until_complete(run_mcp_agent(query))
    # 保存结果，供下次页面重载后显示
    st.session_state.last_result = result
    # 解锁按钮并刷新界面
    st.session_state.is_processing = False
    st.rerun()

# 页面重载后显示最近一次结果
if st.session_state.last_result:
    st.markdown("### 执行结果")
    st.markdown(st.session_state.last_result)
else:
    # 暂无执行结果
    pass

# 为首次使用者显示帮助信息
if 'result' not in locals():
    st.markdown(
        """<div style='padding: 20px; background-color: #f0f2f6; border-radius: 10px;'>
        <h4>使用方法：</h4>
        <ol>
            <li>在 mcp_agent.secrets.yaml 中配置模型 API 密钥</li>
            <li>输入需要 Agent 执行的网页浏览或交互指令</li>
            <li>点击“运行指令”查看结果</li>
        </ol>
        <p><strong>功能说明：</strong></p>
        <ul>
            <li>使用 Playwright 打开网页</li>
            <li>点击元素、滚动页面和输入文本</li>
            <li>截取指定页面元素</li>
            <li>提取网页信息</li>
            <li>执行多步骤浏览任务</li>
        </ul>
        </div>""", 
        unsafe_allow_html=True
    )

# 页脚
st.markdown("---")
st.write("基于 Streamlit、Playwright 和 [MCP-Agent](https://www.github.com/lastmile-ai/mcp-agent) 构建 ❤️")
