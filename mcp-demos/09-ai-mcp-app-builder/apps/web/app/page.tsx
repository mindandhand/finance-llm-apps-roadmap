"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import { CopilotChat } from "@copilotkit/react-core/v2";
import { useCopilotChat } from "@copilotkit/react-core";
import type { WorkspaceInfo } from "@/lib/workspace/types";
import { TextMessage, Role } from "@copilotkit/runtime-client-gql";
import { BuilderAgentProvider } from "./components/BuilderAgentProvider";
import { McpServerManager } from "./components/McpServerManager";
import { ToolDetailModal } from "./components/ToolDetail";
import { ChatSuggestions } from "./components/ChatSuggestions";
import { LoadingSpinner, EmptyState } from "./components/shared";
import { useMcpServers } from "./components/CopilotKitProvider";
import {
  useMcpIntrospect,
  type ServerIntrospection,
} from "./hooks/useMcpIntrospect";
import {
  useToolConfigStore,
  type MergedToolConfig,
} from "./hooks/useToolConfigStore";
import {
  getHeaderDocsUrl,
  getHeaderLogoUrl,
  getHeaderPrimaryCtaLabel,
  getHeaderSecondaryCtaUrl,
} from "./constants/branding";
import copilotKitLogo from "./image.png";

// ---------------------------------------------------------------------------
// 模块级常量：保持引用稳定，避免重复渲染
// ---------------------------------------------------------------------------

const CHAT_LABELS = {
  chatInputPlaceholder: "让我构建一个组件或添加 MCP Server……",
  welcomeMessageText:
    "你好！我是 MCP App 构建助手。请在侧边栏添加 MCP Server，或让我构建一个组件。",
} as const;

// ---------------------------------------------------------------------------
// 主页面：管理顶层状态，并将渲染委托给 StudioView
// ---------------------------------------------------------------------------

export default function CopilotKitPage() {
  const [selectedTool, setSelectedTool] = useState<string>("");
  const { appendMessage } = useCopilotChat();

  const { servers } = useMcpServers();
  const {
    allTools,
    data: serverData,
    loading,
    refresh,
  } = useMcpIntrospect(servers);
  const toolStore = useToolConfigStore(allTools);

  const activeTool =
    toolStore.mergedTools.find((t) => t.toolName === selectedTool) ??
    toolStore.mergedTools[0] ??
    null;

  const handleTryPrompt = (prompt: string) => {
    appendMessage(new TextMessage({ content: prompt, role: Role.User }));
  };

  return (
    <main className="app-shell flex h-screen w-screen flex-col overflow-hidden p-2 sm:p-3 md:p-4">
      <TopBar />

      <div className="mx-auto min-h-0 w-full max-w-[1800px] flex-1">
        <StudioView
          mergedTools={toolStore.mergedTools}
          activeTool={activeTool}
          selectedTool={selectedTool || activeTool?.toolName || ""}
          onSelectTool={setSelectedTool}
          onTryPrompt={handleTryPrompt}
          loading={loading}
          serverData={serverData}
          onRefresh={refresh}
          toolStore={toolStore}
        />
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// 顶部栏
// ---------------------------------------------------------------------------

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden
    >
      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
    </svg>
  );
}

