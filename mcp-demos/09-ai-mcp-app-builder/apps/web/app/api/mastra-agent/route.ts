import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { MastraAgent } from "@ag-ui/mastra";
import { Agent } from "@mastra/core/agent";
import { MCPClient } from "@mastra/mcp";
import { createOpenAI } from "@ai-sdk/openai";
import { NextRequest } from "next/server";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";
import { Observable } from "rxjs";
import crypto from "crypto";
import { z } from "zod";
import { getProvider } from "@/lib/workspace";
import { getDefaultMcpServers, type McpServerConfig } from "@/lib/mcp-defaults";

// 为较长的 Agent 循环预留最多 5 分钟
export const maxDuration = 300;

const mastraVerbose = process.env.MASTRA_AGENT_DEBUG === "1";
function mastraLog(...args: unknown[]) {
  if (mastraVerbose) console.log(...args);
}

function readMcpServersFromHeader(req: NextRequest): McpServerConfig[] {
  try {
    const raw = req.headers.get("x-mcp-servers");
    if (raw == null) return getDefaultMcpServers();
    const parsed = JSON.parse(raw) as McpServerConfig[];
    if (!Array.isArray(parsed)) return getDefaultMcpServers();
    mastraLog(
      "[mastra-agent] MCP servers from header:",
      parsed.map((s) => s.url),
    );
    return parsed;
  } catch {
    console.warn(
      "[mastra-agent] Failed to parse x-mcp-servers header, using defaults",
    );
    return getDefaultMcpServers();
  }
}

// ── MCP UI 工具元数据 ───────────────────────────────────────────────────────

interface McpUIToolInfo {
  toolName: string;
  resourceUri: string;
  serverConfig: McpServerConfig;
  serverHash: string;
}

function getServerHash(cfg: McpServerConfig): string {
  const raw = JSON.stringify({ type: cfg.type, url: cfg.url });
  return crypto.createHash("md5").update(raw).digest("hex");
}

async function fetchUIToolMetadata(
  servers: McpServerConfig[],
): Promise<Map<string, McpUIToolInfo>> {
  const uiTools = new Map<string, McpUIToolInfo>();

  for (const server of servers) {
    try {
      const transport =
        server.type === "sse"
          ? new SSEClientTransport(new URL(server.url))
          : new StreamableHTTPClientTransport(new URL(server.url));

      const client = new Client(
        { name: "mastra-ui-metadata", version: "1.0.0" },
        { capabilities: {} },
      );

      await client.connect(transport);
      const { tools } = await client.listTools();
      await client.close();

      const serverId = server.serverId || new URL(server.url).hostname;

      for (const tool of tools) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const meta = tool._meta as Record<string, any> | undefined;
        const resourceUri = meta?.["ui/resourceUri"];
        if (typeof resourceUri === "string") {
          // Mastra MCPClient 会为工具名称添加 serverId 前缀
          const mastraToolName = `${serverId}_${tool.name}`;
          uiTools.set(mastraToolName, {
            toolName: mastraToolName,
            resourceUri,
            serverConfig: server,
            serverHash: getServerHash(server),
          });
        }
      }
    } catch (err) {
      console.warn(
        `[mastra-agent] Failed to fetch UI metadata from ${server.url}:`,
        err,
      );
    }
  }

  mastraLog("[mastra-agent] UI tools found:", [...uiTools.keys()]);
  return uiTools;
}

// ── MCP 代理请求处理器 ───────────────────────────────────────────────────────
// CopilotKit v2 的 MCPAppsActivityRenderer 获取组件 HTML 时，会通过 Agent
// 发送代理请求，由此处理器执行

