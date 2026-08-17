# 09 架构与调用链说明

本文解释 AI MCP App Builder 中各组件如何协作。建议先运行页面并观察一次聊天，再结合本文阅读源码。

## 1. 项目解决什么问题

普通 MCP Client 只能连接已经存在的 MCP Server。这个项目进一步让 Agent 在隔离工作区中修改代码、启动新的 MCP Server，并把新 Server 提供的 Tool 和交互式 UI 接回当前聊天。

完整任务包含两个循环：

```text
代码生成循环：理解需求 → 读取模板 → 修改代码 → 构建 → 修复错误

MCP 使用循环：连接 Server → 发现 Tool → 调用 Tool → 读取 UI Resource → 渲染结果
```

前者操作工作区，后者操作 MCP 协议。理解这两个循环的区别，是阅读项目的关键。

## 2. 组件关系

```text
浏览器
  ├─ Next.js 页面
  ├─ CopilotKit Chat
  ├─ 前端 Actions / Readable State
  └─ MCP Apps Renderer
          │ AG-UI 请求与事件
          ▼
Next.js Route /api/mastra-agent
  ├─ Mastra Agent
  ├─ OpenAI-compatible 模型客户端
  ├─ 工作区工具
  ├─ Mastra MCPClient
  └─ MCP UI 中间件
          │
          ├───────────────┐
          ▼               ▼
工作区 Provider       已连接的 MCP Server
  └─ Podman/E2B 沙箱    ├─ Tools
      ├─ 文件系统        ├─ Resources
      ├─ 命令执行        └─ MCP App HTML
      └─ 新 MCP Server
```

### 浏览器层

`app/page.tsx` 负责页面布局和主要状态。`DynamicCopilotKitProvider` 将页面接入 Agent Route，并在请求头中携带当前 MCP Server 列表。

`BuilderAgentProvider` 注册两类模型上下文：

- `useCopilotReadable`：让模型知道当前工作区、选中工具和已连接 Server；
- `useCopilotAction`：允许模型请求浏览器更新 React 状态。

这些 Action 不应承担克隆仓库、安装依赖或执行 Shell 等重任务。浏览器刷新或断网都可能中断它们，而且把基础设施凭证交给浏览器会扩大泄露风险。

### Agent 层

`api/mastra-agent/route.ts` 是当前默认 Agent 入口。它在每次请求中：

1. 解析 `x-mcp-servers`；
2. 查询已连接 Server 的工具与 UI 元数据；
3. 创建 Mastra MCP Client；
4. 将 MCP 工具和工作区工具合并后交给模型；
5. 将执行事件转换为 CopilotKit 可以消费的 AG-UI 流；
6. 请求结束时断开临时 MCP Client。

`api/copilotkit/route.ts` 是保留的旧 Agent 实现，不是当前页面默认调用的入口。保留它的价值在于比较两种 Agent 后端，但修改功能时要避免只更新其中一条路径。

### 工作区层

`WorkspaceProvider` 隔离 Agent 与具体沙箱供应商。Agent 只依赖创建工作区、读写文件、执行命令和停止工作区等能力，不需要理解 E2B 的底层 API。

当前实现是 `E2BWorkspaceProvider`：

- 配置 `E2B_TEMPLATE` 时，从预构建模板快速启动；
- 未配置模板时，创建基础沙箱后克隆仓库、安装依赖并启动 Server；
- 沙箱内部 MCP Server 默认监听 `3109`；
- Provider 将内部端口转换为外部可以访问的 HTTPS Endpoint。

## 3. 一次聊天请求如何流动

```text
用户输入
  ↓
CopilotKit 把消息、Readable State 和 x-mcp-servers 发给后端
  ↓
Mastra Agent 获取可用工作区工具和 MCP 工具
  ↓
模型决定直接回答或调用工具
  ↓
工具结果返回模型，模型继续下一步
  ↓
AG-UI 事件流回浏览器
  ↓
CopilotKit 显示文字、工具状态或 MCP App UI
```

