"""
01 Hello Agent：最小可运行的 Agno Agent。

这个 demo 只保留 Agno Agent 的最小闭环：

1. 从 `.env` 文件读取模型配置。
2. 创建一个 Agno `Agent`。
3. 把 Agent 连接到 DeepSeek 兼容模型。
4. 从命令行接收一个 prompt，并把回答流式输出到终端。

这里暂时不加入工具、记忆、AgentOS 或前端，目的是先看清楚：
Agent 本身到底包了哪些东西，以及一次最小调用是怎么跑起来的。
"""
import argparse
import os
from pathlib import Path

from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from dotenv import load_dotenv


# 当前 demo 所在目录：
#   agno-demos/01-hello-agent
APP_DIR = Path(__file__).resolve().parent

# Agno demo 总目录：
#   agno-demos
AGNO_DEMOS_DIR = APP_DIR.parent

# 仓库根目录：
#   finance-llm-apps-roadmap
REPO_DIR = AGNO_DEMOS_DIR.parent

# 依次加载三个位置的 .env：
#
# 1. 当前 demo 目录：只影响 01-hello-agent。
# 2. agno-demos 目录：影响所有 Agno demos。
# 3. 仓库根目录：作为全局默认配置。
#
# python-dotenv 默认不会覆盖已经存在的环境变量，所以命令行 export 的变量
# 仍然可以覆盖 .env 文件里的配置。
for env_path in (
    APP_DIR / ".env",
    AGNO_DEMOS_DIR / ".env",
    REPO_DIR / ".env",
):
    load_dotenv(env_path)


def build_agent() -> Agent:
    """创建本 demo 使用的 Agno Agent。"""
    # DeepSeek 模型需要 API key。这里也允许用 OPENAI_API_KEY 作为兜底，
    # 方便用户复用已有环境变量名，但错误提示仍以本 demo 推荐的
    # DEEPSEEK_API_KEY 为准。
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing DEEPSEEK_API_KEY. Add it to .env or export it in your shell."
        )

    # 模型名和 base URL 都从环境变量读取：
    #
    # - DEEPSEEK_MODEL_ID：DeepSeek 专用模型名。
    # - MODEL_ID：通用模型名兜底，后续 demo 可以复用。
    # - DEEPSEEK_BASE_URL：DeepSeek API 地址。
    #
    # 这样切换模型时只改 .env，不需要改 Python 代码。
    model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat"))
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    # Agent 是 Agno 的核心对象。这个最小例子里只配置四类信息：
    #
    # - name：Agent 名称，便于日志和调试时识别。
    # - model：底层 LLM，这里用 DeepSeek。
    # - instructions：长期稳定的行为约束。
    # - markdown / debug_mode：输出格式和调试开关。
    return Agent(
        name="Hello Agno Finance Agent",
        model=DeepSeek(id=model_id, api_key=api_key, base_url=base_url),
        instructions=[
            # instructions 和用户 prompt 不同：
            # - instructions 是 Agent 的长期规则。
            # - prompt 是用户每次运行时输入的问题。
            "You are a concise finance learning assistant.",
            "Explain concepts with concrete examples.",
            "Do not provide investment advice or pretend to know live market data.",
        ],
        # markdown=True 会让模型更倾向于输出 Markdown，终端展示更清晰。
        markdown=True,
        # AGNO_DEBUG=1/true/yes 时打开 Agno 调试输出，便于观察请求过程。
        debug_mode=os.getenv("AGNO_DEBUG", "").lower() in {"1", "true", "yes"},
    )


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="Run the first minimal Agno Agent demo."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        # 没有传入 prompt 时，使用一个默认问题，保证直接运行脚本也能看到效果。
        default="用三点说明 Agno Agent 和普通 LLM 调用有什么区别。",
        help="Prompt to send to the agent.",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        # 默认使用流式输出；加上 --no-stream 后一次性打印完整回答。
        help="Disable streaming output.",
    )
    return parser.parse_args()


def main() -> None:
    # 1. 读取命令行参数。
    args = parse_args()

    # 2. 构建 Agent。这个步骤只负责配置 Agent，还没有向模型发送请求。
    agent = build_agent()

    # 3. 向 Agent 发送 prompt，并把模型回答打印到终端。
    #
    # `print_response` 是 Agno 提供的最简单终端调用方式：
    # prompt 输入 -> Agent 调用模型 -> 终端输出回答。
    agent.print_response(args.prompt, stream=not args.no_stream)


# 只有直接执行 `python hello_agent.py` 时才运行 main()。
# 如果未来别的 demo import 这个文件，main() 不会自动执行。
if __name__ == "__main__":
    main()
