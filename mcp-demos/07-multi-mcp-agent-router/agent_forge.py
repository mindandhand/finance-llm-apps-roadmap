"""多 MCP Agent Forge：通过 MCP 工具路由实现专业 Agent。

每个 Agent 根据领域专长连接不同的 MCP Server。本示例演示如何将查询
路由给专业 Agent，而不是让单个 Agent 访问所有工具。

灵感来源：https://github.com/WeberG619/cadre-ai
"""

import asyncio
import json
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

import streamlit as st
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

st.set_page_config(
    page_title="Agent Forge - Multi-MCP Agents",
    page_icon="\u2692\ufe0f",
    layout="wide",
)


@dataclass
class Agent:
    """拥有独立系统提示和 MCP Server 配置的专业 Agent。"""
    name: str
    description: str
    system_prompt: str
    icon: str = "\U0001f916"
    mcp_servers: list = field(default_factory=list)


# --- Agent 定义 ---
AGENTS = {
    "code_reviewer": Agent(
        name="代码审查员",
        description="审查代码缺陷、反模式和可维护性",
        icon="\U0001f50d",
        system_prompt=(
            "你是一名专业代码审查员，请分析以下方面：\n"
            "- 缺陷和逻辑错误\n"
            "- 反模式和代码异味\n"
            "- 性能问题\n"
            "- 安全漏洞\n"
            "- 可读性和可维护性\n\n"
            "给出具体问题和行号，并用代码提供修复建议。\n"
            "使用可用工具读取文件和获取仓库数据。"
        ),
        mcp_servers=[
            {"name": "github", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"]},
            {"name": "filesystem", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]},
        ],
    ),
    "security_auditor": Agent(
        name="安全审计员",
        description="检查 OWASP Top 10、注入、XSS、密钥和认证问题",
        icon="\U0001f6e1\ufe0f",
        system_prompt=(
            "你是一名专注应用安全的安全审计员。请检查：\n"
            "- OWASP Top 10 漏洞\n"
            "- 注入攻击（SQL、命令、XSS）\n"
            "- 硬编码密钥和凭证\n"
            "- 身份认证和授权缺陷\n"
            "- 不安全的依赖\n\n"
            "按严重、较高、中等、较低评定每个问题，并提供修复步骤。\n"
            "使用可用工具获取内容并检查仓库。"
        ),
        mcp_servers=[
            {"name": "github", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"]},
            {"name": "fetch", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-fetch"]},
        ],
    ),
    "researcher": Agent(
        name="研究员",
        description="研究主题、获取网页内容并综合信息",
        icon="\U0001f4da",
        system_prompt=(
            "你是一名研究助手，负责：\n"
            "- 获取并分析网页内容\n"
            "- 综合多个来源的信息\n"
            "- 提供引用和参考资料\n"
            "- 清晰总结研究发现\n\n"
            "始终注明来源并区分事实和观点。\n"
            "使用可用工具获取网页并保存研究笔记。"
        ),
        mcp_servers=[
            {"name": "fetch", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-fetch"]},
            {"name": "filesystem", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]},
        ],
    ),
    "bim_engineer": Agent(
        name="BIM 工程师",
        description="处理建筑信息模型、Revit 和施工数据",
        icon="\U0001f3d7\ufe0f",
        system_prompt=(
            "你是一名 BIM（建筑信息模型）工程师，专长包括：\n"
            "- Revit API 和模型操作\n"
            "- 施工文档标准\n"
            "- 建筑规范合规性\n"
            "- 碰撞检测和协调\n"
            "- 详图库管理\n\n"
            "处理 Revit 时，通过 MCP 桥接直接访问模型。\n"
            "参考 AIA 标准组织文档，并使用可用工具读写项目文件。"
        ),
        mcp_servers=[
            {"name": "filesystem", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]},
        ],
    ),
}


def classify_query(query: str) -> str:
    """根据关键词将查询路由给最合适的 Agent。"""
    query_lower = query.lower()

    security_keywords = ["security", "vulnerability", "owasp", "injection", "xss",
                         "csrf", "secret", "credential", "auth", "penetration",
                         "安全", "漏洞", "注入", "密钥", "认证", "渗透"]
    code_keywords = ["review", "bug", "refactor", "code quality", "anti-pattern",
                     "lint", "test", "coverage", "pull request", "pr ",
                     "审查", "缺陷", "重构", "代码质量", "测试", "覆盖率"]
    bim_keywords = ["revit", "bim", "wall", "floor plan", "sheet", "construction",
                    "building", "architecture", "detail", "annotation",
                    "墙体", "平面图", "施工", "建筑", "详图", "标注"]

    if any(kw in query_lower for kw in security_keywords):
        return "security_auditor"
    if any(kw in query_lower for kw in code_keywords):
        return "code_reviewer"
    if any(kw in query_lower for kw in bim_keywords):
        return "bim_engineer"
    return "researcher"


def mcp_tool_to_anthropic(tool) -> dict:
    """将 MCP 工具定义转换为 Anthropic 工具格式。"""
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.inputSchema,
    }


