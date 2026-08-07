# MCP 中文学习路线：10 个由浅入深的示例

这组示例从“连接一个本地工具”开始，逐步扩展到多 MCP 编排、专业 Agent 路由、聊天内交互 UI，以及运行时生成 MCP App。建议按 01–10 顺序学习。

本目录有两个约定：

1. 教程正文使用中文，代码标识、命令、协议名和第三方产品名保留原文。
2. 默认使用 DeepSeek；只有出现视觉输入、专项代码模型等明确需求时才切换其他中国模型。

## 先理解四个概念

- **MCP Server**：提供工具、资源和提示模板的一侧，可以是本地进程、Docker 容器或 HTTP 服务。
- **MCP Client**：连接 Server、发现能力，并把工具 schema 交给模型的一侧。
- **Tool / Resource / Prompt**：Tool 执行动作，Resource 提供数据，Prompt 提供可复用提示模板。
- **Transport**：Client 与 Server 的通信方式。本目录主要涉及 stdio、Docker stdio、HTTP 和 MCP Apps UI。

MCP 解决的是“如何用统一协议连接外部能力”，不是替代 Agent 框架。示例会分别使用 Agno、mcp-agent、CopilotKit 和 Mastra。

## 默认使用 DeepSeek，按需求切换

轻量任务默认使用 `deepseek-v4-flash`，复杂编排、路由和代码任务默认使用 `deepseek-v4-pro`。其他模型不是并列默认项，只有 DeepSeek 当前能力与任务输入不匹配时才切换。模型名称和能力以 2026 年 8 月的厂商文档为准。

| 示例 | 主要特性 | DeepSeek 默认 | 何时考虑其他模型 | 当前接入状态 |
| --- | --- | --- | --- | --- |
| 01 Filesystem | 少量、确定性的文件工具调用 | `deepseek-v4-flash` | 通常无需切换 | 已迁移到 Agno，支持 OpenAI-compatible 配置 |
| 02 Firecrawl | 多网页抓取、长文本汇总 | `deepseek-v4-pro` | 需要特定中文长文档能力时评估千问 | 已迁移到 Agno，支持 OpenAI-compatible 配置 |
| 03 Notion | 中文知识库、长对话、页面编辑 | `deepseek-v4-flash` | 超长文档或特定中文效果不足时评估千问 | 已支持 OpenAI-compatible 环境变量 |
| 04 GitHub | 仓库、Issue、PR 和代码分析 | `deepseek-v4-pro` | 大型代码生成任务可评估 `qwen3-coder-plus` | 已支持 OpenAI-compatible 环境变量 |
| 05 Browser | 多步浏览器操作、页面与截图理解 | `deepseek-v4-pro` | 必须直接理解截图时改用支持视觉输入的千问模型 | `mcp-agent` 配置可直接设置 base URL |
| 06 Multi-MCP | 多服务工具选择与长链路执行 | `deepseek-v4-pro` | 实际评测证明专项模型完成率更高时再切换 | 已支持 OpenAI-compatible 环境变量 |
| 07 Router | 意图路由、专业 Agent、复杂推理 | `deepseek-v4-pro` | 当前任务通常无需切换 | 当前仍硬编码 Claude，需要改代码 |
| 08 Travel Planner | 地图、住宿、搜索等多工具规划 | `deepseek-v4-pro` | 需要视觉行程或特定中文本地化时评估千问 | 已支持 OpenAI-compatible 环境变量 |
| 09 MCP Apps | 从请求选择正确 UI Tool | `deepseek-v4-flash` | Tool 数量很大或含视觉输入时再评估其他模型 | 当前 route 未接入自定义 base URL |
| 10 App Builder | 生成 TypeScript/React/MCP Server | `deepseek-v4-pro` | 超长代码库或专项 Coding Agent 可评估 `qwen3-coder-plus` | Mastra 主路径已支持 OpenAI-compatible |

### 什么时候才切换模型

- 需要模型直接理解截图、图片或视频，而当前 DeepSeek API 路径只传文本。
- 大型代码库生成效果不满足要求，需要专项 Coding Agent 模型。
- 已用实际测试证明中文长文档质量、延迟或成本不符合目标。

不要因为某个模型在排行榜上更高就切换。先用同一组任务验证工具选择、参数正确率、完成率、延迟和成本。

不要把“支持 OpenAI-compatible API”误解为“任何框架都能零修改切换”。框架还可能固定 provider、消息格式、tool schema 或模型前缀。每个子目录 README 都会写明当前状态。

