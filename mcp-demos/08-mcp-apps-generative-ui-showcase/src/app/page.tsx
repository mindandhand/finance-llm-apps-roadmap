"use client";

import {
  CopilotKitProvider,
  CopilotSidebar,
  CopilotPopup,
  useAgent,
  useCopilotKit,
  useCopilotChatConfiguration,
} from "@copilotkit/react-core/v2";
import { useMediaQuery } from "@/hooks/use-media-query";
import { randomUUID, DEFAULT_AGENT_ID } from "@copilotkit/shared";
import { useCallback } from "react";

export const dynamic = "force-dynamic";

// 内联 Lucide 风格 SVG 图标，避免外部资源影响稳定性
const Icons = {
  plane: (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z" />
    </svg>
  ),
  building: (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect width="16" height="20" x="4" y="2" rx="2" ry="2" />
      <path d="M9 22v-4h6v4" />
      <path d="M8 6h.01" />
      <path d="M16 6h.01" />
      <path d="M12 6h.01" />
      <path d="M12 10h.01" />
      <path d="M12 14h.01" />
      <path d="M16 10h.01" />
      <path d="M16 14h.01" />
      <path d="M8 10h.01" />
      <path d="M8 14h.01" />
    </svg>
  ),
  trendingUp: (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
      <polyline points="16 7 22 7 22 13" />
    </svg>
  ),
  layoutGrid: (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect width="7" height="7" x="3" y="3" rx="1" />
      <rect width="7" height="7" x="14" y="3" rx="1" />
      <rect width="7" height="7" x="14" y="14" rx="1" />
      <rect width="7" height="7" x="3" y="14" rx="1" />
    </svg>
  ),
  sparkles: (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" />
      <path d="M20 3v4" />
      <path d="M22 5h-4" />
      <path d="M4 17v2" />
      <path d="M5 18H3" />
    </svg>
  ),
};

const apps = [
  {
    id: "flights",
    name: "机票预订",
    description:
      "搜索航班、选择座位并通过完整向导完成预订",
    icon: Icons.plane,
    iconClass: "flights",
    prompts: [
      "为 2 名乘客预订 1 月 20 日从纽约到洛杉矶的航班",
      "查找下周从伦敦到巴黎的航班",
    ],
  },
  {
    id: "hotels",
    name: "酒店预订",
    description:
      "浏览酒店、比较房型并预订世界各地的住宿",
    icon: Icons.building,
    iconClass: "hotels",
    prompts: [
      "为 2 位客人查找 1 月 15 日至 18 日的巴黎酒店",
      "查找东京可住 3 晚的酒店",
    ],
  },
  {
    id: "trading",
    name: "投资模拟器",
    description:
      "创建投资组合、执行交易并通过实时图表跟踪表现",
    icon: Icons.trendingUp,
    iconClass: "trading",
    prompts: [
      "创建一个 10,000 美元、侧重科技股的投资组合",
      "创建一个保守型红利投资组合",
    ],
  },
  {
    id: "kanban",
    name: "看板",
    description:
      "通过拖放卡片、分栏和任务跟踪管理项目",
    icon: Icons.layoutGrid,
    iconClass: "kanban",
    prompts: [
      "为我的软件项目创建看板",
      "创建营销活动看板",
    ],
  },
];

export default function MCPAppsDemo() {
  return (
    <CopilotKitProvider runtimeUrl="/api/copilotkit" showDevConsole="auto">
      <AppLayout />
    </CopilotKitProvider>
  );
}

