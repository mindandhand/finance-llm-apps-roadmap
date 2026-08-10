"""对话式 Agent 的轻量会话环境。

原课程通过 Google ADK Runner/Session 保存消息与共享状态。这里使用框架无关的
数据结构提供同等语义，再由 LangGraph Checkpointer 负责流程恢复。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConversationMessage:
    """框架无关的最小对话消息，便于保存与测试。"""
    role: str
    content: str


@dataclass
class ConversationSession:
    """保存多轮消息和跨 Agent 共享状态，不绑定特定 LLM SDK。"""
    messages: list[ConversationMessage] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)

    def add(self, role: str, content: str) -> ConversationMessage:
        # 仅允许常见角色，避免错误角色名污染后续模型上下文。
        if role not in {"user", "assistant", "tool"}:
            raise ValueError(f"不支持的消息角色：{role}")
        text = content.strip()
        if not text:
            raise ValueError("对话消息不能为空。")
        message = ConversationMessage(role, text)
        self.messages.append(message)
        return message

    def snapshot(self) -> dict[str, Any]:
        """返回普通 Python 数据快照，可安全交给工作流 checkpointer。"""
        return {
            "messages": [message.__dict__.copy() for message in self.messages],
            "state": deepcopy(self.state),
        }
