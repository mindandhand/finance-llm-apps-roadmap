"use client";

import { useCopilotAction, useCopilotChat } from "@copilotkit/react-core";
import { TextMessage, Role } from "@copilotkit/runtime-client-gql";

export type McpTestPrompt = { label: string; message: string };

function parsePrompts(raw: unknown): McpTestPrompt[] {
  if (typeof raw !== "string" || !raw.trim()) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    const out: McpTestPrompt[] = [];
    for (const item of parsed) {
      if (!item || typeof item !== "object") continue;
      const o = item as Record<string, unknown>;
      const label = o.label;
      const message = o.message;
      if (typeof label !== "string" || typeof message !== "string") continue;
      const l = label.trim();
      const m = message.trim();
      if (!l || !m) continue;
      out.push({ label: l, message: m });
    }
    return out.slice(0, 8);
  } catch {
    return [];
  }
}

function TestPromptButtons({ prompts }: { prompts: McpTestPrompt[] }) {
  const { appendMessage } = useCopilotChat();

  if (prompts.length === 0) return null;

  return (
    <div
      className="mt-2 rounded-xl border border-emerald-100 bg-emerald-50/50 px-3 py-2.5"
      data-slot="mcp-test-prompts"
    >
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-emerald-800">
        试用 MCP Server
      </p>
      <div className="flex flex-wrap gap-1.5">
        {prompts.map((p, i) => (
          <button
            key={`${p.label}-${i}`}
            type="button"
            onClick={() => {
              void appendMessage(
                new TextMessage({ content: p.message, role: Role.User }),
              );
            }}
            className="rounded-full border border-emerald-200/90 bg-white px-2.5 py-1 text-[11px] font-medium text-emerald-900 shadow-sm transition hover:bg-emerald-100"
          >
            {p.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/**
 * 注册仅在前端运行的 CopilotKit Action：Agent 调用 `show_mcp_test_prompts`，
 * 传入 `{ label, message }[]` JSON 字符串；对话界面将其渲染为可点击标签，
 * 点击后把消息追加到当前会话。
 */
export function RegisterMcpTestPromptsAction() {
  useCopilotAction({
    name: "show_mcp_test_prompts",
    description:
      "在对话中显示可点击的测试 Prompt，让用户试用已连接的 MCP Server。" +
      "工具可见后，在 refresh_mcp_tools 之后调用。" +
      '传入 prompts_json，例如 [{"label":"列出工具","message":"列出 MCP Server 的所有工具"}]。',
    parameters: [
      {
        name: "prompts_json",
        type: "string",
        description:
          '对象 JSON 数组，包含 "label"（短标签）和 "message"（点击后发送的完整文本），最多约 8 项。',
        required: true,
      },
    ],
    handler: async ({ prompts_json }) => {
      const n = parsePrompts(prompts_json).length;
      return n > 0
        ? `正在显示 ${n} 个测试 Prompt 标签，用户点击后可在对话中发送。`
        : "prompts_json 中没有有效 Prompt，请使用 {label, message} JSON 数组。";
    },
    render: ({ args }) => {
      const prompts = parsePrompts(args?.prompts_json);
      if (prompts.length === 0) {
        return (
          <p className="text-xs text-amber-800">
            无法解析测试 Prompt。请将 prompts_json 设置为包含 label 和 message
            字段的对象 JSON 数组。
          </p>
        );
      }
      return <TestPromptButtons prompts={prompts} />;
    },
  });

  return null;
}
