"""
03 Structured Output：把 Agno Agent 的最终回答约束成 Pydantic schema。

02 里工具已经能返回结构化事实，但 Agent 的最终回答仍然是自然语言。
这个 demo 增加一个清晰的输出边界：

1. 工具继续负责读取本地金融样例数据。
2. Agent 负责比较、归纳和写结论。
3. 最终结果必须符合 Pydantic 模型，方便后续 API 和前端解析。
4. 当输出无法解析时，脚本给出明确错误，而不是静默吞掉异常。
"""
import argparse
import json
import os
from pathlib import Path
from typing import Any, Literal

from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError


APP_DIR = Path(__file__).resolve().parent
AGNO_DEMOS_DIR = APP_DIR.parent
REPO_DIR = AGNO_DEMOS_DIR.parent

for env_path in (
    APP_DIR / ".env",
    AGNO_DEMOS_DIR / ".env",
    REPO_DIR / ".env",
):
    load_dotenv(env_path)


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
    """面向前端或 API 的结构化金融研究摘要。"""

    question: str
    as_of: str = Field(description="本次样例数据日期")
    summary: str = Field(description="一句话总结")
    assessments: list[SymbolAssessment] = Field(min_length=1)
    comparison: list[str] = Field(min_length=2, max_length=5)
    caveats: list[str] = Field(min_length=2, max_length=4)
    next_questions: list[str] = Field(min_length=2, max_length=4)


def normalize_symbol(symbol: str) -> str:
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
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing DEEPSEEK_API_KEY. Add it to .env or export it in your shell."
        )

    model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat"))
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    return Agent(
        name="Agno Structured Finance Agent",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an Agno Agent that returns a Pydantic structured output."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default=(
            "比较 SH510300 和 SH588000 的行情、新闻和因子，"
            "输出一个适合前端展示的结构化研究摘要。"
        ),
        help="Prompt to send to the agent.",
    )
    parser.add_argument(
        "--schema",
        action="store_true",
        help="Print the ResearchBrief JSON schema without calling the LLM.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Print a deterministic sample ResearchBrief without calling the LLM.",
    )
    return parser.parse_args()


def build_sample_brief() -> ResearchBrief:
    market_510300 = get_market_snapshot("SH510300")
    market_588000 = get_market_snapshot("SH588000")
    factor_510300 = get_factor_summary("SH510300")
    factor_588000 = get_factor_summary("SH588000")

    return ResearchBrief(
        question="比较 SH510300 和 SH588000 的结构化研究摘要",
        as_of=market_510300["as_of"],
        summary="样例数据中，SH510300 表现更稳，SH588000 波动和成长风格风险更高。",
        assessments=[
            SymbolAssessment(
                symbol="SH510300",
                name=market_510300["name"],
                risk_level="medium",
                risk_score=42,
                key_points=[
                    "当日涨跌幅为 0.86%，短期表现相对占优。",
                    "60 日波动率为 0.183，低于 SH588000。",
                ],
                evidence=[
                    EvidenceItem(
                        source=market_510300["source"],
                        symbol="SH510300",
                        field="change_percent",
                        value="0.86",
                    ),
                    EvidenceItem(
                        source=factor_510300["source"],
                        symbol="SH510300",
                        field="60d_volatility",
                        value="0.183",
                    ),
                ],
            ),
            SymbolAssessment(
                symbol="SH588000",
                name=market_588000["name"],
                risk_level="high",
                risk_score=71,
                key_points=[
                    "当日涨跌幅为 -1.21%，短期承压。",
                    "60 日波动率为 0.317，样例中风险更高。",
                ],
                evidence=[
                    EvidenceItem(
                        source=market_588000["source"],
                        symbol="SH588000",
                        field="change_percent",
                        value="-1.21",
                    ),
                    EvidenceItem(
                        source=factor_588000["source"],
                        symbol="SH588000",
                        field="60d_volatility",
                        value="0.317",
                    ),
                ],
            ),
        ],
        comparison=[
            "SH510300 的短期动量和波动表现更均衡。",
            "SH588000 的成交活跃度较高，但波动率也明显更高。",
        ],
        caveats=[
            "本 demo 使用本地样例数据，不是实时行情。",
            "输出用于演示结构化 Agent，不构成投资建议。",
        ],
        next_questions=[
            "是否需要加入更长周期的回撤指标？",
            "是否需要把结果转成前端风险卡片？",
        ],
    )


def coerce_research_brief(content: Any) -> ResearchBrief:
    if isinstance(content, ResearchBrief):
        return content
    if isinstance(content, BaseModel):
        return ResearchBrief.model_validate(content.model_dump())
    if isinstance(content, str):
        return ResearchBrief.model_validate_json(content)
    if isinstance(content, dict):
        return ResearchBrief.model_validate(content)
    raise TypeError(f"Unsupported response content type: {type(content)!r}")


def print_json(model: BaseModel | dict[str, Any]) -> None:
    if isinstance(model, BaseModel):
        print(model.model_dump_json(indent=2))
    else:
        print(json.dumps(model, ensure_ascii=False, indent=2))


def main() -> None:
    args = parse_args()

    if args.schema:
        print_json(ResearchBrief.model_json_schema())
        return

    if args.sample:
        print_json(build_sample_brief())
        return

    agent = build_agent()
    response = agent.run(args.prompt, stream=False)

    try:
        brief = coerce_research_brief(response.content)
    except (TypeError, ValidationError) as exc:
        print("Structured output validation failed.")
        print(str(exc))
        print("\nRaw response content:")
        print(response.content)
        raise SystemExit(1) from exc

    print_json(brief)


if __name__ == "__main__":
    main()