工具调用可能发生多次。例如“创建天气组件”通常不是一次模型调用：

```text
provision_workspace
  → set_active_workspace
  → add_mcp_server
  → read_file
  → write_file
  → exec/build
  → restart_server
  → refresh_mcp_tools
  → 调用新工具
```

如果模型在中途停止，优先检查：系统提示是否明确要求继续、工具结果是否被正确回传、AG-UI Run 是否异常结束，以及模型是否支持稳定的连续工具调用。

## 4. 为什么 Endpoint 要传回浏览器

工作区创建后，后端已经知道沙箱 Endpoint，但页面维护的 Server 列表仍不知道它。Agent 因此调用 `add_mcp_server` 前端 Action，把 Endpoint 写入共享 React 状态。

下一轮请求时，Provider 将新列表放入 `x-mcp-servers`。后端重新发现工具，侧边栏也刷新能力列表。这种设计让浏览器显示状态、Agent 可见工具和 MCP UI 渲染使用同一组 Server。

这里传递的是 MCP Endpoint 和展示标识，不应传递 E2B API Key。

## 5. MCP Tool 与 MCP App 的区别

普通 MCP Tool 返回文本或结构化内容：

```text
tools/call → content: [{ type: "text", text: "..." }]
```

MCP App 还关联一个 UI Resource。Client 根据工具元数据取得 Resource URI，再读取 `text/html+mcp` 内容：

```text
tools/list
  ↓ 找到 ui/resourceUri
resources/read
  ↓ 返回 text/html+mcp
MCP Apps Renderer
  ↓
iframe 中显示交互组件
```

因此“工具执行成功”不等于“UI 一定能显示”。还要检查 Resource URI、MIME 类型、HTML 内容、CSP、资源地址重写和 AG-UI Activity 是否正确。

## 6. 状态分别保存在哪里

| 状态 | 保存位置 | 生命周期 |
|---|---|---|
| 聊天及前端状态 | CopilotKit/React | 当前页面会话 |
| MCP Server 列表 | React Context | 当前页面会话 |
| 最近工作区标识 | localStorage | 浏览器刷新后仍存在 |
| 工作区文件 | Podman/E2B 沙箱文件系统 | 沙箱生命周期内 |
| 模型与 E2B 密钥 | 服务端环境变量 | 服务进程生命周期 |

localStorage 中的工作区标识只用于尝试重连。它不能证明用户有权访问该工作区；如果改造成多用户产品，服务端必须校验工作区所有权。

## 7. 阅读源码的检查问题

完成阅读后，应能回答：

1. 为什么 MCP Server 列表既影响侧边栏，也影响 Agent 的可用工具？
2. 为什么创建沙箱和更新 React 状态分别属于后端 Tool 与前端 Action？
3. 为什么修改 Server 代码后要重启并重新发现工具？
4. Tool 结果如何变成 AG-UI Activity？
5. `text/html+mcp` 如何最终进入 iframe？
6. 页面刷新后可以恢复哪些状态，不能恢复哪些状态？
7. E2B API Key 为什么不能放入 `NEXT_PUBLIC_*` 环境变量？

## 8. 调试顺序

遇到问题时按链路从近到远检查：

1. 浏览器是否成功调用 `/api/mastra-agent`；
2. 模型配置和 API Key 是否正确；
3. `x-mcp-servers` 是否包含预期 Endpoint；
4. MCP introspection 是否能列出工具；
5. 工作区是否仍在运行；
6. 沙箱内 Server 是否监听 `3109`；
7. Tool 是否关联有效 UI Resource；
8. AG-UI 流中是否产生对应 Activity；
9. iframe 是否被 CSP 或资源地址阻止。

不要一开始同时修改模型、MCP Server、沙箱和 UI。先确定故障所在层，再做最小改动。
