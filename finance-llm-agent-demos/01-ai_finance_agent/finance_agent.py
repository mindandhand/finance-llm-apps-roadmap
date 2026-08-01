import os
from pathlib import Path

from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from agno.os import AgentOS
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools
from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
SHARED_WORKSPACE_DIR = REPO_DIR.parent

for env_path in (
    APP_DIR / ".env",
    REPO_DIR / ".env",
    SHARED_WORKSPACE_DIR / ".env",
):
    load_dotenv(env_path)

model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat"))
base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")

agent = Agent(
    name="Finance Agent",
    model=DeepSeek(
        id=model_id,
        api_key=api_key,
        base_url=base_url,
    ),
    tools=[DuckDuckGoTools(), YFinanceTools()],
    instructions=[
        "Always use tables to display financial/numerical data. "
        "For text data use bullet points and small paragraphs."
    ],
    debug_mode=os.getenv("AGNO_DEBUG", "").lower() in {"1", "true", "yes"},
    markdown=True,
)

agent_os = AgentOS(agents=[agent])
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="finance_agent:app", reload=False)