function AppLayout() {
  const { agent } = useAgent({ agentId: DEFAULT_AGENT_ID });
  const { copilotkit } = useCopilotKit();
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const config = useCopilotChatConfiguration();

  // 发送消息并运行 Agent
  const sendMessage = useCallback(
    async (message: string) => {
      config?.setModalOpen(true);
      agent.addMessage({
        id: randomUUID(),
        role: "user",
        content: message,
      });
      try {
        await copilotkit.runAgent({ agent });
      } catch (error) {
        console.error("Agent 运行失败：", error);
      }
    },
    [agent, copilotkit, config],
  );

  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* 动态抽象背景 */}
      <div className="abstract-bg">
        <div className="blob-3" />
      </div>

      {/* 主体内容 */}
      <main className="relative z-10 mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-6 md:px-6 md:py-12">
        {/* 首屏区域 */}
        <section className="text-center space-y-6">
          <div className="inline-flex items-center gap-2 glass-subtle px-4 py-2 rounded-full text-sm text-[var(--color-text-secondary)]">
            {Icons.sparkles}
            <span>MCP Apps 演示</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-[var(--color-text-primary)]">
            对话中的交互式 AI 应用
          </h1>
          <p className="max-w-2xl mx-auto text-lg text-[var(--color-text-secondary)]">
            丰富的 UI 组件可直接在对话侧边栏中渲染，并通过支持双向通信的
            MCP Apps 扩展（SEP-1865）运行。
          </p>

          {/* 文档按钮 */}
          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <a
              href="https://go.copilotkit.ai/mcp-apps"
              target="_blank"
              rel="noopener noreferrer"
              className="docs-btn docs-btn-primary"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
              </svg>
              了解更多
            </a>
            <a
              href="https://docs.copilotkit.ai/generative-ui/mcp-apps"
              target="_blank"
              rel="noopener noreferrer"
              className="docs-btn docs-btn-secondary"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
              </svg>
              文档
            </a>
          </div>
        </section>

        {/* 应用卡片网格 */}
        <section className="grid gap-6 md:grid-cols-2">
          {apps.map((app) => (
            <div key={app.id} className="app-card">
              <div className={`app-card-icon ${app.iconClass}`}>{app.icon}</div>
              <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2">
                {app.name}
              </h3>
              <p className="text-sm text-[var(--color-text-secondary)] mb-4">
                {app.description}
              </p>
              <div className="flex flex-wrap gap-2">
                {app.prompts.map((prompt, i) => (
                  <button
                    key={i}
                    className="prompt-pill text-xs cursor-pointer hover:scale-105 transition-transform"
                    onClick={() => sendMessage(prompt)}
                  >
                    &ldquo;{prompt}&rdquo;
                  </button>
                ))}
              </div>
            </div>
          ))}
        </section>

        {/* 原理说明 */}
        <section className="glass-card">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-gradient-to-br from-[var(--color-lilac)] to-[var(--color-mint)] flex items-center justify-center text-white">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="12" cy="12" r="10" />
                <path d="M12 16v-4" />
                <path d="M12 8h.01" />
              </svg>
            </div>
            <div>
              <h4 className="font-semibold text-[var(--color-text-primary)] mb-1">
                工作原理
              </h4>
              <p className="text-sm text-[var(--color-text-secondary)]">
                每个应用都在对话中的沙箱 iframe 内渲染。UI 通过 postMessage
                使用 JSON-RPC 与 MCP Server 通信，从而支持选择航班座位、
                预订酒店房间或执行交易等实时交互。
              </p>
              <p className="mt-3 text-xs text-[var(--color-text-tertiary)]">
                MCP Server:{" "}
                <code className="glass-subtle px-2 py-0.5 rounded text-[var(--color-text-secondary)]">
                  cd mcp-server && npm run dev
                </code>
              </p>
            </div>
          </div>
        </section>
      </main>

      {/* CopilotKit 对话界面：桌面端使用侧边栏，移动端使用弹窗 */}
      {isDesktop ? (
        <CopilotSidebar defaultOpen={true} width="50%" />
      ) : (
        <CopilotPopup
          defaultOpen={false}
          labels={{
            modalHeaderTitle: "MCP Apps 助手",
            chatInputPlaceholder: "今天想尝试什么？",
          }}
        />
      )}
    </div>
  );
}