async function executeProxiedMcpRequest(
  serverConfig: McpServerConfig,
  method: string,
  params?: Record<string, unknown>,
): Promise<unknown> {
  const transport =
    serverConfig.type === "sse"
      ? new SSEClientTransport(new URL(serverConfig.url))
      : new StreamableHTTPClientTransport(new URL(serverConfig.url));

  const client = new Client(
    { name: "mastra-mcp-proxy", version: "1.0.0" },
    {
      capabilities: {
        extensions: {
          "io.modelcontextprotocol/ui": { mimeTypes: ["text/html+mcp"] },
        },
      },
    },
  );

  try {
    await client.connect(transport);
    switch (method) {
      case "tools/call":
        return await client.callTool(
          params as { name: string; arguments?: Record<string, unknown> },
        );
      case "resources/read": {
        const result = await client.readResource(params as { uri: string });
        // 调整组件 HTML，使其可在受 CSP 保护的沙箱 iframe 中渲染：
        // 1. 从 <base> 标签提取内部 Origin，例如 http://localhost:3109
        // 2. 删除会被 CSP base-uri 'self' 阻止的 <base> 标签；JS/CSS 内联且图片
        //    使用 __mcpPublicUrl 时也不再需要该标签
        // 3. 将剩余内部 Origin 引用改写为外部 Endpoint Origin
        const serverOrigin = new URL(serverConfig.url).origin;
        if (Array.isArray(result.contents)) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          result.contents = result.contents.map((c: any) => {
            if (typeof c.text === "string") {
              let html = c.text;
              const baseTagMatch = html.match(/<base\s+href="([^"]*)"[^>]*>/i);
              if (baseTagMatch) {
                try {
                  const internalOrigin = new URL(baseTagMatch[1]).origin;
                  html = html.replace(/<base\b[^>]*>/gi, "");
                  if (internalOrigin !== serverOrigin) {
                    html = html.replaceAll(internalOrigin, serverOrigin);
                  }
                } catch {
                  /* ignore */
                }
              }
              return { ...c, text: html };
            }
            return c;
          });
        }
        return result;
      }
      case "notifications/message":
        await client.notification({
          method: "notifications/message",
          params: params as Record<string, unknown>,
        });
        return { success: true };
      case "ping":
        return await client.ping();
      default:
        throw new Error(`MCP method not allowed for UI proxy: ${method}`);
    }
  } finally {
    await client.close();
  }
}

// ── AG-UI 函数中间件：ACTIVITY_SNAPSHOT 与代理请求 ───────────────────────────
// 在 AG-UI Observable 层而非 SSE 层运行，使事件正确流经 CopilotKit v2
// 管线并触发 MCPAppsActivityRenderer

