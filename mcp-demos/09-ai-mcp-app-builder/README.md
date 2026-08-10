# 09 AI MCP App Builder

这个示例让用户用自然语言描述 MCP App，由 Agent 在 E2B 沙箱中读写代码、启动 MCP Server，再把生成的交互界面接回聊天页面。它是 Tool、Resource、MCP Apps 和 Agent 工具循环的综合实践。

## 学习目标

- 理解“Agent 生成 MCP Server 与 UI”的完整链路；
- 使用 E2B 创建隔离的代码工作区；
- 让 Agent 读取、写入并执行沙箱内文件；
- 动态连接 MCP Server、发现工具并渲染 UI Resource；
- 区分主 Mastra Agent 路由与保留的旧 CopilotKit 路由。

## 默认模型

默认使用 `deepseek-v4-pro`。Builder 需要理解现有代码、连续调用文件和命令工具、修复构建错误并生成完整应用，属于复杂 Agent 编程任务。

只有超大代码库或专项代码生成评测确有优势时，再考虑 `qwen3-coder-plus` 等代码模型。切换前应验证工具调用、上下文长度、成本和生成项目的实际通过率。

## 当前模型支持状态

主接口 `apps/web/app/api/mastra-agent/route.ts` 使用 `createOpenAI()`，并读取 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 和 `OPENAI_MODEL`，可以配置 DeepSeek 的 OpenAI-compatible API。

仓库的 `.env.example` 仍使用旧模型名 `deepseek-chat`。运行时请改为：

```env
OPENAI_API_KEY=your-deepseek-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-pro
```

另一个接口 `apps/web/app/api/copilotkit/route.ts` 是保留的旧实现，模型仍写死为 `openai/gpt-5.5`。主页面使用 Mastra 路径时可以走 DeepSeek；如果切回旧路由，需要单独改造模型配置。

## 关键目录

- `apps/web/`：Next.js 页面、Agent API、MCP 管理和预览界面。
- `apps/web/app/api/mastra-agent/route.ts`：主 Agent、MCP 代理和沙箱工具。
- `apps/web/lib/workspace/e2b.ts`：E2B 工作区封装。
- `apps/mcp-use-server/`：沙箱内使用的 MCP Server 模板。
- `apps/threejs-server/`：本地 Three.js MCP App 示例。
- `pnpm-workspace.yaml`：Monorepo 工作区配置。

## 架构

```text
用户描述应用
  ↓
CopilotKit 聊天界面
  ↓
Mastra Agent + DeepSeek V4 Pro
  ↓
工作区工具：创建沙箱、读写文件、执行命令
  ↓
返回并连接沙箱 MCP 地址
  ↓
发现 Tools + 读取 HTML Resource
  ↓
聊天中预览生成的 MCP App
```

## 环境要求

- Node.js 20 或更高版本；
- pnpm 10；
- DeepSeek API Key；
- E2B API Key：生成和运行沙箱应用时使用。

## 运行

```bash
pnpm install
cp .env.example .env
```

编辑 `.env`：

```env
OPENAI_API_KEY=your-deepseek-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-pro
E2B_API_KEY=your-e2b-key
```

启动整个工作区：

```bash
pnpm dev
```

也可以只启动单个部分：

| 目标 | 命令 |
|---|---|
| Web 应用 | `pnpm --filter web dev` |
| Three.js 示例 | `cd apps/threejs-server && pnpm dev` |
| 本地 MCP 模板 | `cd apps/mcp-use-server && pnpm dev` |

Next.js 通常运行在 `http://localhost:3000`，以终端实际输出为准。

## E2B 配置

| 变量 | 作用 |
|---|---|
| `E2B_API_KEY` | 调用 E2B 沙箱服务 |
| `E2B_TEMPLATE` | 使用预构建模板，减少启动等待 |
| `E2B_REPO_URL` | 未设置模板时，在沙箱中克隆代码仓库 |

没有 `E2B_API_KEY` 时，仍可连接已有 MCP Server，但无法完成“创建沙箱并生成应用”的核心流程。

## 动态 MCP Server

页面可添加或删除 MCP Server 地址，配置通过 `x-mcp-servers` 请求头发送给后端。默认 Server 可用以下变量覆盖：

```env
DEFAULT_MCP_SERVERS=[...]
NEXT_PUBLIC_DEFAULT_MCP_SERVERS=[...]
```

前者用于服务端，后者会暴露给浏览器。不要把私密 Token 放进 `NEXT_PUBLIC_*` 变量。

## 阅读代码时重点关注

1. `provision_workspace` 如何创建沙箱并返回 MCP Endpoint。
2. `read_file`、`write_file` 和 `exec` 如何组成 Agent 编程能力。
3. Agent 如何启动生成的 Server，再把 Endpoint 加回页面。
4. `fetchUIToolMetadata()` 如何发现 `ui/resourceUri`。
5. MCP 代理如何读取 HTML 并处理 iframe 资源地址。

## 金融场景改造

可以生成组合风险面板、财报摘要器、因子筛选器或事件日历。数据读取工具与交易执行工具应完全分离。生成代码只能先在沙箱运行；接入真实账户前还需完成依赖审计、权限检查、人工评审和独立部署。

## 安全边界

- 不要把生产密钥写入生成代码或前端环境变量；
- 限制沙箱生命周期、网络访问和资源额度；
- 对下载项目做依赖和恶意代码扫描；
- 生产部署前必须人工检查；
- 不要让生成应用直接执行不可逆的真实交易。

## 常见问题

- 模型报 404：确认模型名和接口地址。
- 能聊天但不能创建应用：检查 `E2B_API_KEY` 和模板配置。
- 新 Server 启动后没有工具：检查 Endpoint，再重新执行工具发现。
- 切换旧 CopilotKit Route 后调用 OpenAI：该路由仍写死模型，需要单独修改。
