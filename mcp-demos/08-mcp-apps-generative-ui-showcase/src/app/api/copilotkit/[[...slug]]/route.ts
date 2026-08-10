/**
 * 使用 MCP Apps 中间件的 CopilotKit API 路由。
 * 连接旅行预订 MCP Server，并启用带 UI 的工具。
 *
 * 参考：v2.x/apps/react/demo/src/app/api/copilotkit-mcp/[[...slug]]/route.ts
 */

import {
  BuiltInAgent,
  CopilotRuntime,
  createCopilotEndpoint,
  InMemoryAgentRunner,
} from "@copilotkit/runtime/v2";
import { handle } from "hono/vercel";
import { MCPAppsMiddleware } from "@ag-ui/mcp-apps-middleware";

// 根据可用 API Key 决定使用哪个大语言模型
const determineModel = () => {
  if (process.env.OPENAI_API_KEY?.trim()) {
    return `openai/${process.env.OPENAI_MODEL?.trim() || "deepseek-chat"}`;
  }
  if (process.env.ANTHROPIC_API_KEY?.trim()) {
    return "anthropic/claude-sonnet-4-6";
  }
  if (process.env.GOOGLE_API_KEY?.trim()) {
    return "google/gemini-3.1-pro-preview";
  }
  return `openai/${process.env.OPENAI_MODEL?.trim() || "deepseek-chat"}`;
};

// 使用多应用助手角色和 MCP Apps 中间件创建 Agent
const agent = new BuiltInAgent({
  model: determineModel(),
  prompt: `你是一名 AI 助手，可以访问 4 个直接在对话中渲染的交互式应用。每个应用都为特定任务提供丰富的 UI。

## 可用应用

### 1. 机票预订（search-flights）
搜索航班、选择座位并通过完整向导完成预订。
- 参数：origin（机场代码，如 JFK、LAX、LHR）、destination（机场代码）、departureDate（YYYY-MM-DD）、passengers（1-9）、cabinClass（economy/business/first）
- 示例：“为 2 名乘客预订 1 月 20 日从纽约到洛杉矶的航班”
- 辅助工具：select-flight、select-seats、book-flight

### 2. 酒店预订（search-hotels）
浏览酒店、比较房型并预订世界各地的住宿。
- 参数：city（巴黎、东京、纽约等）、checkIn（YYYY-MM-DD）、checkOut（YYYY-MM-DD）、guests（1-6）、rooms（1-4）
- 示例：“为 2 位客人查找 1 月 15 日至 18 日的巴黎酒店”
- 辅助工具：select-hotel、select-room、book-hotel

### 3. 投资模拟器（create-portfolio）
创建包含持仓、图表和交易功能的模拟投资组合。
- 参数：initialBalance（1000-1000000）、riskTolerance（conservative/moderate/aggressive）、focus（tech/healthcare/diversified/growth/dividend）
- 示例：“创建一个 10,000 美元、激进型且侧重科技股的投资组合”
- 辅助工具：execute-trade、refresh-prices

### 4. 看板（create-board）
创建支持拖放卡片和分栏的任务看板。
- 参数：projectName（字符串）、template（blank/software/marketing/personal）
- 示例：“为我的软件项目创建看板”
- 辅助工具：add-card、update-card、delete-card、move-card

## 行为准则
- 用户请求与某个应用匹配时，使用相应工具渲染交互式 UI
- 缺少关键参数时提出澄清问题
- 每个应用都有辅助工具，用于处理 UI 中的进一步交互
- 主动帮助用户使用各项交互功能`,
}).use(
  new MCPAppsMiddleware({
    mcpServers: [
      {
        type: "http",
        url: process.env.MCP_SERVER_URL || "http://localhost:3001/mcp",
      },
    ],
  }),
);

// 创建 CopilotKit Runtime
const runtime = new CopilotRuntime({
  agents: {
    default: agent,
  },
  runner: new InMemoryAgentRunner(),
});

// 创建 Hono Endpoint
const app = createCopilotEndpoint({
  runtime,
  basePath: "/api/copilotkit",
});

export const GET = handle(app);
export const POST = handle(app);
