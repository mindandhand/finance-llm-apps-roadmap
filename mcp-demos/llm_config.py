"""Shared OpenAI-compatible model settings for the MCP demos.

DeepSeek, Qwen, Zhipu, Moonshot, Baichuan and many local gateways expose an
OpenAI-compatible chat API. These helpers keep the demos provider-neutral while
preserving the original Agno/OpenAIChat integration.
"""

import os


DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


def get_llm_api_key() -> str | None:
    return (
        os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("LLM_API_KEY")
    )


def get_llm_base_url() -> str:
    return os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL


def get_llm_model(default: str = DEFAULT_MODEL) -> str:
    return os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL") or default


def create_agno_openai_model(openai_chat_cls, default_model: str = DEFAULT_MODEL):
    """Create an Agno OpenAIChat model with a best-effort base_url override."""

    api_key = get_llm_api_key()
    model_id = get_llm_model(default_model)
    base_url = get_llm_base_url()

    try:
        return openai_chat_cls(id=model_id, api_key=api_key, base_url=base_url)
    except TypeError:
        return openai_chat_cls(id=model_id, api_key=api_key)
