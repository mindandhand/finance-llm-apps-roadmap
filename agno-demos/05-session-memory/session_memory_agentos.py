"""
05 Session Memory：给 AgentOS 服务增加 SQLite session 持久化和历史上下文。

04 已经把一个结构化金融 Agent 暴露成 AgentOS/FastAPI 服务。
这个 demo 在 04 的基础上加入最小可观察的会话能力：

1. 使用 SqliteDb 保存 Agent runs 和 sessions。
2. Agent 使用 add_history_to_context=True 读取同一 session 的最近历史。
3. AgentOS 启用 /sessions 等数据库相关路由。
4. 仍然只使用本地样例金融工具，不引入真实行情或交易动作。

运行后可以用同一个 session_id 连续调用：

第一问：比较 SH510300 和 SH588000。
第二问：继续追问“刚才哪个波动更高，为什么？”

第二问会带上同一 session 中的最近历史，而不是从零开始回答。
"""
import argparse
import json
import os
from pathlib import Path
from typing import Any, Literal

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
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


AGENT_ID = "finance-session-agent"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7777
DEFAULT_DB_FILE = APP_DIR / "data" / "session_memory.db"


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
    # 续问可能只问一个字段，例如“谁的波动率更高”，模型未必需要展开多条要点。
    # 因此 05 比 03/04 的完整报告 schema 更宽松。
    key_points: list[str] = Field(default_factory=list, max_length=4)
    evidence: list[EvidenceItem] = Field(min_length=1)


class ResearchBrief(BaseModel):
    """服务端返回给前端的结构化研究摘要。"""

    question: str
    as_of: str = Field(description="本次样例数据日期")
    summary: str = Field(description="一句话总结")
    assessments: list[SymbolAssessment] = Field(min_length=1)
    # 05 支持续问。续问有时只回答一个明确问题，例如“哪个波动更高”，
    # 这时 1 条 comparison 也足够表达上下文引用关系。
    comparison: list[str] = Field(min_length=1, max_length=5)
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


def resolve_db_file() -> Path:
    """读取 demo 使用的 SQLite 文件位置。"""
    env_value = os.getenv("AGNO_DEMO_DB_FILE")
    return Path(env_value).expanduser() if env_value else DEFAULT_DB_FILE


def build_db(db_file: Path | None = None) -> SqliteDb:
    """创建 Agno SQLite db。

    只要把同一个 db 同时传给 Agent 和 AgentOS：
    - Agent 可以保存 runs，并在后续调用中读取同一 session 的历史。
    - AgentOS 可以启用 /sessions、/memories、/metrics 等内置路由。
    """
    path = db_file or resolve_db_file()
    return SqliteDb(
        db_file=str(path),
        id="finance-session-sqlite",
        session_table="demo_05_sessions",
        memory_table="demo_05_memories",
        metrics_table="demo_05_metrics",
        eval_table="demo_05_eval_runs",
        traces_table="demo_05_traces",
        spans_table="demo_05_spans",
        components_table="demo_05_components",
        component_configs_table="demo_05_component_configs",
        component_links_table="demo_05_component_links",
        learnings_table="demo_05_learnings",
        schedules_table="demo_05_schedules",
        schedule_runs_table="demo_05_schedule_runs",
        approvals_table="demo_05_approvals",
        service_accounts_table="demo_05_service_accounts",
    )


def build_agent(db: SqliteDb) -> Agent:
    """创建带 SQLite session 历史的结构化金融 Agent。"""
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing DEEPSEEK_API_KEY. Add it to .env or export it in your shell."
        )

    model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat"))
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    return Agent(
        id=AGENT_ID,
        name="Finance Session Agent",
        model=DeepSeek(id=model_id, api_key=api_key, base_url=base_url),
        db=db,
        tools=[
            get_market_snapshot,
            get_latest_news,
            get_factor_summary,
        ],
        instructions=[
            "You are a concise finance research assistant.",
            "Use tools for market data, news, and factor facts.",
            "When the user asks a follow-up, use the session history if relevant.",
            "Return only information supported by tool results or prior session context.",
            "Do not provide personalized investment advice.",
        ],
        output_schema=ResearchBrief,
        structured_outputs=False,
        parse_response=True,
        markdown=False,
        add_history_to_context=True,
        num_history_runs=3,
        store_history_messages=True,
        debug_mode=os.getenv("AGNO_DEBUG", "").lower() in {"1", "true", "yes"},
    )


def build_agent_os(db_file: Path | None = None) -> AgentOS:
    """创建带 SQLite db 的 AgentOS。"""
    db = build_db(db_file)
    return AgentOS(
        id="finance-session-memory",
        name="Finance Session Memory",
        description="An AgentOS service with SQLite sessions and history context.",
        version="0.1.0",
        db=db,
        agents=[build_agent(db)],
        telemetry=False,
    )


def build_app() -> FastAPI:
    """返回 uvicorn 可以直接加载的 FastAPI app。"""
    return build_agent_os().get_app()


app = build_app()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve a finance AgentOS demo with SQLite session memory."
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
        "--db-file",
        type=Path,
        default=resolve_db_file(),
        help=f"SQLite db file. Default: {DEFAULT_DB_FILE}",
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
    parser.add_argument(
        "--db-info",
        action="store_true",
        help="Print database path and current session count without calling the LLM.",
    )
    return parser.parse_args()


def print_json(data: Any) -> None:
    """统一打印 JSON，保证中文不被转义。"""
    print(json.dumps(data, ensure_ascii=False, indent=2))


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
    print_json(routes)


def print_db_info(db_file: Path) -> None:
    """打印 SQLite 文件和 session 数量。"""
    db = build_db(db_file)
    sessions = db.get_sessions(limit=100)
    session_count = len(sessions) if isinstance(sessions, list) else len(sessions[0])
    print_json(
        {
            "db_file": str(db_file.resolve()),
            "exists": db_file.exists(),
            "agent_id": AGENT_ID,
            "session_count": session_count,
            "session_table": "demo_05_sessions",
            "history_context": {
                "add_history_to_context": True,
                "num_history_runs": 3,
                "store_history_messages": True,
            },
        }
    )


def main() -> None:
    args = parse_args()

    if args.routes:
        print_routes(build_agent_os(args.db_file).get_app())
        return

    if args.db_info:
        print_db_info(args.db_file)
        return

    os.environ["AGNO_DEMO_DB_FILE"] = str(args.db_file)
    target: str | FastAPI = "session_memory_agentos:app" if args.reload else build_agent_os(args.db_file).get_app()
    build_agent_os(args.db_file).serve(
        target,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
