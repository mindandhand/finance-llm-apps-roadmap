# 08 MCP Apps 生成式界面示例

这个示例把航班预订、酒店预订、投资组合模拟器和看板直接渲染在聊天界面中。MCP Server 不只返回文本或 JSON，还把工具与 HTML Resource 关联起来，由 CopilotKit 在沙箱 iframe 中展示交互界面。

## 学习目标

- 理解 MCP Apps 中 Tool、Resource 和聊天宿主的协作关系；
- 用 `_meta["ui/resourceUri"]` 关联工具与 HTML 界面；
- 通过 `text/html+mcp` 暴露可渲染资源；
- 理解 iframe 应用如何通过 `postMessage` 再调用 MCP 工具；
- 分别启动 MCP Server 和 Next.js 前端。

## 默认模型策略

项目默认使用 `deepseek-v4-flash`。本示例的重点是协议和界面交互，模型主要负责识别意图、补齐参数并选择工具，Flash 模型通常已经够用。

但当前代码**尚未完成 DeepSeek 直连适配**。API Route 使用 CopilotKit 的 `openai/...` Provider，只读取 `OPENAI_API_KEY` 和 `OPENAI_MODEL`，没有把 `OPENAI_BASE_URL` 传给 Provider。仅把模型名改成 `deepseek-v4-flash`，请求不一定会发送到 DeepSeek。

落实 DeepSeek 默认规范时，需要先在 `src/app/api/copilotkit/[[...slug]]/route.ts` 中创建支持自定义 `baseURL` 的模型 Provider，再配置：

```env
OPENAI_API_KEY=your-deepseek-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-flash
```

当前 Route 中的 `deepseek-chat` 只是旧默认字符串，不代表已经接入 DeepSeek，而且该旧别名已经停止服务。

## 四个应用

| 应用 | 入口工具 | 主要交互 |
|---|---|---|
| 航班预订 | `search-flights` | 查询航班、选座、预订 |
| 酒店预订 | `search-hotels` | 选择酒店、房型、预订 |
| 投资组合模拟 | `create-portfolio` | 查看图表、模拟买卖 |
| 看板 | `create-board` | 新建、移动和删除卡片 |

这些都是演示数据，不能把投资组合中的报价或交易结果用于真实投资决策。

## 关键文件

- `mcp-server/server.ts`：注册 MCP Tools 和 Resources。
- `mcp-server/src/`：四个应用的服务端逻辑。
- `mcp-server/apps/`：打包后的 HTML 应用。
- `src/app/api/copilotkit/[[...slug]]/route.ts`：Agent、Runtime 和 MCP Apps Middleware。
- `src/app/page.tsx`：聊天页面。

## 工作流程

```text
用户：“创建一个 1 万美元的科技组合”
  ↓
模型调用 create-portfolio
  ↓
工具元数据指向 ui://stocks/trading-app.html
  ↓
Middleware 读取 HTML Resource
  ↓
CopilotKit 在沙箱 iframe 中渲染交易面板
  ↓
界面通过 postMessage 调用 execute-trade 等工具
```

## 本地运行

分别安装前端和 MCP Server 依赖：

```bash
npm install
cd mcp-server
npm install
cd ..
```

在完成 DeepSeek Provider 适配前，请按当前代码实际支持的模型配置 `.env.local`。随后打开两个终端。

终端一：

```bash
cd mcp-server
npm run build
npm run dev
```

MCP Server 默认监听 `http://localhost:3001/mcp`。

终端二，在示例根目录运行：

```bash
npm run dev
```

打开 `http://localhost:3000`。如果 MCP Server 地址不同，设置：

```env
MCP_SERVER_URL=http://localhost:3001/mcp
```

## Tool 与 Resource 如何关联

```typescript
server.registerTool(
  "search-flights",
  {
    inputSchema: { origin, destination, departureDate, passengers },
    _meta: { "ui/resourceUri": "ui://flights/flights-app.html" },
  },
  handler,
);

server.registerResource(
  "flights-app",
  "ui://flights/flights-app.html",
  { mimeType: "text/html+mcp" },
  () => ({ contents: [{ text: htmlContent }] }),
);
```

Tool 负责执行操作，Resource 提供界面。服务端控制业务逻辑，聊天宿主负责安全展示。

## 阅读代码时重点关注

1. 入口 Tool 如何声明 `ui/resourceUri`。
2. HTML App 如何获得结果并继续调用工具。
3. `MCPAppsMiddleware` 如何连接 HTTP MCP Server。
4. iframe 沙箱如何隔离生成式界面。
5. 前后端为什么需要分别启动。

## 金融场景改造

可以保留投资组合应用，把演示价格换成带时间戳的数据源，并增加持仓上限、行业暴露、最大回撤和风险预算。真实交易必须放在独立服务中，并加入鉴权、幂等、额度限制和人工确认；不要让 iframe 持有交易密钥。

## 常见问题

- 聊天可用但没有界面：检查 MCP Server、`MCP_SERVER_URL` 和 Resource MIME 类型。
- 工具成功但 iframe 空白：检查 HTML 构建结果和浏览器控制台。
- DeepSeek Key 无效：当前 Route 缺少自定义 `baseURL` 接线，需要先适配代码。
- 端口冲突：确认前端使用 3000、MCP Server 使用 3001，或同步修改配置。
