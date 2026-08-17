"use client";

import { useCopilotAction, useCopilotReadable } from "@copilotkit/react-core";
import type { MergedToolConfig } from "../hooks/useToolConfigStore";
import type { WorkspaceInfo } from "@/lib/workspace/types";
import { RegisterMcpTestPromptsAction } from "./McpTestPromptsAction";

// ---------------------------------------------------------------------------
// BuilderAgentProvider
//
// 注册仅在前端运行的 CopilotKit Action，用于更新 React/UI 状态。
// E2B 创建、文件 I/O 和命令执行等异步重任务均由
// app/api/mastra-agent/route.ts 中的 Mastra Agent 后端工具完成。
// app/api/copilotkit/route.ts 是保留的旧实现，不是当前页面的默认链路。
// ---------------------------------------------------------------------------

interface BuilderAgentProviderProps {
  activeTool: MergedToolConfig | null;
  allToolNames: string[];
  onAddServer: (endpoint: string, serverId?: string) => void;
  onRefreshServers: () => void;
  connectedServers: string[];
  activeWorkspace: WorkspaceInfo | null;
  onWorkspaceChange: (ws: WorkspaceInfo | null) => void;
  children: React.ReactNode;
}

export function BuilderAgentProvider({
  activeTool,
  allToolNames,
  onAddServer,
  onRefreshServers,
  connectedServers,
  activeWorkspace,
  onWorkspaceChange,
  children,
}: BuilderAgentProviderProps) {
  // ── 可读上下文 ──────────────────────────────────────────────────────────
  // 作为大语言模型的实时上下文注入每个 Agent 请求。这里只传递完成决策所需的
  // 摘要，不把完整 HTML 或全部文件内容塞入上下文，避免无意义地占用模型窗口。

  useCopilotReadable({
    description:
      "当前 E2B 工作区。null 表示尚未创建沙箱，需要先调用后端 provision_workspace 工具。",
    value: activeWorkspace ?? {
      status: "not-provisioned",
      message:
        "调用后端工具 provision_workspace(name) 创建配置的工作区沙箱。",
    },
  });

  useCopilotReadable({
    description: "构建器中当前选中的工具",
    value: activeTool
      ? {
          toolName: activeTool.toolName,
          source: activeTool.source,
          description: activeTool.description,
          inputSchema: activeTool.inputSchema,
          previewData: activeTool.previewData,
          hasUI: activeTool.hasUI,
          htmlSourceLength: activeTool.htmlSource?.length ?? 0,
          htmlSourcePreview: activeTool.htmlSource?.slice(0, 500) ?? null,
          isModified: activeTool.isModified,
        }
      : { toolName: null, message: "尚未选择工具" },
  });

  useCopilotReadable({
    description: "构建器中所有可用工具的名称",
    value: allToolNames,
  });

  useCopilotReadable({
    description:
      "当前连接到 Studio 的 MCP Server，每一项都是 Endpoint URL。",
    value: connectedServers,
  });

  // ── UI 状态前端 Action ───────────────────────────────────────────────────
  // 这些 Action 只更新 React 状态，不执行 E2B I/O。典型顺序是：后端创建或
  // 重启 Server → Agent 调用前端 Action → 页面连接 Endpoint 并刷新工具列表。

  useCopilotAction({
    name: "add_mcp_server",
    description:
      "将新的 MCP Server 连接到 Studio 侧边栏。" +
      "在 provision_workspace 返回沙箱 Endpoint 后调用。",
    parameters: [
      {
        name: "endpoint",
        type: "string",
        description:
          "完整 MCP Endpoint URL，例如 https://sandbox-abc.e2b.app/mcp",
        required: true,
      },
      {
        name: "serverId",
        type: "string",
        description: "简短标识，例如 weather-widget",
        required: false,
      },
    ],
    handler: async ({ endpoint, serverId }) => {
      // 幂等判断可防止模型重试同一 Action 时重复添加侧边栏条目。
      if (connectedServers.includes(endpoint as string)) {
        return `Server“${endpoint}”已连接。`;
      }
      onAddServer(endpoint as string, serverId as string | undefined);
      // 保存 serverId，以便恢复会话
      try {
        const saved = JSON.parse(
          localStorage.getItem("mcp_active_workspace") ?? "{}",
        );
        localStorage.setItem(
          "mcp_active_workspace",
          JSON.stringify({ ...saved, serverId: serverId ?? "workspace" }),
        );
      } catch {}
      return `已连接位于“${endpoint}”的 MCP Server${serverId ? `（${serverId}）` : ""}。`;
    },
  });

  useCopilotAction({
    name: "set_active_workspace",
    description:
      "在 UI 中注册已创建的工作区，并在 Server 条目显示状态标记。" +
      "provision_workspace 完成后立即调用。",
    parameters: [
      {
        name: "workspaceId",
        type: "string",
        description: "provision_workspace 返回的沙箱 ID",
        required: true,
      },
      {
        name: "endpoint",
        type: "string",
        description: "沙箱的 MCP Endpoint URL",
        required: true,
      },
    ],
    handler: async ({ workspaceId, endpoint }) => {
      // 工作区信息同时写入 React 状态和 localStorage：前者驱动当前页面，后者
      // 用于刷新后的重连。这里只保存标识与 Endpoint，不保存 E2B 凭证。
      onWorkspaceChange({
        workspaceId: workspaceId as string,
        endpoint: endpoint as string,
        status: "running",
        path: "/home/user/workspace",
      });
      // 保存工作区以恢复会话，下次加载页面时直接重连，无需重新创建
      try {
        const saved = JSON.parse(
          localStorage.getItem("mcp_active_workspace") ?? "{}",
        );
        localStorage.setItem(
          "mcp_active_workspace",
          JSON.stringify({
            ...saved,
            workspaceId: workspaceId as string,
            endpoint: endpoint as string,
          }),
        );
      } catch {}
      return `工作区已在 UI 中注册（sandboxId：${workspaceId}）。`;
    },
  });

  useCopilotAction({
    name: "refresh_mcp_tools",
    description:
      "重新获取所有已连接 MCP Server 的能力，使新工具显示在侧边栏。" +
      "重新构建开发 Server 并等待约 3–5 秒后调用。",
    parameters: [],
    handler: async () => {
      onRefreshServers();
      return "正在刷新所有已连接 MCP Server 的工具，新工具稍后会显示。";
    },
  });

  return (
    <>
      <RegisterMcpTestPromptsAction />
      {children}
    </>
  );
}
