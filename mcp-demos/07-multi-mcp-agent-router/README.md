# 07 多 MCP Agent 路由

这个示例把任务分给代码审查、安全审计、资料研究和 BIM 四个专业 Agent。每个 Agent 只连接自身所需的 MCP Server，用清晰的工具边界降低误调用风险。

## 学习目标

- 用规则路由把请求分配给专业 Agent；
- 为不同 Agent 配置独立提示词和 MCP 工具；
- 将 MCP 工具定义转换为模型 API 的工具格式；
- 实现“模型调用工具—执行 MCP 工具—回传结果—继续推理”的循环；
- 比较自动路由与人工选择。

## 默认模型策略

项目统一默认使用 `deepseek-v4-pro`。本示例涉及工具调用循环、代码审查和安全分析，优先选择 Pro 模型，通常无需切换其他模型。

但要注意：**当前代码还没有接入 DeepSeek**。`agent_forge.py` 仍使用 Anthropic SDK，模型写死为 `claude-sonnet-4-20250514`，页面也只接收 Anthropic API Key。仅设置 `DEEPSEEK_API_KEY` 不会生效。

要落实 DeepSeek 默认规范，需要同步修改模型客户端、接口地址、模型名、页面配置，以及工具调用消息格式。DeepSeek V4 同时提供 OpenAI-compatible 和 Anthropic-compatible API；采用后者可能改动较少，但仍需实际验证工具调用，不能只替换模型名称。

## 关键文件

- `agent_forge.py`：Agent 定义、规则路由、MCP 连接、工具循环和 Streamlit 页面。
- `requirements.txt`：Anthropic SDK、MCP SDK 和 Streamlit 依赖。

## 路由方式

```text
用户请求
  ↓
关键词规则 classify_query()
  ├─ 安全关键词 → Security Auditor
  ├─ 代码关键词 → Code Reviewer
  ├─ BIM 关键词  → BIM Engineer
  └─ 其他请求   → Researcher
  ↓
只连接该 Agent 配置的 MCP Server
```

这里的 Router 不是大模型，而是 `classify_query()` 中的关键词匹配。它简单、可解释、成本低，但中文关键词和模糊意图覆盖有限。页面也提供 Manual 模式，可以直接指定 Agent。

## 运行当前版本

以下步骤运行的是仓库现有 Claude 版本，不代表已完成 DeepSeek 适配：

```bash
pip install -r requirements.txt
streamlit run agent_forge.py
```

启动后，在侧边栏输入 Anthropic API Key。GitHub Agent 还需要：

```bash
export GITHUB_PERSONAL_ACCESS_TOKEN=your-github-token
```

Filesystem Server 当前只允许访问 `/tmp`。如需审查其他目录，应改成明确、最小的目录，不要开放整个用户目录。

## 四个专业 Agent

| Agent | 任务 | MCP Server |
|---|---|---|
| Code Reviewer | 缺陷、性能、可维护性审查 | GitHub、Filesystem |
| Security Auditor | OWASP、注入、密钥和鉴权检查 | GitHub、Fetch |
| Researcher | 网页获取、资料归纳和引用 | Fetch、Filesystem |
| BIM Engineer | Revit、施工和建筑数据问答 | Filesystem |

BIM Agent 的提示词提到了 Revit MCP bridge，但实际配置只有 Filesystem Server，并没有连接 Revit。能力边界应以 `mcp_servers` 的真实配置为准。

## 阅读代码时重点关注

1. `AGENTS` 如何绑定提示词和 MCP Server。
2. `classify_query()` 如何决定自动路由结果。
3. `connect_mcp_servers()` 如何收集工具并记录工具所属会话。
4. `run_agent_async()` 如何处理连续多轮 `tool_use`。
5. `AsyncExitStack` 如何统一关闭 MCP 连接。

## 金融场景改造

可以增加因子研究、风险审查、研报整理和数据质量 Agent。先把中文领域关键词加入 `classify_query()`，再为每个角色只开放必需工具。交易和文件写入工具应与只读工具分离，并在写操作前增加人工确认。

## 常见问题

- 配置 DeepSeek Key 后仍提示 Anthropic Key：这是当前实现限制，需要先适配客户端。
- 中文请求总被分给 Researcher：当前关键词主要是英文。
- MCP Server 启动失败：检查 Node.js、`npx` 和网络。
- GitHub 工具报权限错误：检查 Token，并只授予任务必需的权限。
