"use client";

import { CopilotKit } from "@copilotkit/react-core";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import { DEFAULT_SERVERS, type McpServerEntry } from "../constants/mcpServers";
import { TOOL_CALL_RENDERERS } from "./ToolCallRenderer";

// ─── MCP Server 共享状态 ─────────────────────────────────────────────────────

type ServersUpdater =
  | McpServerEntry[]
  | ((prev: McpServerEntry[]) => McpServerEntry[]);

interface McpServersContextValue {
  servers: McpServerEntry[];
  setServers: (update: ServersUpdater) => void;
}

const McpServersContext = createContext<McpServersContextValue>({
  servers: DEFAULT_SERVERS,
  setServers: () => {},
});

/**
 * 读取或更新当前 MCP Server 列表。
 *
 * Server 管理器、Agent Action 和 CopilotKit Runtime 必须共享同一份列表；否则
 * 页面虽然显示 Server 已连接，后端请求却可能仍携带旧的 Endpoint。
 */
export function useMcpServers(): McpServersContextValue {
  return useContext(McpServersContext);
}

// ─── CopilotKit Provider ──────────────────────────────────────────────────────

/**
 * MCP Server 列表的唯一数据源，同时也是 Web UI 与 Agent 后端的连接边界。
 *
 * 数据流：
 * 1. 使用 constants/mcpServers.ts 中的 DEFAULT_SERVERS 初始化；
 * 2. 侧边栏或 Agent Action 通过 useMcpServers() 增删 Server；
 * 3. Provider 把列表序列化到 `x-mcp-servers` 请求头；
 * 4. `/api/mastra-agent` 根据请求头发现工具并读取 MCP Apps UI Resource。
 *
 * 列表只保存在当前 React 会话中，不写入 localStorage。工作区恢复信息由
 * BuilderAgentProvider 单独保存，避免把短期 UI 状态与沙箱生命周期混在一起。
 */
export function DynamicCopilotKitProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [servers, setServersState] =
    useState<McpServerEntry[]>(DEFAULT_SERVERS);

  const setServers = useCallback((update: ServersUpdater) => {
    setServersState((prev) => {
      const next = typeof update === "function" ? update(prev) : update;
      console.log(
        `[CopilotKitProvider] Server list updated — ${next.length} server(s):`,
        next.map((s) => s.endpoint),
      );
      return next;
    });
  }, []);

  const headers = useMemo(() => {
    // CopilotKit 会在每次 Agent 请求中附带该 Header，因此新增沙箱 Server 后，
    // 下一轮对话无需重建 Provider 就能让后端看到最新工具集合。
    const value = JSON.stringify(
      servers.map((s) => ({
        type: "http" as const,
        url: s.endpoint,
        ...(s.serverId ? { serverId: s.serverId } : {}),
      })),
    );
    console.log(
      `[CopilotKitProvider] x-mcp-servers header updated — ${servers.length} server(s):`,
      servers.map((s) => s.endpoint),
    );
    return { "x-mcp-servers": value };
  }, [servers]);

  return (
    <McpServersContext.Provider value={{ servers, setServers }}>
      <CopilotKit
        // CopilotKit 负责聊天 UI、前端 Action 和事件渲染；实际推理由该 Mastra
        // Route 完成。保留这层 Provider 是 MCP Apps 组件能回到聊天流的关键。
        runtimeUrl="/api/mastra-agent"
        headers={headers}
        showDevConsole={false}
        renderToolCalls={TOOL_CALL_RENDERERS}
      >
        {children}
      </CopilotKit>
    </McpServersContext.Provider>
  );
}
