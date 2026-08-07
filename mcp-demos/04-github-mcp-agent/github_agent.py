import asyncio
import os
import streamlit as st
from textwrap import dedent
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.run.agent import RunOutput
from agno.tools.mcp import MCPTools
from mcp import StdioServerParameters
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))
from llm_config import create_agno_openai_model, get_llm_api_key, get_llm_model

st.set_page_config(page_title="🐙 GitHub MCP Agent", page_icon="🐙", layout="wide")

st.markdown("<h1 class='main-header'>🐙 GitHub MCP Agent</h1>", unsafe_allow_html=True)
st.markdown("使用自然语言和模型上下文协议（MCP）探索 GitHub 仓库")

with st.sidebar:
    st.header("🔑 身份认证")
    
    llm_key = st.text_input("大语言模型 API Key", type="password",
                            help="Agent 使用的 DeepSeek/OpenAI 兼容密钥")
    if llm_key:
        os.environ["DEEPSEEK_API_KEY"] = llm_key
    st.caption(f"模型：{get_llm_model()}")
    
    github_token = st.text_input("GitHub Token", type="password", 
                                help="在 github.com/settings/tokens 创建具有 repo 权限的 Token")
    if github_token:
        os.environ["GITHUB_TOKEN"] = github_token
    
    st.markdown("---")
    st.markdown("### 示例查询")
    
    st.markdown("**Issue**")
    st.markdown("- 按标签列出 Issue")
    st.markdown("- 哪些 Issue 正在被积极讨论？")
    
    st.markdown("**Pull Request**")
    st.markdown("- 哪些 PR 需要审查？")
    st.markdown("- 列出最近合并的 PR")
    
    st.markdown("**仓库**")
    st.markdown("- 显示仓库健康指标")
    st.markdown("- 分析仓库活跃规律")
    
    st.markdown("---")
    st.caption("说明：如果主输入框尚未选择仓库，请在查询中明确指定仓库。")

col1, col2 = st.columns([3, 1])
with col1:
    repo = st.text_input("仓库", value="Shubhamsaboo/awesome-llm-apps", help="格式：owner/repo")
with col2:
    query_type = st.selectbox("查询类型", [
        "Issue", "Pull Request", "仓库活动", "自定义"
    ])

if query_type == "Issue":
    query_template = f"查找 {repo} 中带有 bug 标签的 Issue"
elif query_type == "Pull Request":
    query_template = f"列出 {repo} 最近合并的 PR"
elif query_type == "仓库活动":
    query_template = f"分析 {repo} 的代码质量趋势"
else:
    query_template = ""

query = st.text_area("你的查询", value=query_template,
                     placeholder="你想了解这个仓库的哪些信息？")

async def run_github_agent(message):
    if not os.getenv("GITHUB_TOKEN"):
        return "错误：未提供 GitHub Token"
    
    if not get_llm_api_key():
        return "错误：未提供大语言模型 API Key"
    
    try:
        server_params = StdioServerParameters(
            command="docker",
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
                model=create_agno_openai_model(OpenAIChat),
                tools=[mcp_tools],
                instructions=dedent("""\
                    你是 GitHub 助手，负责帮助用户探索仓库及其活动。
                    - 有条理且简洁地说明仓库情况
                    - 以 GitHub API 返回的事实和数据为依据
                    - 使用 Markdown 提升可读性
                    - 适合时使用表格展示数值数据
                    - 有帮助时附上相关 GitHub 页面链接
                """),
                markdown=True,
            )
            
            response: RunOutput = await asyncio.wait_for(agent.arun(message), timeout=120.0)
            return response.content
                
    except asyncio.TimeoutError:
        return "错误：请求在 120 秒后超时"
    except Exception as e:
        return f"错误：{str(e)}"

if st.button("🚀 运行查询", type="primary", use_container_width=True):
    if not llm_key and not get_llm_api_key():
        st.error("请在侧边栏输入 DeepSeek/OpenAI 兼容 API Key")
    elif not github_token:
        st.error("请在侧边栏输入 GitHub Token")
    elif not query:
        st.error("请输入查询内容")
    else:
        with st.spinner("正在分析 GitHub 仓库……"):
            if repo and repo not in query:
                full_query = f"{query}，仓库为 {repo}"
            else:
                full_query = query
                
            result = asyncio.run(run_github_agent(full_query))
        
        st.markdown("### 查询结果")
        st.markdown(result)

if 'result' not in locals():
    st.markdown(
        """<div class='info-box'>
        <h4>使用方法：</h4>
        <ol>
            <li>在侧边栏输入<strong>大语言模型 API Key</strong></li>
            <li>在侧边栏输入 <strong>GitHub Token</strong></li>
            <li>指定仓库，例如 Shubhamsaboo/awesome-llm-apps</li>
            <li>选择查询类型或输入自定义查询</li>
            <li>点击“运行查询”查看结果</li>
        </ol>
        <p><strong>工作原理：</strong></p>
        <ul>
            <li>通过 Docker 运行官方 GitHub MCP Server，实时访问 GitHub API</li>
            <li>Agent 理解查询并调用合适的 GitHub API</li>
            <li>使用易读的 Markdown 展示分析结果和链接</li>
            <li>查询聚焦于 Issue、PR 或仓库信息时效果更好</li>
        </ul>
        </div>""", 
        unsafe_allow_html=True
    )
