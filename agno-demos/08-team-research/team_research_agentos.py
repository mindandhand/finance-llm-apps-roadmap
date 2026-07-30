"""
08 Team Research：用 Researcher、Analyst、Reviewer 组成金融研究团队。

Team 的价值不是让多个模型重复聊天，而是把职责边界写清楚：

- Researcher 负责收集样例行情和新闻事实。
- Analyst 负责比较因子、动量和波动率。
- Reviewer 负责检查证据、风险提示和投资建议边界。
"""
import argparse
import json
import os
from pathlib import Path
from typing import Any

from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from agno.os.app import AgentOS
from agno.team import Team
from agno.team.team import TeamMode
from dotenv import load_dotenv
from fastapi import FastAPI


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
NEWS_DATA = {
    "SH510300": ["宽基 ETF 资金流入放缓。", "金融和消费权重影响较大。"],
    "SH588000": ["半导体板块波动加大。", "成长风格短期承压。"],
}
FACTOR_DATA = {
    "SH510300": {"20d_momentum": 0.041, "60d_volatility": 0.183},
    "SH588000": {"20d_momentum": -0.026, "60d_volatility": 0.317},
}


def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    aliases = {"510300": "SH510300", "588000": "SH588000"}
    value = aliases.get(value, value)
    if value not in MARKET_DATA:
        raise ValueError(f"unsupported symbol: {symbol}")
    return value


def get_research_packet(symbol: str) -> dict[str, Any]:
    normalized = normalize_symbol(symbol)
    return {
        "symbol": normalized,
        "market": MARKET_DATA[normalized],
        "news": NEWS_DATA[normalized],
        "source": "local_demo_research_packet",
    }


def get_factor_packet(symbol: str) -> dict[str, Any]:
    normalized = normalize_symbol(symbol)
    return {
        "symbol": normalized,
        "factors": FACTOR_DATA[normalized],
        "source": "local_demo_factor_packet",
    }


def build_model() -> DeepSeek:
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or "missing"
    model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat"))
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    return DeepSeek(id=model_id, api_key=api_key, base_url=base_url)


def build_team() -> Team:
    model = build_model()
    researcher = Agent(
        id="researcher",
        name="Researcher",
        role="Collect local market and news evidence.",
        model=model,
        tools=[get_research_packet],
        instructions=["Only report facts returned by tools.", "Always include source names."],
        markdown=True,
        telemetry=False,
    )
    analyst = Agent(
        id="analyst",
        name="Analyst",
        role="Compare factors and produce concise quantitative observations.",
        model=model,
        tools=[get_factor_packet],
        instructions=["Use factor tools before making factor claims.", "Explain volatility and momentum plainly."],
        markdown=True,
        telemetry=False,
    )
    reviewer = Agent(
        id="reviewer",
        name="Reviewer",
        role="Check evidence, caveats, and investment-advice boundaries.",
        model=model,
        instructions=["Flag unsupported claims.", "Require a non-advice caveat in the final answer."],
        markdown=True,
        telemetry=False,
    )
    return Team(
        id="finance-research-team",
        name="Finance Research Team",
        model=model,
        mode=TeamMode.coordinate,
        members=[researcher, analyst, reviewer],
        instructions=[
            "Coordinate the members to compare SH510300 and SH588000.",
            "Final answer must separate facts, interpretation, reviewer caveats, and next questions.",
        ],
        markdown=True,
        show_members_responses=True,
        telemetry=False,
    )


def build_app() -> FastAPI:
    agent_os = AgentOS(
        id="team-research-demo",
        name="08 Team Research Demo",
        teams=[build_team()],
        telemetry=False,
    )
    return agent_os.get_app()


app = build_app()


def print_sample_team_plan() -> None:
    sample = {
        "team_id": "finance-research-team",
        "members": ["Researcher", "Analyst", "Reviewer"],
        "handoff": [
            "Researcher collects local market/news packets.",
            "Analyst compares 20d momentum and 60d volatility.",
            "Reviewer checks evidence and non-advice caveat.",
        ],
    }
    print(json.dumps(sample, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the team research demo.")
    parser.add_argument("prompt", nargs="?", default="比较 SH510300 和 SH588000 的行情、新闻和因子。")
    parser.add_argument("--sample-team", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.sample_team:
        print_sample_team_plan()
        return
    if args.serve:
        AgentOS(teams=[build_team()], telemetry=False).serve(app, host=args.host, port=args.port)
        return
    response = build_team().run(args.prompt)
    print(response.content)


if __name__ == "__main__":
    main()
