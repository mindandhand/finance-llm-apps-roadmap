import asyncio
import os
from pathlib import Path
import shutil
import streamlit as st
from textwrap import dedent
from agno.agent import Agent
from agno.run.agent import RunOutput
from agno.models.deepseek import DeepSeek
from agno.tools.mcp import MCPTools
from dotenv import load_dotenv
from mcp import StdioServerParameters

APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
WORKSPACE_DIR = REPO_DIR.parent
for env_path in (APP_DIR / ".env", REPO_DIR / ".env", WORKSPACE_DIR / ".env"):
    load_dotenv(env_path)

st.set_page_config(page_title="GitHub MCP Agent", page_icon="🐙", layout="wide")

st.markdown("<h1 class='main-header'>🐙 GitHub MCP Agent</h1>", unsafe_allow_html=True)
st.markdown("使用自然语言查询 GitHub 仓库、Issue、Pull Request 和项目活动。")

with st.sidebar:
    st.header("🔑 认证配置")
    
    deepseek_key = st.text_input(
        "DeepSeek API Key",
        value=os.getenv("DEEPSEEK_API_KEY", ""),
        type="password",
        help="用于调用 DeepSeek 并理解 GitHub 查询。",
    )
    if deepseek_key:
        os.environ["DEEPSEEK_API_KEY"] = deepseek_key
    
    github_token = st.text_input(
        "GitHub Token",
        value=os.getenv("GITHUB_TOKEN", ""),
        type="password",
        help="在 github.com/settings/tokens 创建，按需授予仓库读取权限。",
    )
    if github_token:
        os.environ["GITHUB_TOKEN"] = github_token
    
    st.markdown("---")
    st.markdown("### 示例查询")
    
    st.markdown("**Issue**")
    st.markdown("- 查看带 bug 标签的 Issue")
    st.markdown("- 哪些 Issue 正在积极讨论？")
    
    st.markdown("**Pull Request**")
    st.markdown("- 哪些 PR 等待 Review？")
    st.markdown("- 查看最近合并的 PR")
    
    st.markdown("**仓库活动**")
    st.markdown("- 查看仓库健康指标")
    st.markdown("- 分析仓库活动趋势")
    
    st.markdown("---")
    st.caption("如果查询中没有写仓库，程序会自动补充主区域中的仓库。")

col1, col2 = st.columns([3, 1])
with col1:
    repo = st.text_input("GitHub 仓库", value="Shubhamsaboo/awesome-llm-apps", help="格式：owner/repo")
with col2:
    query_type = st.selectbox("查询类型", [
        "Issue", "Pull Request", "仓库活动", "自定义"
    ])

if query_type == "Issue":
    query_template = f"查看 {repo} 中带 bug 标签的 Issue"
elif query_type == "Pull Request":
    query_template = f"查看 {repo} 最近合并的 Pull Request"
elif query_type == "仓库活动":
    query_template = f"分析 {repo} 的仓库活动和健康状况"
else:
    query_template = ""

query = st.text_area("查询内容", value=query_template, placeholder="你想了解这个仓库的什么信息？")


def deepseek_model() -> DeepSeek:
    """创建用于 GitHub 工具调用和结果整理的 DeepSeek Agent 模型。"""
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("未找到 DEEPSEEK_API_KEY。")
    return DeepSeek(
        id=os.getenv("DEEPSEEK_MODEL_ID", "deepseek-chat"),
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )

async def run_github_agent(message):
    if not os.getenv("GITHUB_TOKEN"):
        return "错误：未提供 GitHub Token。"
    
    if not os.getenv("DEEPSEEK_API_KEY"):
        return "错误：未提供 DEEPSEEK_API_KEY。"

    if not shutil.which("podman"):
        return "错误：未找到 Podman，请先安装并启动 Podman machine。"
    
    try:
        server_params = StdioServerParameters(
            command="podman",
            args=[
                "run", "-i", "--rm",
                "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
                "-e", "GITHUB_TOOLSETS",
                "ghcr.io/github/github-mcp-server"
            ],
            env={
                **os.environ,
                "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv('GITHUB_TOKEN'),
                "GITHUB_TOOLSETS": "repos,issues,pull_requests"
            }
        )
        
        async with MCPTools(server_params=server_params) as mcp_tools:
            agent = Agent(
                model=deepseek_model(),
                tools=[mcp_tools],
                instructions=dedent("""\
                    你是 GitHub 助手，帮助用户查询仓库及其活动。
                    - 使用中文回答，并给出有条理、简洁的结论
                    - 只使用 GitHub API 返回的事实，不要编造缺失数据
                    - 适合时使用 Markdown 表格展示数值
                    - 重要结论尽量附上 GitHub 页面链接
                """),
                markdown=True,
            )
            
            response: RunOutput = await asyncio.wait_for(agent.arun(message), timeout=120.0)
            return response.content
                
    except asyncio.TimeoutError:
        return "错误：请求超过 120 秒仍未完成。"
    except Exception as e:
        return f"错误：{str(e)}"

if st.button("🚀 执行查询", type="primary", use_container_width=True):
    if not deepseek_key:
        st.error("请在侧边栏输入 DeepSeek API Key。")
    elif not github_token:
        st.error("请在侧边栏输入 GitHub Token。")
    elif not query:
        st.error("请输入查询内容。")
    else:
        with st.spinner("正在查询 GitHub 仓库..."):
            if repo and repo not in query:
                full_query = f"{query} in {repo}"
            else:
                full_query = query
                
            result = asyncio.run(run_github_agent(full_query))
        
        st.markdown("### 查询结果")
        st.markdown(result)

if 'result' not in locals():
    st.markdown(
        """<div class='info-box'>
        <h4>How to use this app:</h4>
        <ol>
            <li>在侧边栏配置 <strong>DeepSeek API Key</strong></li>
            <li>在侧边栏配置 GitHub Token</li>
            <li>填写仓库名称，例如 Shubhamsaboo/awesome-llm-apps</li>
            <li>选择查询类型或编写自定义查询</li>
            <li>点击“执行查询”查看结果</li>
        </ol>
        <p><strong>How it works:</strong></p>
        <ul>
            <li>通过 Podman 启动官方 GitHub MCP Server，访问 GitHub API</li>
            <li>DeepSeek Agent 理解查询并调用相应 GitHub 工具</li>
            <li>结果使用 Markdown 展示，并尽量附带链接</li>
            <li>针对 Issue、PR 或仓库活动的具体问题效果更好</li>
        </ul>
        </div>""", 
        unsafe_allow_html=True
    )