function createMcpUIMiddleware(
  mcpServers: McpServerConfig[],
  uiTools: Map<string, McpUIToolInfo>,
) {
  // 为代理请求构建 Server 查询映射
  const serverById = new Map<string, McpServerConfig>();
  const serverByHash = new Map<string, McpServerConfig>();
  for (const s of mcpServers) {
    const hash = getServerHash(s);
    serverByHash.set(hash, s);
    if (s.serverId) serverById.set(s.serverId, s);
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (input: any, next: { run: (input: any) => Observable<any> }) => {
    // ── 处理 MCP 代理请求（MCPAppsActivityRenderer 获取 HTML）──
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const proxiedReq = input.forwardedProps?.__proxiedMCPRequest as any;
    if (proxiedReq) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return new Observable<any>((subscriber) => {
        // 查找 Server 配置
        let server: McpServerConfig | undefined;
        if (proxiedReq.serverId) server = serverById.get(proxiedReq.serverId);
        if (!server && proxiedReq.serverHash)
          server = serverByHash.get(proxiedReq.serverHash);

        const runId = input.runId;

        subscriber.next({
          type: "RUN_STARTED",
          runId,
          threadId: input.threadId,
        });

        if (!server) {
          subscriber.next({
            type: "RUN_FINISHED",
            runId,
            threadId: input.threadId,
            result: {
              error: `Unknown MCP server: ${proxiedReq.serverId || proxiedReq.serverHash}`,
            },
          });
          subscriber.complete();
          return;
        }

        executeProxiedMcpRequest(server, proxiedReq.method, proxiedReq.params)
          .then((result) => {
            subscriber.next({
              type: "RUN_FINISHED",
              runId,
              threadId: input.threadId,
              result,
            });
            subscriber.complete();
          })
          .catch((err) => {
            subscriber.next({
              type: "RUN_FINISHED",
              runId,
              threadId: input.threadId,
              result: { error: String(err) },
            });
            subscriber.complete();
          });
      });
    }

    // ── 普通请求：运行 Agent、拦截工具结果并发出 ACTIVITY_SNAPSHOT ──
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return new Observable<any>((subscriber) => {
      const toolNameByCallId = new Map<string, string>();
      const toolArgsByCallId = new Map<string, string>();
      // 修复 React Key 重复问题（根因分析）：
      // Mastra 对 TOOL_CALL_START.parentMessageId 和所有 TEXT_MESSAGE_* 事件复用
      // 同一个 messageId。CopilotKit 会分别从两类事件创建消息，导致相同 ID 出现两次，
      // 进而触发消息和 custom Block 的重复 Key 错误。
      //
      // 处理策略：
      // 1. 记录已发出的每个 messageId 或 parentMessageId。
      // 2. TEXT_MESSAGE_* 的 messageId 与已见 parentMessageId 冲突时重新映射。
      // 3. TOOL_CALL_START 的 parentMessageId 已发出时重新映射，避免创建重复消息。
      const usedAsParentId = new Set<string>();
      const currentTextRemap = new Map<string, string>(); // original ID → current remap for this text msg
      const emittedMessageIds = new Set<string>(); // ids already sent (as messageId or parentMessageId)
      const parentRemap = new Map<string, string>(); // original parentMessageId → remapped (for TOOL_CALL_START)

      next.run(input).subscribe({
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        next: (event: any) => {
          // 记录工具调用的 parentMessageId，供 TEXT_MESSAGE 重新映射
          if (event.type === "TOOL_CALL_START" && event.parentMessageId) {
            usedAsParentId.add(event.parentMessageId);
          }

          // 重新映射与 parentMessageId 冲突的文本事件 messageId
          if (event.messageId && usedAsParentId.has(event.messageId)) {
            if (event.type === "TEXT_MESSAGE_START") {
              currentTextRemap.set(event.messageId, crypto.randomUUID());
            }
            const remapped = currentTextRemap.get(event.messageId);
            if (remapped) {
              event = { ...event, messageId: remapped };
            }
          }

          // TOOL_CALL_START 的 parentMessageId 已发出时重新映射，避免 React Key 重复
          if (event.type === "TOOL_CALL_START" && event.parentMessageId) {
            const parentId = event.parentMessageId;
            if (emittedMessageIds.has(parentId)) {
              if (!parentRemap.has(parentId)) {
                parentRemap.set(parentId, crypto.randomUUID());
              }
              event = { ...event, parentMessageId: parentRemap.get(parentId) };
            }
          }

          // 传递可能已经重新映射的事件
          subscriber.next(event);

          // 记录已发出的 ID，避免再次使用
          if (event.messageId) emittedMessageIds.add(event.messageId);
          if (event.parentMessageId)
            emittedMessageIds.add(event.parentMessageId);

          // 记录工具调用名称
          if (
            event.type === "TOOL_CALL_START" &&
            event.toolCallId &&
            event.toolCallName
          ) {
            toolNameByCallId.set(event.toolCallId, event.toolCallName);
          }

          // 累积工具调用参数
          if (
            event.type === "TOOL_CALL_ARGS" &&
            event.toolCallId &&
            event.delta
          ) {
            const prev = toolArgsByCallId.get(event.toolCallId) || "";
            toolArgsByCallId.set(event.toolCallId, prev + event.delta);
          }

          // 收到 MCP UI 工具结果时发出 ACTIVITY_SNAPSHOT
          if (event.type === "TOOL_CALL_RESULT" && event.toolCallId) {
            const toolName = toolNameByCallId.get(event.toolCallId);
            if (toolName && uiTools.has(toolName)) {
              const info = uiTools.get(toolName)!;

              let toolInput: Record<string, unknown> = {};
              try {
                toolInput = JSON.parse(
                  toolArgsByCallId.get(event.toolCallId) || "{}",
                );
              } catch {
                /* ignore parse errors */
              }

              // 包装结果以匹配 MCPAppsActivityContentSchema：
              // { content?: [{type:"text", text:"..."}], structuredContent?: any, isError?: boolean }
              let rawResult: unknown;
              try {
                rawResult = JSON.parse(event.content || "{}");
              } catch {
                rawResult = event.content || "";
              }
              const resultText =
                typeof rawResult === "string"
                  ? rawResult
                  : JSON.stringify(rawResult);
              const result = {
                content: [{ type: "text" as const, text: resultText }],
                structuredContent: rawResult,
              };

              mastraLog(
                `[mastra-agent] Emitting ACTIVITY_SNAPSHOT for: ${toolName}`,
              );
              subscriber.next({
                type: "ACTIVITY_SNAPSHOT",
                messageId: crypto.randomUUID(),
                activityType: "mcp-apps",
                content: {
                  result,
                  resourceUri: info.resourceUri,
                  serverHash: info.serverHash,
                  serverId: info.serverConfig.serverId,
                  toolInput,
                },
                replace: true,
              });
            }
          }
        },
        error: (err: unknown) => subscriber.error(err),
        complete: () => subscriber.complete(),
      });
    });
  };
}

