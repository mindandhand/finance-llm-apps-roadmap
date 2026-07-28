## AI 金融分析 Agent

这个应用是一个金融分析 Agent，使用 DeepSeek 模型服务，并结合实时股票数据和网页搜索能力，提供结构化的金融分析结果。

### 功能

- 支持 DeepSeek API
- 通过 YFinance 获取实时股票数据
- 通过 DuckDuckGo 进行网页搜索
- 金融和数值数据会优先用表格展示
- 提供 AgentOS 交互式界面

### 快速开始

1. 进入项目目录

```bash
cd 01-ai_finance_agent
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 配置模型服务

在 `01-ai_finance_agent/.env` 或仓库根目录 `finance-llm-agent-demos/.env` 中填入你的 DeepSeek API key、服务地址和模型名：
```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_ID=deepseek-chat
```

如果需要使用其他 DeepSeek 模型，可以把 `DEEPSEEK_MODEL_ID` 设置为服务支持的模型名，例如 `deepseek-chat`、`deepseek-reasoner`、`deepseek-v4-flash` 或 `deepseek-v4-pro`。

4. 运行 AgentOS API
```bash
python finance_agent.py
```

也可以从 `finance-llm-agent-demos` 仓库根目录运行：

```bash
./scripts/run_01_agent.sh
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

- 请分析 AAPL 最近的股价表现，并用表格展示关键数据。
- TSLA 当前股价是多少？最近有哪些重要新闻？
- 比较 MSFT 和 GOOGL 的市值、PE、52 周高低点和近期表现。
- NVDA 最近的上涨或下跌主要可能由哪些因素驱动？
- 请给出 AMZN 的公司概况、主营业务和最近市场情绪。
- 找出 META 最近的相关新闻，并总结可能影响股价的风险点。
- 请用表格列出 JPM 的当前价格、成交量、市值和分析师建议。
- 我想了解苹果公司的财务健康状况，请先查实时数据再给出要点。

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