function TopBar() {
  const docsUrl = getHeaderDocsUrl();
  const logoUrl = getHeaderLogoUrl();
  const primaryLabel = getHeaderPrimaryCtaLabel();
  const secondaryUrl = getHeaderSecondaryCtaUrl();

  return (
    <nav className="mx-auto mb-3 flex w-full max-w-[1800px] shrink-0 items-center justify-between gap-3">
      <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
        <span className="shrink-0 text-sm font-semibold leading-none tracking-tight text-slate-900 sm:text-base">
          MCP App 构建助手
        </span>
        <span
          className="hidden h-4 w-px shrink-0 bg-slate-200 sm:block"
          aria-hidden
        />
        <div className="flex min-w-0 items-center gap-1.5 sm:gap-2">
          <span className="shrink-0 text-[10px] font-medium text-slate-500 sm:text-xs">
            技术支持
          </span>
          <a
            href={logoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-w-0 shrink rounded-md outline-offset-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-400"
            aria-label="CopilotKit：打开 GitHub 仓库"
          >
            <Image
              src={copilotKitLogo}
              alt=""
              width={copilotKitLogo.width}
              height={copilotKitLogo.height}
              className="h-[18px] w-auto max-w-[min(160px,38vw)] sm:h-[22px] sm:max-w-[200px]"
              priority
              sizes="(max-width: 640px) 38vw, 200px"
            />
          </a>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
        <a
          href={docsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-full border border-indigo-200 bg-indigo-50/90 px-2.5 py-1 text-[11px] font-medium text-indigo-800 shadow-sm transition hover:border-indigo-300 hover:bg-indigo-100 sm:px-3"
        >
          {primaryLabel}
        </a>
        <a
          href={secondaryUrl}
          target="_blank"
          rel="noopener noreferrer"
          title="在 GitHub 查看源代码"
          aria-label="在 GitHub 查看源代码"
          className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white/90 text-slate-600 shadow-sm transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 sm:h-9 sm:w-9"
        >
          <GitHubIcon className="h-[18px] w-[18px] sm:h-5 sm:w-5" />
        </a>
      </div>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// 工作区：左侧边栏和对话区组成的双栏布局
// 左侧边栏：上方显示 Server 和工具列表，下方显示工具预览及 Prompt
// ---------------------------------------------------------------------------

function StudioView({
  mergedTools,
  activeTool,
  selectedTool,
  onSelectTool,
  onTryPrompt,
  loading,
  serverData,
  onRefresh,
  toolStore,
}: {
  mergedTools: MergedToolConfig[];
  activeTool: MergedToolConfig | null;
  selectedTool: string;
  onSelectTool: (name: string) => void;
  onTryPrompt: (prompt: string) => void;
  loading: boolean;
  serverData: ServerIntrospection[];
  onRefresh: () => void;
  toolStore: ReturnType<typeof useToolConfigStore>;
}) {
  const { servers, setServers } = useMcpServers();
  const [mobileTab, setMobileTab] = useState<"chat" | "tools">("chat");
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceInfo | null>(
    null,
  );
  /** 在详情弹窗中打开工具，让侧边栏列表保持紧凑。 */
  const [detailTool, setDetailTool] = useState<MergedToolConfig | null>(null);

  /** 与 globals.css 的 @media (min-width: 768px) 一致，避免挂载两个 CopilotChat 树。 */
  const [mdUp, setMdUp] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const apply = () => setMdUp(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  // 挂载时从 localStorage 恢复最近的工作区，避免每次刷新页面都重新创建 E2B 沙箱
  useEffect(() => {
    try {
      const raw = localStorage.getItem("mcp_active_workspace");
      if (!raw) return;
      const { workspaceId, endpoint, serverId } = JSON.parse(raw) as {
        workspaceId?: string;
        endpoint?: string;
        serverId?: string;
      };
      if (!workspaceId || !endpoint) return;

      fetch("/api/workspace/info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspaceId }),
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((info) => {
          if (!info) {
            localStorage.removeItem("mcp_active_workspace");
            return;
          }
          const liveEndpoint: string = info.endpoint ?? endpoint;
          setActiveWorkspace({
            workspaceId,
            endpoint: liveEndpoint,
            status: "running",
            path: "/home/user/workspace",
          });
          setServers((prev) => {
            if (prev.some((s) => s.endpoint === liveEndpoint)) return prev;
            return [
              ...prev,
              { endpoint: liveEndpoint, serverId: serverId ?? "workspace" },
            ];
          });
        })
        .catch(() => localStorage.removeItem("mcp_active_workspace"));
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 移动端和桌面端共用的侧边栏内容
  const sidebarContent = (
    <>
      {/* Server：每个 Server 的错误和重新连接入口都显示在列表中 */}
      <section className="shrink-0 rounded-2xl border border-slate-200 bg-white p-3">
        <McpServerManager
          activeWorkspace={activeWorkspace}
          serverStatuses={serverData}
          onReconnect={onRefresh}
          globalLoading={loading}
        />
      </section>

      {/* 工具列表使用紧凑行，完整详情显示在弹窗中 */}
      <section className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <h3 className="mb-2 shrink-0 text-xs font-semibold uppercase tracking-wide text-slate-500">
          工具
        </h3>

        {loading && mergedTools.length === 0 && <LoadingSpinner />}

        <ul className="min-h-0 flex-1 space-y-1.5 overflow-y-auto pr-1">
          {mergedTools.map((t) => {
            const isSelected = selectedTool === t.toolName;
            return (
              <li key={t.toolName}>
                <button
                  type="button"
                  onClick={() => {
                    onSelectTool(t.toolName);
                    setDetailTool(t);
                    setMobileTab("tools");
                  }}
                  className={`flex w-full items-center gap-2 rounded-xl border px-3 py-2.5 text-left transition ${
                    isSelected
                      ? "border-emerald-300 bg-emerald-50/60 ring-1 ring-emerald-200/80"
                      : "border-slate-200 bg-white/90 hover:border-slate-300 hover:bg-slate-50"
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="block truncate text-sm font-medium text-slate-900">
                        {t.toolName}
                      </span>
                      {t.hasUI && (
                        <span className="shrink-0 rounded px-1 py-0.5 text-[9px] font-semibold bg-emerald-100 text-emerald-700">
                          UI
                        </span>
                      )}
                      {t.source === "local" && (
                        <span className="shrink-0 rounded px-1 py-0.5 text-[9px] font-semibold bg-blue-100 text-blue-700">
                          本地
                        </span>
                      )}
                      {t.isModified && (
                        <span className="shrink-0 rounded px-1 py-0.5 text-[9px] font-semibold bg-amber-100 text-amber-700">
                          已修改
                        </span>
                      )}
                    </div>
                    <span className="block truncate text-[11px] text-slate-500">
                      {t.description}
                    </span>
                  </div>
                  <svg
                    className="h-4 w-4 shrink-0 text-slate-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    aria-hidden
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                </button>
              </li>
            );
          })}
        </ul>

        {!loading && mergedTools.length === 0 && (
          <EmptyState message="暂无工具。请添加 MCP Server，或让 Agent 创建一个。" />
        )}
      </section>
    </>
  );

  const chatPanel = (
    <section className="glass-panel flex min-h-0 flex-1 flex-col rounded-2xl p-3 sm:p-4">
      <div className="mb-2 shrink-0">
        <div className="mb-1.5 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-900">Agent</h2>
          <p className="hidden text-xs text-slate-500 sm:block">
            {activeTool
              ? `当前工具：${activeTool.toolName}——可以要求 Agent 使用或修改它`
              : "请选择工具，或让 Agent 创建一个"}
          </p>
        </div>
      </div>
      <div className="chat-container min-h-0 flex-1 overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
        <CopilotChat className="h-full w-full" labels={CHAT_LABELS} />
      </div>
    </section>
  );

  return (
    <>
      <ToolDetailModal
        tool={detailTool}
        open={detailTool !== null}
        onClose={() => setDetailTool(null)}
        onTryPrompt={(p) => {
          onTryPrompt(p);
          setMobileTab("chat");
        }}
        onPreviewDataChange={(data) => {
          if (detailTool) {
            toolStore.updateConfig(detailTool.toolName, { previewData: data });
            setDetailTool({ ...detailTool, previewData: data });
          }
        }}
      />
      <BuilderAgentProvider
        activeTool={activeTool}
        allToolNames={mergedTools.map((t) => t.toolName)}
        onAddServer={(endpoint, serverId) =>
          setServers((prev) => [...prev, { endpoint, serverId }])
        }
        onRefreshServers={onRefresh}
        connectedServers={servers.map((s) => s.endpoint)}
        activeWorkspace={activeWorkspace}
        onWorkspaceChange={setActiveWorkspace}
      >
        {/*
        单一 CopilotChat：只有当前布局分支会挂载对话组件（移动端与桌面端互斥）。
        以前两个分支都会保留在 DOM 中；CSS 虽在桌面端隐藏移动端布局，但 React 仍会挂载
        两个 CopilotChat 实例，从而重复请求 POST /api/mastra-agent。
      */}
        <ChatSuggestions />
        {/* 移动端（<768px）：双标签切换；桌面端跳过内部树，避免重复挂载对话 */}
        <div className="mobile-layout flex h-full min-h-0 flex-col gap-2">
          {!mdUp && (
            <>
              <nav className="glass-panel shrink-0 rounded-2xl p-1">
                <div className="grid grid-cols-2 gap-1">
                  {(["chat", "tools"] as const).map((key) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setMobileTab(key)}
                      className={`rounded-xl px-2 py-1.5 text-[11px] font-medium capitalize transition ${
                        mobileTab === key
                          ? "bg-slate-900 text-white shadow-sm"
                          : "bg-white/70 text-slate-600 hover:bg-white hover:text-slate-900"
                      }`}
                    >
                      {key === "tools" ? "工具" : "对话"}
                    </button>
                  ))}
                </div>
              </nav>

              {mobileTab === "chat" ? (
                chatPanel
              ) : (
                <aside className="glass-panel flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto rounded-2xl p-2.5">
                  {sidebarContent}
                </aside>
              )}
            </>
          )}
        </div>

        {/* 桌面端（≥768px）：固定宽度侧边栏和自适应对话区 */}
        <div
          className="desktop-layout h-full gap-3"
          style={{
            display: "grid",
            gridTemplateColumns: "340px minmax(0,1fr)",
          }}
        >
          {mdUp && (
            <>
              <aside className="glass-panel flex min-h-0 flex-col gap-3 overflow-hidden rounded-2xl p-3">
                {sidebarContent}
              </aside>
              {chatPanel}
            </>
          )}
        </div>
      </BuilderAgentProvider>
    </>
  );
}