// ── 工作区 Provider：按环境选择 Podman 或 E2B，可安全地跨请求复用 ────────────

const workspaceProvider = getProvider();

// ── 后端工具：在 Agent 循环中由 Server 端运行 ────────────────────────────────

const workspaceTools: Record<string, unknown> = {
  provision_workspace: {
    description:
      "Create an isolated workspace from the pre-built mcp-use-server template. " +
      "Returns workspaceId and endpoint. " +
      "After success, ALWAYS call add_mcp_server(endpoint, serverId) " +
      "and set_active_workspace(workspaceId, endpoint) so the UI updates.",
    parameters: z.object({
      name: z
        .string()
        .describe("Short identifier for this workspace, e.g. 'weather-widget'"),
    }),
    execute: async ({ name }: { name: string }) => {
      const info = await workspaceProvider.provision(name);

      // 自动清理默认模板工具 product-search，使工作区从空白状态开始；
      // Agent 无需了解模板默认项，构建也会更快
      try {
        const e2b = await import("e2b");
        const sandbox = await e2b.Sandbox.connect(info.workspaceId);
        const WS = "/home/user/workspace";
        let idx = await sandbox.files.read(`${WS}/index.ts`);
        const hadDefault = idx.includes("registerProductSearch");
        if (hadDefault) {
          idx = idx.replace(
            'import { register as registerProductSearch } from "./tools/product-search";\n',
            "",
          );
          idx = idx.replace("registerProductSearch(server);\n", "");
          await sandbox.files.write(`${WS}/index.ts`, idx);
          await sandbox.commands.run(
            "rm -rf resources/product-search-result tools/product-search.ts",
            { cwd: WS, timeoutMs: 5000 },
          );
          // 重启 Server，使其在 mcp-introspect 查询前移除旧工具
          await sandbox.commands.run(
            "kill $(ss -tlnp 'sport = :3109' | grep -oP 'pid=\\K[0-9]+' | head -1) 2>/dev/null; sleep 1",
            { cwd: WS, timeoutMs: 10000 },
          );
          await sandbox.commands.run("npm run dev > /tmp/dev.log 2>&1", {
            cwd: WS,
            timeoutMs: 5000,
            background: true,
          });
          mastraLog(
            "[provision_workspace] Cleaned up default template tool + restarted server",
          );
        }
      } catch (cleanupErr) {
        console.warn(
          "[provision_workspace] Template cleanup warning:",
          cleanupErr,
        );
      }

      return JSON.stringify({
        workspaceId: info.workspaceId,
        endpoint: info.endpoint,
        status: info.status,
        nextSteps: [
          `Call add_mcp_server("${info.endpoint}", "${name}") to connect the sandbox to the UI`,
          `Call set_active_workspace("${info.workspaceId}", "${info.endpoint}") to show the status badge`,
        ],
      });
    },
  },

  read_file: {
    description:
      "Read a file from the active workspace. Path is relative to workspace root " +
      "(/home/user/workspace). Use this to inspect existing code before editing.",
    parameters: z.object({
      workspaceId: z
        .string()
        .describe("Sandbox ID returned by provision_workspace"),
      path: z
        .string()
        .describe("Relative file path, e.g. 'index.ts' or 'tools/my-tool.ts'"),
    }),
    execute: async ({
      workspaceId,
      path,
    }: {
      workspaceId: string;
      path: string;
    }) => {
      return await workspaceProvider.readFile(workspaceId, path);
    },
  },

  write_file: {
    description:
      "Write (create or overwrite) a file in the active workspace. " +
      "Parent directories are created automatically. Path is relative to workspace root.",
    parameters: z.object({
      workspaceId: z.string().describe("Sandbox ID"),
      path: z
        .string()
        .describe(
          "Relative file path, e.g. 'resources/price-chart/widget.tsx'",
        ),
      content: z.string().describe("Full file content to write"),
    }),
    execute: async ({
      workspaceId,
      path,
      content,
    }: {
      workspaceId: string;
      path: string;
      content: string;
    }) => {
      await workspaceProvider.writeFile(workspaceId, path, content);
      return `Wrote ${content.length} chars to "${path}"`;
    },
  },

  edit_file: {
    description:
      "Targeted search-and-replace in a workspace file. Supports multiple edits in one call. " +
      "Each search string must match exactly (including whitespace/newlines). " +
      "Edits are applied sequentially. Prefer this over write_file for small changes.",
    parameters: z.object({
      workspaceId: z.string().describe("Sandbox ID"),
      path: z.string().describe("Relative file path"),
      edits: z
        .array(
          z.object({
            search: z.string().describe("Exact string to find in the file"),
            replace: z.string().describe("String to replace it with"),
          }),
        )
        .describe("Array of search/replace pairs to apply sequentially"),
    }),
    execute: async ({
      workspaceId,
      path,
      edits,
    }: {
      workspaceId: string;
      path: string;
      edits: Array<{ search: string; replace: string }>;
    }) => {
      const sandbox = await (await import("e2b")).Sandbox.connect(workspaceId);
      const fullPath = `/home/user/workspace/${path.replace(/^\//, "")}`;
      let content = await sandbox.files.read(fullPath);
      const results: string[] = [];
      for (const edit of edits) {
        if (!content.includes(edit.search)) {
          results.push(`SKIP: search string not found for one edit`);
          continue;
        }
        content = content.replace(edit.search, edit.replace);
        results.push(`OK`);
      }
      await sandbox.files.write(fullPath, content);
      return `Edited "${path}" — ${edits.length} edit(s): ${results.join(", ")}`;
    },
  },

  exec: {
    description:
      "Run a shell command in the active workspace root. " +
      "Use background=true for long-running processes. " +
      "Note: fuser and lsof are NOT available — use ss for port lookups.",
    parameters: z.object({
      workspaceId: z.string().describe("Sandbox ID"),
      cmd: z.string().describe("Shell command to run"),
      background: z
        .boolean()
        .optional()
        .describe(
          "Run in background and return immediately (for servers). Default: false.",
        ),
      timeoutMs: z
        .number()
        .optional()
        .describe(
          "Timeout in milliseconds for foreground commands. Default: 60000.",
        ),
    }),
    execute: async ({
      workspaceId,
      cmd,
      background,
      timeoutMs,
    }: {
      workspaceId: string;
      cmd: string;
      background?: boolean;
      timeoutMs?: number;
    }) => {
      const result = await workspaceProvider.exec(workspaceId, cmd, {
        background,
        timeoutMs,
      });
      if (result.background) return `Started in background: ${cmd}`;
      const parts: string[] = [];
      if (result.stdout) parts.push(`stdout:\n${result.stdout}`);
      if (result.stderr) parts.push(`stderr:\n${result.stderr}`);
      parts.push(`exit code: ${result.exitCode}`);
      return parts.join("\n");
    },
  },

  restart_server: {
    description:
      "Kill the running MCP server on port 3109, rebuild all widgets, restart, " +
      "and poll until healthy. Returns tools/list on success or build logs on failure. " +
      "Call this after writing/editing any tool or widget file.",
    parameters: z.object({
      workspaceId: z.string().describe("Sandbox ID"),
    }),
    execute: async ({ workspaceId }: { workspaceId: string }) => {
      const e2b = await import("e2b");
      const sandbox = await e2b.Sandbox.connect(workspaceId);
      const WS = "/home/user/workspace";

      // 1. 通过 ss 停止旧 Server，E2B 中没有 fuser/lsof
      await sandbox.commands.run(
        "kill $(ss -tlnp 'sport = :3109' | grep -oP 'pid=\\K[0-9]+' | head -1) 2>/dev/null; sleep 2",
        { cwd: WS, timeoutMs: 10000 },
      );

      // 2. 在后台运行 npm run dev，先构建组件再启动 Server
      await sandbox.commands.run("npm run dev > /tmp/dev.log 2>&1", {
        cwd: WS,
        timeoutMs: 5000,
        background: true,
      });

      // 3. 轮询直到 Server 响应，最长 30 秒
      for (let attempt = 0; attempt < 6; attempt++) {
        await new Promise((r) => setTimeout(r, 5000));

        const result = await sandbox.commands.run(
          "curl -sf http://localhost:3109/mcp -X POST " +
            "-H 'Content-Type: application/json' " +
            '-d \'{"jsonrpc":"2.0","method":"tools/list","id":1,"params":{}}\' 2>/dev/null | head -c 500',
          { cwd: WS, timeoutMs: 10000 },
        );

        if (result.stdout && result.stdout.includes("tools")) {
          return `Server restarted successfully.\n${result.stdout}`;
        }
      }

      // 4. 失败时返回构建日志以便调试
      const logs = await sandbox.commands.run("cat /tmp/dev.log | tail -40", {
        cwd: WS,
        timeoutMs: 5000,
      });
      return `Server failed to start after 30s. Build logs:\n${logs.stdout}\n${logs.stderr}`;
    },
  },

  get_workspace_info: {
    description: "Get current status and endpoint of the active workspace sandbox.",
    parameters: z.object({
      workspaceId: z.string().describe("Sandbox ID"),
    }),
    execute: async ({ workspaceId }: { workspaceId: string }) => {
      const info = await workspaceProvider.getInfo(workspaceId);
      return JSON.stringify(info);
    },
  },

  download_workspace: {
    description:
      "Package the current workspace as a .tar.gz archive (excludes node_modules/dist) and return a signed download URL. " +
      "Present the URL to the user so they can download their MCP server.",
    parameters: z.object({
      workspaceId: z.string().describe("Sandbox ID"),
    }),
    execute: async ({ workspaceId }: { workspaceId: string }) => {
      const { downloadUrl } =
        await workspaceProvider.prepareDownload(workspaceId);
      return `Workspace packaged. Download URL (valid ~1 hour): ${downloadUrl}`;
    },
  },
};

