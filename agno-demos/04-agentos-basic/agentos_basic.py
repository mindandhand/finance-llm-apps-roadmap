"""
04 AgentOS Basic：把 Agno Agent 暴露成本地 FastAPI 服务。

前 3 个 demo 都是终端脚本：

1. 01 跑通最小 Agent。
2. 02 增加本地金融工具。
3. 03 把最终回答约束成 Pydantic schema。

这个 demo 不急着做记忆、数据库、前端或自定义 API。它只做一件事：
把一个已有 Agent 注册到 AgentOS，然后得到一个 FastAPI app。

启动后可以访问：

- GET /health：服务健康检查。
- GET /docs：Swagger 调试页面。
- POST /agents/{agent_id}/runs：调用注册到 AgentOS 的 Agent。
"""
import argparse
import json
import os
from pathlib import Path
from typing import Any, Literal

from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from agno.os.app import AgentOS
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field


APP_DIR = Path(__file__).resolve().parent
AGNO_DEMOS_DIR = APP_DIR.parent
REPO_DIR = AGNO_DEMOS_DIR.parent

for env_path in (
    APP_DIR / ".env",
    AGNO_DEMOS_DIR / ".env",
    REPO_DIR / ".env",
):
    load_dotenv(env_path)


AGENT_ID = "finance-research-agent"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7778


# 继续使用本地样例数据，让 04 的重点保持在“服务化”而不是“数据源接入”。
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


class EvidenceItem(BaseModel):
    """最终结论引用的一条可追溯事实。"""

    source: str = Field(description="工具或数据源名称")
    symbol: str = Field(description="标的代码")
    field: str = Field(description="被引用的字段或事实类型")
    value: str = Field(description="字段值，统一转为便于展示的字符串")


class SymbolAssessment(BaseModel):
    """单个标的的结构化评估。"""

    symbol: str
    name: str
    risk_level: Literal["low", "medium", "high"]
    risk_score: int = Field(ge=0, le=100, description="0 到 100 的风险分数")
    key_points: list[str] = Field(min_length=2, max_length=4)
    evidence: list[EvidenceItem] = Field(min_length=2)


class ResearchBrief(BaseModel):
    """AgentOS API 返回给调用方的结构化研究摘要。"""

    question: str
    as_of: str = Field(description="本次样例数据日期")
    summary: str = Field(description="一句话总结")
    assessments: list[SymbolAssessment] = Field(min_length=1)
    comparison: list[str] = Field(min_length=2, max_length=5)
    caveats: list[str] = Field(min_length=2, max_length=4)
    next_questions: list[str] = Field(min_length=2, max_length=4)


def normalize_symbol(symbol: str) -> str:
    """把用户输入或模型工具参数统一成内部 symbol。"""
    normalized = symbol.strip().upper()
    if normalized in MARKET_DATA:
        return normalized
    if normalized == "510300":
        return "SH510300"
    if normalized == "588000":
        return "SH588000"
    raise ValueError(f"unsupported symbol: {symbol}")


def get_market_snapshot(symbol: str) -> dict[str, Any]:
    """查询本地样例行情快照。"""
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
    """查询本地样例因子摘要。"""
    normalized = normalize_symbol(symbol)
    return {
        "symbol": normalized,
        "factors": FACTOR_DATA[normalized],
        "source": "local_demo_factor_data",
    }


def build_agent() -> Agent:
    """创建要注册到 AgentOS 的结构化金融 Agent。"""
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing DEEPSEEK_API_KEY. Add it to .env or export it in your shell."
        )

    model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat"))
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    return Agent(
        id=AGENT_ID,
        name="Finance Research Agent",
        model=DeepSeek(id=model_id, api_key=api_key, base_url=base_url),
        tools=[
            get_market_snapshot,
            get_latest_news,
            get_factor_summary,
        ],
        instructions=[
            "You are a concise finance research assistant.",
            "Use tools for every symbol before producing the final answer.",
            "Return only information supported by tool results.",
            "Do not provide personalized investment advice.",
            "Keep all output fields short and suitable for a product UI.",
        ],
        output_schema=ResearchBrief,
        structured_outputs=False,
        parse_response=True,
        markdown=False,
        debug_mode=os.getenv("AGNO_DEBUG", "").lower() in {"1", "true", "yes"},
    )


def build_agent_os() -> AgentOS:
    """创建 AgentOS 实例。

    这个 demo 暂时不传 db，所以 session、memory、approvals 等需要数据库的
    路由会出现在 /docs 中，但会以 disabled feature 的形式返回错误。
    这是刻意保留的：04 先聚焦“Agent 如何变成服务”，05 再引入记忆和存储。
    """
    return AgentOS(
        id="finance-agentos-basic",
        name="Finance AgentOS Basic",
        description="A minimal AgentOS service wrapping one structured finance agent.",
        version="0.1.0",
        agents=[build_agent()],
        telemetry=False,
    )


def build_app() -> FastAPI:
    """返回 uvicorn 可以直接加载的 FastAPI app。"""
    return build_agent_os().get_app()


# uvicorn agentos_basic:app 会读取这个模块级变量。
app = build_app()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve the structured finance Agent through Agno AgentOS."
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Host to bind. Default: {DEFAULT_HOST}",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to bind. Default: {DEFAULT_PORT}",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn reload. Useful while editing this demo.",
    )
    parser.add_argument(
        "--routes",
        action="store_true",
        help="Print available FastAPI routes without starting the server.",
    )
    return parser.parse_args()


def print_routes(fastapi_app: FastAPI) -> None:
    """打印当前 AgentOS app 暴露的主要 HTTP routes。"""
    routes: list[dict[str, Any]] = []
    for route in fastapi_app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path is None or methods is None:
            continue
        routes.append(
            {
                "path": path,
                "methods": sorted(methods),
                "name": getattr(route, "name", ""),
            }
        )
    print(json.dumps(routes, ensure_ascii=False, indent=2))


def main() -> None:
    args = parse_args()

    if args.routes:
        print_routes(app)
        return

    # reload=True 时 uvicorn 需要 import string；普通运行直接传 app 对象即可。
    target: str | FastAPI = "agentos_basic:app" if args.reload else app
    build_agent_os().serve(
        target,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
