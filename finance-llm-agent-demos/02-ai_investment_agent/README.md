## AI 投资分析 Agent

这个应用是一个投资分析 Agent，使用 DeepSeek 模型服务，并结合 Yahoo Finance 数据，比较股票表现、检索公司信息，并生成结构化投资分析报告。

### 功能

- 支持 DeepSeek API
- 通过 YFinance 获取股票行情、公司信息、新闻和分析师建议
- 支持两只或多只股票的比较分析
- 金融和数值数据会优先用表格展示
- 提供 AgentOS 交互式界面

### 快速开始

1. 进入项目目录

```bash
cd 02-ai_investment_agent
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 配置模型服务

在 `02-ai_investment_agent/.env` 或仓库根目录 `finance-llm-agent-demos/.env` 中填入你的 DeepSeek API key、服务地址和模型名：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_ID=deepseek-chat
```

如果需要使用其他 DeepSeek 模型，可以把 `DEEPSEEK_MODEL_ID` 设置为服务支持的模型名，例如 `deepseek-chat`、`deepseek-reasoner`、`deepseek-v4-flash` 或 `deepseek-v4-pro`。

4. 运行 AgentOS API

```bash
python investment_agent.py
```

也可以从 `finance-llm-agent-demos` 仓库根目录运行：

```bash
./scripts/run_02_agent.sh
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

- 比较 AAPL 和 MSFT 的近期股价表现、基本面和分析师建议。
- 如果只能在 NVDA 和 AMD 中选一只，请基于公开数据做投资对比。
- 比较 TSLA 和 BYDDF 的估值、增长叙事、风险和市场情绪。
- 请为 GOOGL、META 和 AMZN 做一份三家公司投资对比表。
- 对比 JPM 和 BAC 的财务表现、股息情况和潜在风险。
- 请分析 COST 和 WMT 哪个更适合防御型投资组合。
- 比较 KO 和 PEP 的基本面、估值和长期稳定性。
- 请生成一份关于 MSFT vs AAPL 的投资报告，包括结论、关键数据和风险提示。

### 访问方式说明

`http://localhost:7777` 是本地 AgentOS API 服务，不是聊天网页。直接打开它通常只会看到类似下面的 JSON，表示服务已经启动：

```json
{"name":"AgentOS API","id":"...","version":"1.0.0"}
```

图形化聊天界面由工作区内的本地 AgentUI 提供：

```text
http://localhost:3000
```

本地 Python 进程负责运行 Agent 和工具调用，AgentUI 负责展示聊天、会话和运行管理界面。AgentUI 连接的本地 AgentOS 地址是：

```text
http://localhost:7777
```

如果聊天界面无法使用，可按下面顺序排查：

1. 打开 `http://localhost:7777/docs`，能看到 Swagger 页面说明本地服务正常。
2. 打开 `http://localhost:3000`，确认本地 AgentUI 正常启动。
3. 在 AgentUI 中连接 `http://localhost:7777`。

本项目不额外自写 Streamlit 页面，原因是它已经使用 Agno 的 `AgentOS` 运行方式。本地 AgentUI 正好匹配这套 API，可以复用 AgentOS 的会话、运行记录和后续管理能力；自写页面会绕开这些能力，并引入额外的前端和 Python 环境依赖。
