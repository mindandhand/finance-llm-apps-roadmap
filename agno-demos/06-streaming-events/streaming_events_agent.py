"""
06 Streaming Events：把 Agno 的内容和工具事件流暴露给终端与 AgentOS。

这个 demo 可以独立运行，不依赖 04/05 的代码。它展示两条相同来源的事件流：

1. `Agent.run(..., stream=True, stream_events=True)` 供 Python 客户端消费。
2. AgentOS 的 `POST /agents/{agent_id}/runs` 供浏览器通过 SSE 消费。
"""
import argparse
import json
import os
from pathlib import Path
from typing import Any

from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from agno.os import AgentOS
from agno.run.agent import RunEvent
from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
AGNO_DEMOS_DIR = APP_DIR.parent
REPO_DIR = AGNO_DEMOS_DIR.parent

for env_path in (APP_DIR / ".env", AGNO_DEMOS_DIR / ".env", REPO_DIR / ".env"):
    load_dotenv(env_path)


MARKET_DATA: dict[str, dict[str, Any]] = {
    "SH510300": {
        "name": "沪深300ETF",
        "last_close": 3.493,
        "change_percent": 0.86,
        "as_of": "2024-03-29",
    },
    "SH588000": {
        "name": "科创50ETF",
        "last_close": 0.812,
        "change_percent": -1.21,
        "as_of": "2024-03-29",
    },
}