async def connect_mcp_servers(agent: Agent) -> tuple[AsyncExitStack, list[dict], dict[str, ClientSession]]:
    """启动 MCP Server 并收集工具。

    返回 (exit_stack, tools_list, session_map)，其中 session_map 将
    tool_name 映射到对应会话，用于分发工具调用。
    """
    stack = AsyncExitStack()
    await stack.__aenter__()

    all_tools = []
    session_map = {}

    for srv_config in agent.mcp_servers:
        env = {**os.environ}
        if "env" in srv_config:
            env.update(srv_config["env"])

        params = StdioServerParameters(
            command=srv_config["command"],
            args=srv_config.get("args", []),
            env=env,
        )

        stdio_transport = await stack.enter_async_context(stdio_client(params))
        read_stream, write_stream = stdio_transport
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()

        result = await session.list_tools()
        for tool in result.tools:
            all_tools.append(mcp_tool_to_anthropic(tool))
            session_map[tool.name] = session

    return stack, all_tools, session_map


async def run_agent_async(client: Anthropic, agent: Agent, query: str, history: list) -> str:
    """通过指定 Agent 和真实 MCP 工具连接执行查询。"""
    messages = history + [{"role": "user", "content": query}]

    if not agent.mcp_servers:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=agent.system_prompt,
            messages=messages,
        )
        return response.content[0].text

    stack, tools, session_map = await connect_mcp_servers(agent)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=agent.system_prompt,
            messages=messages,
            tools=tools,
        )

        # Agent 循环：持续处理工具调用，直到获得最终文本回答
        while response.stop_reason == "tool_use":
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            tool_results = []

            for tool_use in tool_use_blocks:
                session = session_map.get(tool_use.name)
                if session is None:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": f"错误：未知工具“{tool_use.name}”",
                        "is_error": True,
                    })
                    continue

                try:
                    result = await session.call_tool(tool_use.name, tool_use.input)
                    result_text = ""
                    for content in result.content:
                        if hasattr(content, "text"):
                            result_text += content.text
                        else:
                            result_text += str(content)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result_text,
                    })
                except Exception as e:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": f"调用工具时出错：{e}",
                        "is_error": True,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=agent.system_prompt,
                messages=messages,
                tools=tools,
            )

        # 提取最终文本
        text_blocks = [b.text for b in response.content if hasattr(b, "text")]
        return "\n".join(text_blocks) if text_blocks else "未生成回答。"

    finally:
        await stack.aclose()


def run_agent(client: Anthropic, agent: Agent, query: str, history: list) -> str:
    """异步 Agent 执行器的同步包装函数。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(run_agent_async(client, agent, query, history))
    finally:
        loop.close()


def main():
    st.markdown("# \u2692\ufe0f Agent Forge")
    st.markdown("**通过 MCP 工具路由连接专业 Agent。** "
                "每个 Agent 根据自身专长连接不同的 MCP Server。")

    # 侧边栏
    with st.sidebar:
        st.header("\U0001f511 配置")
        api_key = st.text_input("Anthropic API Key", type="password",
                                help="可在 console.anthropic.com 获取")
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key

        st.markdown("---")
        st.header("\U0001f916 Agent 列表")
        for agent_id, agent in AGENTS.items():
            with st.expander(f"{agent.icon} {agent.name}"):
                st.markdown(f"**{agent.description}**")
                st.markdown(f"*系统提示：* {agent.system_prompt[:100]}...")
                if agent.mcp_servers:
                    st.markdown("**MCP Server：**")
                    for srv in agent.mcp_servers:
                        st.markdown(f"- `{srv['name']}`")

        st.markdown("---")
        st.markdown("基于 [cadre-ai](https://github.com/WeberG619/cadre-ai) 构建")

    # 选择 Agent
    col1, col2 = st.columns([3, 1])
    with col2:
        mode = st.radio("Agent 选择方式", ["自动路由", "手动选择"])
        if mode == "手动选择":
            selected = st.selectbox(
                "选择 Agent",
                options=list(AGENTS.keys()),
                format_func=lambda x: f"{AGENTS[x].icon} {AGENTS[x].name}",
            )

    # 保存每个 Agent 的对话历史
    if "histories" not in st.session_state:
        st.session_state.histories = {k: [] for k in AGENTS}
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 显示对话
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar=msg.get("avatar")):
            st.markdown(msg["content"])

    # 对话输入框
    if prompt := st.chat_input("请输入任何问题……"):
        if not api_key:
            st.error("请在侧边栏输入 Anthropic API Key。")
            return

        # 将查询路由给 Agent
        if mode == "自动路由":
            agent_id = classify_query(prompt)
        else:
            agent_id = selected

        agent = AGENTS[agent_id]

        # 显示用户消息
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 显示路由信息
        with st.chat_message("assistant", avatar=agent.icon):
            st.caption(f"已路由至 **{agent.icon} {agent.name}**")
            tools_info = ", ".join(s["name"] for s in agent.mcp_servers)
            st.caption(f"MCP Server：{tools_info}" if tools_info else "未连接 MCP Server")

            client = Anthropic(api_key=api_key)
            with st.spinner(f"{agent.name} 正在连接 MCP Server……"):
                response = run_agent(
                    client, agent, prompt,
                    st.session_state.histories[agent_id],
                )

            st.markdown(response)

        # 更新对话历史
        st.session_state.histories[agent_id].append(
            {"role": "user", "content": prompt}
        )
        st.session_state.histories[agent_id].append(
            {"role": "assistant", "content": response}
        )
        st.session_state.messages.append(
            {"role": "assistant", "content": response, "avatar": agent.icon}
        )


if __name__ == "__main__":
    main()
