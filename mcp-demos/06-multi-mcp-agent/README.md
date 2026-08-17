# 06 多 MCP 智能助手

这个示例让一个 Agent 同时连接 GitHub、Perplexity、Calendar 和 Gmail 四个 MCP Server。重点是理解 Agent 如何发现工具、跨服务调用工具，并在一次对话中完成组合任务。

## 学习目标

- 使用 `MultiMCPTools` 管理多个 stdio MCP Server；
- 理解模型、Agent、MCP Client 与 MCP Server 的职责边界；
- 为不同服务注入独立凭证；
- 串联搜索、代码仓库、日历和邮件工具；
- 使用 SQLite 保存对话记录和用户记忆。

## 默认模型

默认使用 `deepseek-v4-pro`。多 MCP 场景包含多轮工具选择、参数生成和结果汇总，优先使用能力更完整的 Pro 模型。只有专项模型经过实际任务集评测后明显更好，才建议更换。

当前代码通过上级目录的 `llm_config.py` 创建 OpenAI-compatible 模型，可以使用 DeepSeek 接口。不过共享配置中的默认值可能仍是已经停用的 `deepseek-chat`，运行时应显式指定 V4 模型。

## 关键文件

- `multi_mcp_agent.py`：环境校验、MCP Server 配置、Agent 和命令行会话。
- `requirements.txt`：Python 依赖。
- `../llm_config.py`：OpenAI-compatible 模型配置。
- `tmp/multi_mcp_agent.db`：运行后生成的 SQLite 数据库。

## 架构

```text
用户输入
  ↓
Agno Agent + DeepSeek V4 Pro
  ↓
MultiMCPTools
  ├─ GitHub MCP
  ├─ Perplexity MCP
  ├─ Calendar MCP
  └─ Gmail MCP
```

四个 Server 都由 `npx` 作为子进程启动，并通过 stdio 与 Python 程序通信。Agent 看到合并后的工具列表，每次操作仍由对应的 MCP Server 执行。

## 运行

```bash
pip install -r requirements.txt
node --version
npx --version
```

新建 `.env`：

```env
DEEPSEEK_API_KEY=your-deepseek-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-pro
GITHUB_PERSONAL_ACCESS_TOKEN=your-github-token
PERPLEXITY_API_KEY=your-perplexity-key
```

启动：

```bash
python multi_mcp_agent.py
```

Calendar 和 Gmail Server 首次启动时可能要求浏览器授权。代码会同时连接全部 Server，任何必需服务初始化失败都可能阻止程序进入对话。

## 可以尝试

- “查找我最近更新的 GitHub 仓库，并总结主要改动。”
- “搜索最新的 MCP 资料，并在下周创建一个学习日程。”
- “整理本周待处理的 issue，并起草一封进度邮件。”

跨服务请求最能体现本示例的价值。执行写操作前，应让 Agent 复述目标、对象和参数，并为邮件发送、日历创建等操作增加人工确认。

## 阅读代码时重点关注

1. `mcp_servers` 如何声明四个 Server 的启动命令。
2. `env` 如何把凭证传给 MCP 子进程。
3. `async with MultiMCPTools(...)` 如何管理连接生命周期。
4. `tools=[mcp_tools]` 如何把全部 MCP 工具交给 Agent。
5. `SqliteDb`、`user_id` 和 `session_id` 如何参与记忆管理。

程序每次启动都会生成新的 `user_id` 和 `session_id`。数据库会保存记录，但当前实现不会自动恢复上一次终端会话。

## 金融场景改造

可以把四类服务组合成投研工作流：搜索市场信息、检查策略仓库、创建调研日程、发送研究摘要。建议先把写操作改为“生成草稿”，确认后再创建日历或发送邮件。

## 常见问题

- 缺少环境变量：程序会在启动时列出缺失项。
- `npx` 启动失败：检查 Node.js、网络和包下载权限。
- GitHub 操作无权限：检查 Token 的仓库范围，坚持最小权限原则。
- Gmail 或 Calendar 未连接：重新完成首次 OAuth 授权。
- 模型找不到：确认已设置 `OPENAI_MODEL=deepseek-v4-pro`。
