"use client";

import { useMemo } from "react";
import { useCopilotChatSuggestions } from "@copilotkit/react-core";
import { getChatStarterPrompts } from "../constants/chatStarters";

/**
 * 向 CopilotKit v2 注册起始 Prompt，让 CopilotChat 显示建议标签。
 * 使用 `NEXT_PUBLIC_CHAT_STARTER_PROMPTS`（JSON）配置，详见 `.env.example`；
 * 默认包含三个构建演示和一个 Excalidraw 测试。
 */
export function ChatSuggestions() {
  const suggestions = useMemo(() => getChatStarterPrompts(), []);

  useCopilotChatSuggestions(
    {
      available: "before-first-message",
      suggestions,
    },
    [suggestions],
  );

  return null;
}
