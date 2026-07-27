# 02 Agent With Finance Tools：金融工具调用

这是 `agno-demos/` 的第二个 demo。它在 `01-hello-agent` 的基础上增加 Agno tools：Agent 不再只靠模型直接回答，而是可以调用受控 Python 函数读取行情、新闻和因子样例数据。

这个 demo 仍然只在终端运行，不接 AgentOS，不接前端。

```text
user prompt
  -> Agno Agent
  -> local finance tools
  -> DeepSeek model
  -> streamed markdown response
```

## 新增能力

- 把普通 Python 函数注册为 Agno tools。
- 用本地样例数据模拟行情、新闻和因子查询。
- 通过工具函数返回结构化结果，而不是让模型编造市场事实。
- 增加 `--show-tools`，可以不调用 LLM 直接查看工具输出。

## 工具列表

本 demo 注册了三个工具：

- `get_market_snapshot(symbol)`：读取本地行情快照。
- `get_latest_news(symbol, limit=2)`：读取本地新闻摘要。
- `get_factor_summary(symbol)`：读取本地因子摘要。

当前支持两个样例标的：

- `SH510300`：沪深300ETF。
- `SH588000`：科创50ETF。

## 运行准备

在仓库根目录、`agno-demos/.env` 或本目录 `.env` 中配置：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_ID=deepseek-chat
```

加载优先级是：

```text
02-agent-with-finance-tools/.env -> agno-demos/.env -> 仓库根目录 .env
```

## 安装依赖

```bash
cd agno-demos/02-agent-with-finance-tools
pip install -r requirements.txt
```

## 运行

先不调用 LLM，只看工具输出：

```bash
python finance_tools_agent.py --show-tools
```

使用默认问题调用 Agent：

```bash
python finance_tools_agent.py
```

从统一脚本目录运行：

```bash
../script/run_02.sh
```

传入自定义问题：

```bash
python finance_tools_agent.py "比较 SH510300 和 SH588000 的波动差异，说明数据来源"
```

关闭流式输出：

```bash
python finance_tools_agent.py --no-stream "分析 SH588000 的新闻和因子摘要"
```

## 你应该观察什么

运行时重点看三件事：

- Agent 会先调用工具获取结构化事实。
- 回答中应该引用工具返回的数据源和日期。
- 工具数据是本地样例，不是实时行情，也不能用于交易决策。

## 和后续 demo 的关系

这个 demo 解决“Agent 如何使用工具”。后续会继续推进：

- `03-structured-output`：把 Agent 的最终回答约束成 Pydantic schema。
- `04-agentos-basic`：把 Agent 暴露成 AgentOS 服务。
- `05-session-memory`：加入 session 和历史上下文。
