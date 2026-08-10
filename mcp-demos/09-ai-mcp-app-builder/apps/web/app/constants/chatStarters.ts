export type ChatStarterPrompt = {
  title: string;
  message: string;
};

/** 四个起始 Prompt：三个范围明确的构建演示和一个 Excalidraw 测试，可通过 `NEXT_PUBLIC_CHAT_STARTER_PROMPTS` 覆盖。 */
const DEFAULT_PROMPTS: ChatStarterPrompt[] = [
  { title: "井字棋", message: "创建一个井字棋游戏" },
  {
    title: "小费计算器",
    message:
      "创建一个单组件小费计算器：输入账单金额、选择预设小费比例、设置分摊人数，并显示每人的小费和总金额。只使用 React 和现有模板 CSS，不要添加新的 npm 包。",
  },
  {
    title: "骰子模拟器",
    message:
      "创建一个骰子模拟组件：可选择骰子数量（1–6）和面数（如 4、6、8、10、12、20），提供投掷按钮，并显示每个骰子的结果和总和。只使用 React 和现有模板，不使用图表或绘图库。",
  },
  {
    title: "试用 Excalidraw",
    message:
      "使用 Excalidraw MCP Server 创建一个简单流程图：开始 → 处理 → 判断（是/否分支）→ 结束，并显示结果。",
  },
];

/**
 * CopilotChat v2 的对话建议标签，参见 `ChatSuggestions.tsx`。
 * 可用 `NEXT_PUBLIC_CHAT_STARTER_PROMPTS` 覆盖，值为 `{ "title", "message" }` JSON 数组。
 */
export function getChatStarterPrompts(): ChatStarterPrompt[] {
  const raw = process.env.NEXT_PUBLIC_CHAT_STARTER_PROMPTS;
  if (typeof raw !== "string" || !raw.trim()) {
    return DEFAULT_PROMPTS;
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed) || parsed.length === 0) {
      return DEFAULT_PROMPTS;
    }
    const out: ChatStarterPrompt[] = [];
    for (const item of parsed) {
      if (!item || typeof item !== "object") continue;
      const rec = item as Record<string, unknown>;
      const title = rec.title;
      const message = rec.message;
      if (typeof title !== "string" || typeof message !== "string") continue;
      const t = title.trim();
      const m = message.trim();
      if (!t || !m) continue;
      out.push({ title: t, message: m });
    }
    return dedupeStarterPrompts(out.length > 0 ? out : DEFAULT_PROMPTS);
  } catch {
    return DEFAULT_PROMPTS;
  }
}

/** 去除重复的标题和消息组合，避免错误合并环境变量时界面重复显示标签。 */
function dedupeStarterPrompts(
  prompts: ChatStarterPrompt[],
): ChatStarterPrompt[] {
  const seen = new Set<string>();
  const result: ChatStarterPrompt[] = [];
  for (const p of prompts) {
    const key = `${p.title.trim()}\n${p.message.trim()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(p);
  }
  return result;
}
