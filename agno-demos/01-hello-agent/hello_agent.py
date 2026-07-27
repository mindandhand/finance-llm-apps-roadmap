import argparse
import os
from pathlib import Path

from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
AGNO_DEMOS_DIR = APP_DIR.parent
REPO_DIR = AGNO_DEMOS_DIR.parent

for env_path in (
    APP_DIR / ".env",
    AGNO_DEMOS_DIR / ".env",
    REPO_DIR / ".env",
):
    load_dotenv(env_path)


def build_agent() -> Agent:
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing DEEPSEEK_API_KEY. Add it to .env or export it in your shell."
        )

    model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat"))
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    return Agent(
        name="Hello Agno Finance Agent",
        model=DeepSeek(id=model_id, api_key=api_key, base_url=base_url),
        instructions=[
            "You are a concise finance learning assistant.",
            "Explain concepts with concrete examples.",
            "Do not provide investment advice or pretend to know live market data.",
        ],
        markdown=True,
        debug_mode=os.getenv("AGNO_DEBUG", "").lower() in {"1", "true", "yes"},
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the first minimal Agno Agent demo."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default="用三点说明 Agno Agent 和普通 LLM 调用有什么区别。",
        help="Prompt to send to the agent.",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming output.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    agent = build_agent()
    agent.print_response(args.prompt, stream=not args.no_stream)


if __name__ == "__main__":
    main()