// ── 系统 Prompt ──────────────────────────────────────────────────────────────

const AGENT_SYSTEM_PROMPT = `你是 MCP UI Studio 编码 Agent，负责在隔离的工作区沙箱中构建 MCP UI 工具，并使用已有的 MCP 工具。

规则：
1. 工具调用后绝不能直接停止，必须继续下一步或发送消息。
2. 不要调用 read_file“研究”模板，所有模式均在下方给出。
3. 每条消息最多一句话，并尽量批量调用工具。

请求范围（确保可靠性）：
- 优先构建“一个工具 + 一个组件”：单页面、本地状态、原生 React，并使用 /home/user/workspace 中的模板 CSS。
- 除非用户明确要求且确有必要，否则不要添加 npm 依赖或大型客户端库；默认不增加新包。
- 除非用户坚持，否则避免流程图、节点图、无限画布或图表编辑器（React Flow、Mermaid、D3、graphviz 等），这些会使沙箱任务失控。应建议范围更小的组件，如棋盘、计算器或列表加表单。
- 请求含糊时只提出一个简短的澄清问题，不要猜测并设计大型架构。

═══════════════════════════════════════════════════════════════
代码模式（直接使用，不要调用 read_file）
═══════════════════════════════════════════════════════════════

工作区：/home/user/workspace；Server 端口：3109

── 工具文件：tools/<name>.ts ──
\`\`\`ts
import { MCPServer, text, widget } from "mcp-use/server";
import { z } from "zod";
export function register(server: MCPServer) {
  server.tool(
    { name: "tool-name", description: "工具功能说明",
      schema: z.object({ param: z.string().describe("参数说明") }),
      widget: { name: "widget-folder-name", invoking: "正在加载……", invoked: "已完成" },
      _meta: {
        "ui/previewData": { param: "sample-value" },  // 必需：MCP UI Studio 侧边栏预览的示例数据
      } },
    async ({ param }) => widget({ props: { /* 传给 React */ }, output: text("大语言模型摘要") })
  );
}
\`\`\`
组件工具必须添加 _meta["ui/previewData"]，对象结构必须与组件接收的 props 一致，否则 Studio 无法显示演示预览。

── 组件：resources/<widget-folder-name>/widget.tsx ──
\`\`\`tsx
import { McpUseProvider, useWidget, type WidgetMetadata } from "mcp-use/react";
import React from "react";
import "../styles.css";
export const widgetMetadata: WidgetMetadata = { description: "组件显示内容", metadata: { prefersBorder: false } };
const W: React.FC = () => {
  const { props, isPending } = useWidget<{ param: string }>();
  if (isPending) return <McpUseProvider><div className="p-6 animate-pulse">正在加载……</div></McpUseProvider>;
  return (<McpUseProvider><div className="rounded-2xl border border-default bg-surface-elevated p-6">{/* UI */}</div></McpUseProvider>);
};
export default W;
\`\`\`

── 在 index.ts 中注册（一次 edit_file 调用包含多项编辑）──
edit_file(path: "index.ts", edits: [
  { search: "// ADD NEW TOOL IMPORTS HERE", replace: 'import { register as registerX } from "./tools/x";\\n// ADD NEW TOOL IMPORTS HERE' },
  { search: "// ADD NEW TOOL REGISTRATIONS HERE", replace: 'registerX(server);\\n// ADD NEW TOOL REGISTRATIONS HERE' }
])

═══════════════════════════════════════════════════════════════
工作流 A：构建新工具（尚无沙箱）
═══════════════════════════════════════════════════════════════
1. provision_workspace("<name>") → workspaceId + endpoint
2. add_mcp_server(endpoint, "<name>")
3. set_active_workspace(workspaceId, endpoint)
4. write_file: resources/<widget>/widget.tsx
5. write_file: tools/<name>.ts
6. edit_file(path: "index.ts", edits: [import edit, registration edit])
7. restart_server(workspaceId)：停止旧 Server、重新构建并轮询直至健康；出错时修复代码并重试。
8. refresh_mcp_tools()
9. show_mcp_test_prompts(prompts_json)：前端 Action；传入 JSON 数组字符串，如 [{"label":"列出工具","message":"列出 MCP Server 的所有可用工具"},{"label":"…","message":"…"}]，让用户可在同一对话中点击标签测试 Server。
10. 告知用户服务已上线。

═══════════════════════════════════════════════════════════════
工作流 B：编辑或添加工具（沙箱正在运行）
═══════════════════════════════════════════════════════════════
跳过步骤 1-3，编辑现有文件或添加新工具（步骤 4-8）。
任何修改后执行：restart_server → refresh_mcp_tools → show_mcp_test_prompts（可选，需要试用新增或变更工具时使用）。

═══════════════════════════════════════════════════════════════
工作流 C：使用已有 MCP 工具
═══════════════════════════════════════════════════════════════
直接调用工具，无需操作沙箱。`;

