"""
02 Agent With Finance Tools：给 Agno Agent 增加受控金融工具。

01 里 Agent 只能直接回答问题。这个 demo 增加一层工具边界：

1. Agent 仍然负责理解用户问题和组织最终回答。
2. 行情、新闻、指标这类事实由 Python 工具函数返回。
3. 工具只读取本地样例数据，不访问实时市场，也不执行交易动作。
4. Agent 必须引用工具结果，不能把模型记忆当作市场事实。

这个例子重点不是数据是否完整，而是展示 Agno 的最小 tools 用法：
把普通 Python 函数传给 `Agent(tools=[...])`。
"""
import argparse
import os
from pathlib import Path
from typing import Any

from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from dotenv import load_dotenv


# 当前 demo 所在目录：
#   agno-demos/02-agent-with-finance-tools
APP_DIR = Path(__file__).resolve().parent

# Agno demo 总目录：
#   agno-demos
AGNO_DEMOS_DIR = APP_DIR.parent

# 仓库根目录：
#   finance-llm-apps-roadmap
REPO_DIR = AGNO_DEMOS_DIR.parent

# 和 01 保持一致：当前 demo 的 .env 优先，然后是 agno-demos/.env，
# 最后才是仓库根目录 .env。
for env_path in (
    APP_DIR / ".env",
    AGNO_DEMOS_DIR / ".env",
    REPO_DIR / ".env",
):
    load_dotenv(env_path)


# 本 demo 使用小型内置样例数据，保证离线可读、可审计。
# 后续 demo 可以把这些函数替换成 AkShare、Qlib、数据库或内部服务。
MARKET_DATA: dict[str, dict[str, Any]] = {
    "SH510300": {
        "name": "沪深300ETF",
        "last_close": 3.493,
        "change_percent": 0.86,
        "turnover_million": 1850.4,
        "as_of": "2024-03-29",
    },
    "SH588000": {
        "name": "科创50ETF",
        "last_close": 0.812,
        "change_percent": -1.21,
        "turnover_million": 936.8,
        "as_of": "2024-03-29",
    },
}

NEWS_DATA: dict[str, list[str]] = {
    "SH510300": [
        "宽基 ETF 资金流入放缓，成交额仍保持活跃。",
        "指数权重行业分化，金融和消费板块贡献较大波动。",
    ],
    "SH588000": [
        "半导体板块波动加大，科技成长风格短期承压。",
        "科创板 ETF 成交活跃，但资金方向分歧明显。",
    ],
}

FACTOR_DATA: dict[str, dict[str, float]] = {
    "SH510300": {
        "20d_momentum": 0.041,
        "60d_volatility": 0.183,
        "turnover_score": 0.72,
    },
    "SH588000": {
        "20d_momentum": -0.026,
        "60d_volatility": 0.317,
        "turnover_score": 0.81,
    },
}


def normalize_symbol(symbol: str) -> str:
    """把用户或模型传入的 symbol 统一成工具内部使用的格式。"""
    normalized = symbol.strip().upper()
    if normalized in MARKET_DATA:
        return normalized

    # 允许用户只输入 510300 / 588000，工具自动补交易所前缀。
    if normalized == "510300":
        return "SH510300"
    if normalized == "588000":
        return "SH588000"

    raise ValueError(f"unsupported symbol: {symbol}")


def get_market_snapshot(symbol: str) -> dict[str, Any]:
    """
    查询本地样例行情快照。

    Agent 看到的是这个函数的描述、参数和返回值；真正的数值来自
    Python 数据结构，而不是模型自己生成。
    """
    normalized = normalize_symbol(symbol)
    snapshot = MARKET_DATA[normalized]
    return {
        "symbol": normalized,
        "name": snapshot["name"],
        "last_close": snapshot["last_close"],
        "change_percent": snapshot["change_percent"],
        "turnover_million": snapshot["turnover_million"],
        "as_of": snapshot["as_of"],
        "source": "local_demo_market_data",
    }


def get_latest_news(symbol: str, limit: int = 2) -> dict[str, Any]:
    """查询本地样例新闻摘要。"""
    normalized = normalize_symbol(symbol)
    safe_limit = max(1, min(limit, 5))
    return {
        "symbol": normalized,
        "items": NEWS_DATA[normalized][:safe_limit],
        "source": "local_demo_news_data",
    }


def get_factor_summary(symbol: str) -> dict[str, Any]:
    """查询本地样例因子摘要，用于演示 Agent 如何引用结构化工具结果。"""
    normalized = normalize_symbol(symbol)
    factors = FACTOR_DATA[normalized]
    return {
        "symbol": normalized,
        "factors": factors,
        "interpretation_hint": {
            "20d_momentum": "positive means recent price strength",
            "60d_volatility": "higher means larger short-term risk",
            "turnover_score": "higher means more active trading",
        },
        "source": "local_demo_factor_data",
    }


def build_agent() -> Agent:
    """创建带金融工具的 Agno Agent。"""
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing DEEPSEEK_API_KEY. Add it to .env or export it in your shell."
        )

    model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat"))
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    return Agent(
        name="Agno Finance Tool Agent",
        model=DeepSeek(id=model_id, api_key=api_key, base_url=base_url),
        # 普通 Python 函数可以作为 Agno tools 传入。
        # 函数名、类型注解、docstring 会帮助模型理解何时调用工具。
        tools=[
            get_market_snapshot,
            get_latest_news,
            get_factor_summary,
        ],
        instructions=[
            "You are a concise finance research assistant.",
            "Use tools for market data, news, and factor facts before answering.",
            "Always mention the tool data source and as_of date when available.",
            "Do not claim the data is live or suitable for trading decisions.",
            "Do not provide personalized investment advice.",
        ],
        markdown=True,
        debug_mode=os.getenv("AGNO_DEBUG", "").lower() in {"1", "true", "yes"},
    )


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="Run an Agno Agent with local finance tools."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default=(
            "请分析 SH510300 的行情快照、最新新闻和因子摘要，"
            "说明你调用了哪些工具，并给出三点观察。"
        ),
        help="Prompt to send to the agent.",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming output.",
    )
    parser.add_argument(
        "--show-tools",
        action="store_true",
        help="Print local tool outputs without calling the LLM.",
    )
    return parser.parse_args()


def print_tool_preview() -> None:
    """本地预览工具输出，不需要 API key，也不会调用模型。"""
    for symbol in ("SH510300", "SH588000"):
        print(f"\n[{symbol}] market_snapshot")
        print(get_market_snapshot(symbol))
        print(f"[{symbol}] latest_news")
        print(get_latest_news(symbol))
        print(f"[{symbol}] factor_summary")
        print(get_factor_summary(symbol))


def main() -> None:
    args = parse_args()

    # --show-tools 只验证 Python 工具层，适合在没有 API key 时检查 demo。
    if args.show_tools:
        print_tool_preview()
        return

    agent = build_agent()
    agent.print_response(args.prompt, stream=not args.no_stream)


if __name__ == "__main__":
    main()