## DeepSeek 默认配置

### 轻量任务

```bash
export DEEPSEEK_API_KEY=your-deepseek-key
export OPENAI_BASE_URL=https://api.deepseek.com
export OPENAI_MODEL=deepseek-v4-flash
```

### 复杂 Agent 和代码任务

```bash
export DEEPSEEK_API_KEY=your-deepseek-key
export OPENAI_BASE_URL=https://api.deepseek.com
export OPENAI_MODEL=deepseek-v4-pro
```

旧别名 `deepseek-chat` 和 `deepseek-reasoner` 已在 2026-07-24 停用，新文档不再把它们作为默认值。

### 有明确需求时切换千问

```bash
export LLM_API_KEY=your-dashscope-key
export OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
export OPENAI_MODEL=qwen3-coder-plus
```

### 本地模型

如果本地服务提供 OpenAI-compatible endpoint，可以沿用同一组环境变量：

```bash
export LLM_API_KEY=local
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_MODEL=your-tool-capable-model
```

本地模型必须支持工具调用；只会文本对话的模型无法完成 MCP Agent 循环。

## 通用准备

Python 示例通常需要：

```bash
pip install -r requirements.txt
```

stdio MCP Server 通常由 `npx` 启动，因此先确认 Node.js：

```bash
node --version
npm --version
npx --version
```

不要把模型密钥和 MCP 服务密钥混在一起：

- 模型密钥：DashScope、DeepSeek 等推理服务的 API key。
- MCP 服务密钥：`NOTION_API_KEY`、`GITHUB_TOKEN`、`FIRECRAWL_API_KEY`、地图服务 key 等。

## 学习路径

| # | 目录 | 本节新增内容 | 前置示例 |
| --- | --- | --- | --- |
| 1 | [`01-filesystem-mcp`](01-filesystem-mcp) | Agno 通过 stdio 连接本地 Filesystem Server | 无 |
| 2 | [`02-firecrawl-mcp`](02-firecrawl-mcp) | MCP Server 注入 API key，抓取与抽取网页 | 01 |
| 3 | [`03-notion-mcp-agent`](03-notion-mcp-agent) | SaaS MCP、页面权限、SQLite 对话记忆 | 01 |
| 4 | [`04-github-mcp-agent`](04-github-mcp-agent) | Streamlit、Docker stdio、官方 GitHub Server | 03 |
| 5 | [`05-browser-mcp-agent`](05-browser-mcp-agent) | Playwright 浏览器导航、点击、截图和抽取 | 04 |
| 6 | [`06-multi-mcp-agent`](06-multi-mcp-agent) | 一个 Agent 同时连接多个 MCP Server | 03–05 |
| 7 | [`07-multi-mcp-agent-router`](07-multi-mcp-agent-router) | Router 选择专业 Agent 和最小工具集合 | 06 |
| 8 | [`08-travel-planner-mcp-agent-team`](08-travel-planner-mcp-agent-team) | 多 MCP 与普通工具组成完整业务流程 | 06–07 |
| 9 | [`09-mcp-apps-generative-ui-showcase`](09-mcp-apps-generative-ui-showcase) | Tool 返回可渲染的 UI Resource | 01–08 |
| 10 | [`10-ai-mcp-app-builder`](10-ai-mcp-app-builder) | Agent 在沙箱中生成并运行 MCP App | 09 |

## 每个示例都问四个问题

1. MCP Server 由谁启动？
2. 使用 stdio、Docker stdio、HTTP，还是 MCP Apps UI？
3. Server 暴露哪些 Tools 和 Resources？
4. 当前模型接口是否真的支持这些工具调用格式？

## 安全边界

- Filesystem MCP 只能授权演示目录，不要直接授权主目录或仓库根目录。
- Browser MCP 默认只访问公开页面，不登录高权限系统。
- GitHub、Notion 等 token 使用最小权限，不写入 README 或 Git。
- Tool 参数由模型生成，应用层仍需校验；模型支持 Function Calling 不等于参数永远合法。

## 官方参考

- [千问 Function Calling](https://help.aliyun.com/zh/model-studio/qwen-function-calling)
- [千问文本与代码模型选择](https://help.aliyun.com/zh/model-studio/text-generation-model)
- [DeepSeek Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/)
- [MCP 官方文档](https://modelcontextprotocol.io/docs/)