const openai = createOpenAI({
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL,
});

/** Mastra Agent 使用的 OpenAI 兼容对话模型，例如 deepseek-chat。 */
const OPENAI_MODEL = process.env.OPENAI_MODEL?.trim() || "deepseek-chat";

// ── 请求处理器 ───────────────────────────────────────────────────────────────
// 架构：Mastra Agent 通过 MCPClient 直接执行大语言模型可见的 MCP 工具；
// AG-UI Observable 层的函数中间件处理代理请求、拦截 MCP UI 工具结果并发出
// ACTIVITY_SNAPSHOT；CopilotKit v2 内置的 MCPAppsActivityRenderer 渲染组件 iframe

export const POST = async (req: NextRequest) => {
  const requestId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  let mcp: MCPClient | null = null;

  try {
    const mcpServers = readMcpServersFromHeader(req);
    mastraLog(
      "[mastra-agent] === NEW REQUEST ===",
      requestId,
      "model:",
      OPENAI_MODEL,
    );

    // 1. 获取 UI 工具元数据，包括带 UI 的工具及其 Resource URI
    const uiTools = await fetchUIToolMetadata(mcpServers);

    // 2. 创建用于执行工具的 Mastra MCP Client
    const mcpServerConfig: Record<string, { url: URL }> = {};
    for (const server of mcpServers) {
      const serverId = server.serverId || new URL(server.url).hostname;
      mcpServerConfig[serverId] = { url: new URL(server.url) };
    }

    mcp = new MCPClient({
      id: `mastra-agent-${requestId}`,
      servers: mcpServerConfig,
    });

    let mcpTools = {};
    try {
      mcpTools = await mcp.listTools();
      mastraLog("[mastra-agent] MCP tools loaded:", Object.keys(mcpTools));
    } catch (error) {
      console.error("[mastra-agent] Failed to load MCP tools:", error);
    }

    // 3. 使用 MCP 工具和工作区工具创建 Mastra Agent
    const mastraAgent = new Agent({
      id: "default",
      name: "MCP UI Builder",
      instructions: {
        role: "system",
        content: AGENT_SYSTEM_PROMPT,
        providerOptions: {
          openai: {
            reasoningEffort: "minimal", // Options: "minimal", "low", "medium", "high"
          },
        },
      },
      model: openai(OPENAI_MODEL),
      tools: {
        ...mcpTools,
        ...workspaceTools,
      } as Record<string, never>,
      defaultOptions: {
        maxSteps: 25, // Allow up to 25 tool call steps (default is 10)
      },
    });

    // 4. 使用 AG-UI Adapter 包装
    const agentWrapper = new MastraAgent({
      agent: mastraAgent,
      resourceId: "anonymous",
    });

    // 5. 为 ACTIVITY_SNAPSHOT 和代理请求挂载 AG-UI 中间件；中间件在 Observable
    //    层而非 SSE 层运行，使事件流经 CopilotKit v2 管线并触发 Renderer
    // @ts-expect-error - rxjs version mismatch (7.8.1 vs 7.8.2) between @ag-ui packages
    agentWrapper.use(createMcpUIMiddleware(mcpServers, uiTools));

    // 修复：CopilotKit Runtime 会在 runAgent() 前调用 registeredAgent.clone()；
    // MastraAgent.clone() 会丢失通过 .use() 添加的中间件，因此覆盖 clone()，
    // 在克隆对象上重新挂载中间件
    const mcpMiddleware = createMcpUIMiddleware(mcpServers, uiTools);
    const origClone = agentWrapper.clone.bind(agentWrapper);
    agentWrapper.clone = function () {
      const cloned = origClone();
      // @ts-expect-error - rxjs version mismatch
      cloned.use(mcpMiddleware);
      return cloned;
    };

    mastraLog(
      "[mastra-agent] Agent ready. UI tools:",
      uiTools.size,
      "MCP tools:",
      Object.keys(mcpTools).length,
    );

    // 6. 创建 CopilotKit Runtime
    const serviceAdapter = new ExperimentalEmptyAdapter();

    const runtime = new CopilotRuntime({
      agents: {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        default: agentWrapper as any,
      },
    });

    const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
      runtime,
      serviceAdapter,
      endpoint: "/api/mastra-agent",
    });

    return handleRequest(req);
  } catch (error) {
    console.error("[mastra-agent] Error:", error);
    return new Response(
      JSON.stringify({
        error: error instanceof Error ? error.message : "Internal server error",
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      },
    );
  } finally {
    if (mcp) {
      try {
        await mcp.disconnect();
      } catch {
        /* ignore */
      }
    }
  }
};
