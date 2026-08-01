## AI 金融 Agent 团队

这个应用是一个多 Agent 金融研究团队，使用 DeepSeek 模型服务，并结合 DuckDuckGo 网页搜索、Yahoo Finance 金融数据和 SQLite 会话记录，生成结构化公司研究与金融分析结果。

### 功能

- 支持 DeepSeek API
- 网页研究员负责检索公司新闻、市场背景和公开信息
- 金融数据分析师负责获取股票行情、公司信息、新闻和分析师建议
- Team Agent 负责协调两个 Agent 并汇总最终分析
- 金融和数值数据会优先用表格展示
- 使用 SQLite 保存 Agent 交互记录
- 提供 AgentOS 交互式界面

### 快速开始

1. 进入项目目录

```bash
cd 04-ai_finance_agent_team
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 配置模型服务

在 `04-ai_finance_agent_team/.env` 或仓库根目录 `finance-llm-agent-demos/.env` 中填入你的 DeepSeek API key、服务地址和模型名：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_ID=deepseek-chat
```

如果需要使用其他 DeepSeek 模型，可以把 `DEEPSEEK_MODEL_ID` 设置为服务支持的模型名，例如 `deepseek-chat`、`deepseek-reasoner`、`deepseek-v4-flash` 或 `deepseek-v4-pro`。

4. 运行 AgentOS API

```bash
python finance_agent_team.py
```

也可以从 `finance-llm-agent-demos` 仓库根目录运行：

```bash
./scripts/run_04_agent.sh
```

启动成功后，本地服务会运行在：

```text
http://localhost:7777
```

直接访问这个地址会看到 AgentOS API 信息。要使用图形化聊天界面，请在工作区根目录启动本地 AgentUI：

```bash
cd ..
./scripts/run_agent_ui.sh
```

然后打开：

```text
http://localhost:3000
```

并在 AgentUI 中连接本地 AgentOS 服务：

```text
http://localhost:7777
```

也可以先用本地 API 文档确认 AgentOS 服务正常：

```text
http://localhost:7777/docs
```

### 示例问题

可以在 AgentUI 中尝试下面这些问题：

- 请研究 NVDA 的最新市场动态、当前股价、公司信息和分析师建议，并给出风险点。
- 比较 AAPL 和 MSFT 的近期表现、新闻背景和基本面信息。
- 请分析 TSLA 最近股价波动可能受哪些新闻和基本面因素影响。
- 研究 JPM 的当前股价、公司概况、相关新闻和分析师建议，并用表格展示关键数据。
- 请给出 AMZN 的公司研究摘要，包括最新新闻、关键财务数据和谨慎结论。
- 对比 GOOGL、META 和 AMZN 的市场叙事、风险因素和投资关注点。
- 请为 COST 生成一份公司研究报告，包含网页信息、金融数据表和风险提示。
- 找出近期可能影响 AMD 的重要新闻，并结合当前股价数据做分析。

### 访问方式说明

`http://localhost:7777` 是本地 AgentOS API 服务，不是聊天网页。直接打开它通常只会看到类似下面的 JSON，表示服务已经启动：

```json
{"name":"AgentOS API","id":"...","version":"1.0.0"}
```

图形化聊天界面由工作区内的本地 AgentUI 提供：

```text
http://localhost:3000
```

本地 Python 进程负责运行 Agent、Team 和工具调用，AgentUI 负责展示聊天、会话和运行管理界面。AgentUI 连接的本地 AgentOS 地址是：

```text
http://localhost:7777
```

如果聊天界面无法使用，可按下面顺序排查：

1. 打开 `http://localhost:7777/docs`，能看到 Swagger 页面说明本地服务正常。
2. 打开 `http://localhost:3000`，确认本地 AgentUI 正常启动。
3. 在 AgentUI 中连接 `http://localhost:7777`。

本项目不额外自写 Streamlit 页面，原因是它已经使用 Agno 的 `AgentOS` 运行方式。本地 AgentUI 正好匹配这套 API，可以复用 AgentOS 的会话、运行记录和后续管理能力；自写页面会绕开这些能力，并引入额外的前端和 Python 环境依赖。

> 本项目仅用于技术学习与原型验证，不构成投资、税务、保险或法律建议。