FACTOR_DATA: dict[str, dict[str, float]] = {
    "SH510300": {"20d_momentum": 0.041, "60d_volatility": 0.183},
    "SH588000": {"20d_momentum": -0.026, "60d_volatility": 0.317},
}


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    aliases = {"510300": "SH510300", "588000": "SH588000"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in MARKET_DATA:
        raise ValueError(f"unsupported symbol: {symbol}")
    return normalized


def get_market_snapshot(symbol: str) -> dict[str, Any]:
    """读取本地样例行情快照；数据不是实时行情。"""
    normalized = normalize_symbol(symbol)
    return {
        "symbol": normalized,
        **MARKET_DATA[normalized],
        "source": "local_demo_market_data",
    }


def get_factor_summary(symbol: str) -> dict[str, Any]:
    """读取本地样例因子数据；用于比较动量和波动率。"""
    normalized = normalize_symbol(symbol)
    return {
        "symbol": normalized,
        "factors": FACTOR_DATA[normalized],
        "source": "local_demo_factor_data",
    }


def build_agent() -> Agent:
    # 使用占位值可以让服务在未配置 key 时仍启动并展示 /docs。
    # 真正发起模型请求前，CLI 会给出明确提示；服务调用则由模型层返回错误。
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or "missing"
    model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat"))
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    return Agent(
        id="streaming-finance-agent",
        name="Streaming Finance Agent",
        model=DeepSeek(id=model_id, api_key=api_key, base_url=base_url),
        tools=[get_market_snapshot, get_factor_summary],
        instructions=[
            "Use the tools before stating market or factor facts.",
            "Compare the requested symbols with short, evidence-based observations.",
            "Mention the local sample source and data date.",
            "Do not provide investment advice.",
        ],
        markdown=True,
        debug_mode=os.getenv("AGNO_DEBUG", "").lower() in {"1", "true", "yes"},
    )


# AgentOS 接收的仍然是普通 Agent 对象。这里把 Agent 定义成模块级变量，
# 一方面便于 AgentOS 在启动时发现它，另一方面也让终端模式复用完全相同的
# Agent 配置，避免“终端能运行、API 却使用另一套工具或 instructions”。
agent = build_agent()

# AgentOS 会为 agents 列表中的每个 Agent 自动注册运行接口。
# 本 demo 不自己实现 StreamingResponse；AgentOS 会负责把 Agno 的运行事件
# 转换为 SSE，并处理 content type、连接关闭等 HTTP 层细节。
agent_os = AgentOS(
    id="streaming-events-demo",
    name="06 Streaming Events Demo",
    agents=[agent],
    telemetry=False,
)

# `app` 是标准 FastAPI ASGI application。除了供 `agent_os.serve()` 使用，
# 也可以通过 `uvicorn streaming_events_agent:app` 启动。
app = agent_os.get_app()


def event_name(event: Any) -> str:
    """把事件类型统一转换为适合日志和 JSON 展示的字符串。

    Agno 事件对象的 `event` 字段通常是 `RunEvent` 枚举，例如
    `RunEvent.tool_call_started`，其 `.value` 是 `"ToolCallStarted"`。
    测试替身或不同版本返回的对象也可能直接把该字段保存为字符串。

    因此这里依次处理：

    1. 事件没有 `event` 字段时使用 `"Unknown"`，避免调试代码自身报错。
    2. 字段是枚举时读取 `.value`。
    3. 字段已经是字符串或其他类型时用 `str()` 作为兼容兜底。
    """
    value = getattr(event, "event", "Unknown")
    return getattr(value, "value", str(value))


def tool_summary(event: Any) -> dict[str, Any]:
    """提取工具事件中适合展示和序列化的少量字段。

    `ToolCallStarted` 和 `ToolCallCompleted` 的 `event.tool` 通常是 Agno 的
    Pydantic 模型，但测试代码、旧版事件或自定义事件也可能传入普通 dict。
    这里先把这些形态统一成字典，再只保留 UI 真正关心的字段：

    - `tool_name`：调用了哪个工具。
    - `tool_args`：工具收到的参数，可用于工具卡片的输入摘要。
    - `result`：完成后的工具结果。
    - `tool_call_error`：失败原因。

    不直接返回完整 tool 对象，是因为其中还可能包含内部状态、不可 JSON
    序列化的对象或当前 demo 不关心的字段。生产环境还应在这里对参数和结果
    做长度限制及敏感字段脱敏。
    """
    # 非工具事件一般没有 `tool` 字段；返回空字典让调用方保持统一逻辑。
    tool = getattr(event, "tool", None)
    if tool is None:
        return {}

    # 兼容测试样例或调用方自己构造的 dict 事件。
    if isinstance(tool, dict):
        payload = tool
    # Agno 当前的工具执行对象通常提供 model_dump，但不同版本返回值形态
    # 不完全一致；只有拿到普通 dict 时才直接使用。
    elif hasattr(tool, "model_dump"):
        dumped = tool.model_dump(exclude_none=True)
        if isinstance(dumped, dict):
            payload = dumped
        else:
            payload = {}
    # 最后的兜底主要用于调试：即使遇到未知对象，也不要让事件打印器崩溃。
    else:
        payload = {}

    # 对真实 Agno ToolExecution 对象，直接读取属性是最稳定的展示方式。
    # 这同时弥补 model_dump 不可用或返回非 dict 时导致工具摘要为空的问题。
    for key in ("tool_call_id", "tool_name", "tool_args", "result", "tool_call_error"):
        if key not in payload and hasattr(tool, key):
            value = getattr(tool, key)
            if value is not None:
                payload[key] = value

    if not payload:
        payload = {"value": str(tool)}

    # 使用白名单而不是复制 payload，明确终端/前端输出的数据边界。
    return {
        key: payload[key]
        for key in ("tool_call_id", "tool_name", "tool_args", "result", "tool_call_error")
        if key in payload
    }


def print_event(event: Any) -> None:
    """把 Agno 事件压缩成适合学习和调试的终端格式。

    内容事件和状态事件采用不同输出方式：

    - `RunContent` 不断追加模型生成的文本，不插入额外 JSON。
    - 工具和生命周期事件各占一行，以 `[event]` 开头输出 JSON。

    这种区分对应前端的两个更新通道：content 追加到聊天消息，状态事件
    更新 loading、工具卡片或错误提示。
    """
    name = event_name(event)

    # 默认流式响应会产生许多 RunContent chunk。使用 end="" 才能把这些
    # 小片段拼接成连续正文；flush=True 让用户无需等待输出缓冲区填满。
    if getattr(event, "event", None) == RunEvent.run_content:
        content = getattr(event, "content", None)
        if content:
            print(content, end="", flush=True)
        return

    # 其余事件转成一行 JSON，便于人阅读，也方便未来管道程序逐行解析。
    payload: dict[str, Any] = {"event": name}

    # ToolCallStarted 和 ToolCallCompleted 都包含 "ToolCall"，可以共用同一
    # 提取逻辑。若未来 Agno 增加新的工具事件，也能自动获得基础摘要。
    if "ToolCall" in name:
        payload["tool"] = tool_summary(event)

    # run_id 是关联一次完整执行的关键字段。这里只在生命周期节点重复输出，
    # 避免每个内容 chunk 都携带相同信息造成终端噪声。
    if name in {"RunStarted", "RunCompleted", "RunError"}:
        payload["run_id"] = getattr(event, "run_id", None)

    # 错误事件保留错误内容；default=str 则保证异常对象等特殊类型仍可输出。
    if name == "RunError":
        payload["content"] = str(getattr(event, "content", "unknown error"))
    print(f"\n[event] {json.dumps(payload, ensure_ascii=False, default=str)}")


def print_sample_events() -> None:
    """无需 API key 的稳定预览，说明前端将收到的三类状态。"""
    # 这里不是伪造一次模型执行，而是提供固定的“事件契约预览”：
    # 它适合在配置 API key 前检查日志格式，也适合前端先据此开发状态组件。
    samples = [
        {"event": "RunStarted", "run_id": "sample-run"},
        {
            "event": "ToolCallStarted",
            "tool": {
                "tool_name": "get_market_snapshot",
                "tool_args": {"symbol": "SH510300"},
            },
        },
        {
            "event": "ToolCallCompleted",
            "tool": {
                "tool_name": "get_market_snapshot",
                "result": get_market_snapshot("SH510300"),
            },
        },
        {"event": "RunContent", "content": "SH510300 的样例行情显示……"},
        {"event": "RunCompleted", "run_id": "sample-run"},
    ]
    for sample in samples:
        print(json.dumps(sample, ensure_ascii=False, default=str))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the streaming events demo.")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="比较 SH510300 和 SH588000 的动量与波动率，并说明数据来源。",
    )
    parser.add_argument(
        "--sample-events",
        action="store_true",
        help="Preview representative events without calling an LLM.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start AgentOS instead of streaming events in the terminal.",
    )
    parser.add_argument("--host", default=os.getenv("AGENT_OS_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("AGENT_OS_PORT", "7777"))
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.sample_events:
        print_sample_events()
        return

    if args.serve:
        agent_os.serve(
            app="streaming_events_agent:app",
            host=args.host,
            port=args.port,
            reload=False,
        )
        return

    if not (os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")):
        raise SystemExit(
            "Missing DEEPSEEK_API_KEY. Configure .env, or use --sample-events."
        )

    # stream=True 让 Agent 返回迭代器，而不是等待完整 RunOutput。
    # stream_events=True 进一步要求 Agno 不只返回 RunContent，还返回工具调用
    # 和生命周期事件；这正是本 demo 相比普通 token streaming 新增的能力。
    stream = agent.run(args.prompt, stream=True, stream_events=True)
    for event in stream:
        print_event(event)
    print()


if __name__ == "__main__":
    main()
