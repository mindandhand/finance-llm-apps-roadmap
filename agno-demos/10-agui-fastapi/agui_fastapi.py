"""
10 AG-UI FastAPI：把金融研究 Agent 接入官方 AG-UI 协议。

这个 demo 的重点不是再定义一套事件名，而是展示真实的适配链路：

    Agno Agent -> Agno RunEvent -> AGUI interface -> AG-UI SSE -> 前端

Agent 使用本地样例工具，因此可以稳定演示工具调用、流式文本和标准事件；
后续只需要替换工具实现，就可以接入真实行情、新闻和因子服务。
"""
import argparse
import os
from pathlib import Path
from typing import Any

from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from agno.os.interfaces.agui import AGUI
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


APP_DIR = Path(__file__).resolve().parent
AGNO_DEMOS_DIR = APP_DIR.parent
REPO_DIR = AGNO_DEMOS_DIR.parent
for env_path in (APP_DIR / ".env", AGNO_DEMOS_DIR / ".env", REPO_DIR / ".env"):
    load_dotenv(env_path)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7777

MARKET_DATA: dict[str, dict[str, Any]] = {
    "SH510300": {"name": "沪深300ETF", "change_percent": 0.86, "as_of": "2024-03-29"},
    "SH588000": {"name": "科创50ETF", "change_percent": -1.21, "as_of": "2024-03-29"},
}
FACTOR_DATA: dict[str, dict[str, float]] = {
    "SH510300": {"20d_momentum": 0.041, "60d_volatility": 0.183},
    "SH588000": {"20d_momentum": -0.026, "60d_volatility": 0.317},
}
NEWS_DATA: dict[str, list[str]] = {
    "SH510300": ["宽基 ETF 资金流入放缓。", "金融和消费权重影响较大。"],
    "SH588000": ["半导体板块波动加大。", "成长风格短期承压。"],
}


def normalize_symbol(symbol: str) -> str:
    """统一标的格式，只允许本 demo 明确支持的标的进入工具。"""
    value = symbol.strip().upper()
    value = {"510300": "SH510300", "588000": "SH588000"}.get(value, value)
    if value not in MARKET_DATA:
        raise ValueError(f"unsupported symbol: {symbol}")
    return value


def get_market_snapshot(symbol: str) -> dict[str, Any]:
    """返回行情事实，工具结果带来源和日期，方便前端展示证据。"""
    normalized = normalize_symbol(symbol)
    return {
        "symbol": normalized,
        "market": MARKET_DATA[normalized],
        "source": "local_demo_market_data",
    }


def get_factor_snapshot(symbol: str) -> dict[str, Any]:
    """返回因子结果，Agent 只能根据工具返回的数据进行解释。"""
    normalized = normalize_symbol(symbol)
    return {
        "symbol": normalized,
        "factors": FACTOR_DATA[normalized],
        "source": "local_demo_factor_data",
    }


def get_news_packet(symbol: str) -> dict[str, Any]:
    """返回本地新闻样例，真实系统可以替换为带引用的新闻检索工具。"""
    normalized = normalize_symbol(symbol)
    return {"symbol": normalized, "news": NEWS_DATA[normalized], "source": "local_demo_news_data"}


def build_agent() -> Agent:
    """构造被官方 AGUI interface 暴露的金融研究 Agent。"""
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or "missing"
    # Flash is the default; DEEPSEEK_MODEL_ID can still override it per environment.
    model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-v4-flash"))
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    return Agent(
        id="agui-finance-research-agent",
        name="AG-UI Finance Research Agent",
        model=DeepSeek(id=model_id, api_key=api_key, base_url=base_url),
        tools=[get_market_snapshot, get_factor_snapshot, get_news_packet],
        instructions=[
            "先调用行情、因子和新闻工具，再回答金融研究问题。",
            "回答中区分事实、解读和风险提示，并保留工具来源。",
            "不要把样例数据描述成实时行情，也不要提供个性化投资建议。",
        ],
        markdown=True,
        telemetry=False,
    )


# AGUI 将 Agno 的 RunEvent 转成标准 AG-UI SSE 事件，例如 RUN_STARTED、
# TOOL_CALL_START、TEXT_MESSAGE_CONTENT 和 RUN_FINISHED，前端不需要理解 Agno 内部对象。
agent = build_agent()
app = FastAPI(title="10 AG-UI Finance Research Demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(AGUI(agent=agent).get_router())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent_id": agent.id or ""}


@app.get("/")
def index() -> dict[str, Any]:
    return {
        "name": "10 AG-UI Finance Research Demo",
        "protocol": "AG-UI",
        "endpoint": "/agui",
        "agent_id": agent.id,
        "tools": ["get_market_snapshot", "get_factor_snapshot", "get_news_packet"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a finance Agent through the official AG-UI interface.")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.serve:
        import uvicorn

        uvicorn.run(app, host=args.host, port=args.port)
        return
    print({"endpoint": "/agui", "protocol": "AG-UI", "agent_id": agent.id})


if __name__ == "__main__":
    main()
