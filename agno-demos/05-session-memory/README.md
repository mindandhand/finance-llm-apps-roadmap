# 05 Session Memory：会话记忆

这是 `agno-demos/` 的第五个 demo。它在 `04-agentos-basic` 的基础上加入 SQLite session 持久化：同一个 `session_id` 的多轮请求会被保存，Agent 可以把最近历史加入上下文。

这个 demo 仍然不做自定义前端，先用 AgentOS 自带的 HTTP API 观察会话行为。

```text
AgentOS
  -> SqliteDb
  -> Agent(add_history_to_context=True)
  -> /agents/{agent_id}/runs
  -> /sessions
```

## 新增能力

- 使用 `SqliteDb` 保存 sessions 和 runs。
- 给 Agent 配置 `db=db`。
- 开启 `add_history_to_context=True`。
- 设置 `num_history_runs=3`，续问时只带最近几轮，避免上下文无限增长。
- 开启 `store_history_messages=True`，方便在数据库里复盘请求消息。
- 启用 AgentOS 的 `/sessions` 路由。

## Agno Session 是怎么跑起来的

Agno Session 的核心实现可以理解成一条链路：

```text
一次请求 -> run -> session -> database -> history/context
```

这不是“模型自己记住了”，而是 Agno 把每次调用包装成一个 `run`，再用 `session_id` 把多个 `run` 串起来，存到数据库里。下一次调用时，再按配置决定要不要把历史取出来放回模型上下文。

最小版本可以写成：

```python
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIResponses


agent = Agent(
    model=OpenAIResponses(id="gpt-5.2"),
    db=SqliteDb(db_file="agent.db"),
    add_history_to_context=True,
    num_history_runs=3,
)

agent.print_response(
    "我在分析沪深 300 ETF 最近为什么下跌",
    user_id="user_001",
    session_id="etf_300_thread",
)

agent.print_response(
    "那刚才提到的估值变化是什么意思？",
    user_id="user_001",
    session_id="etf_300_thread",
)
```

真正起作用的是这几个参数：

- `db`：把 session 和 runs 持久化。
- `user_id`：标识是哪位用户。
- `session_id`：标识是哪条对话线程。
- `add_history_to_context=True`：让 Agno 把历史放进模型上下文。
- `num_history_runs=3`：只放最近 3 轮，控制 token 成本。

Agno 的 Sessions 文档说明，`run_id` 标识一次执行，`session_id` 把相关 runs 归到一条线程，`user_id` 把 run/session 关联到用户；配置数据库后，session 记录才有持久化存储。文档也明确区分了 `db=...` 的持久化作用和 `add_history_to_context=True` 的上下文注入作用。来源：[Agno Sessions](https://docs.agno.com/sessions/overview)。

### 核心机制一：每次调用都是一个 run

用户发一次消息，Agent 执行一次，就是一个 `run`。

一次 `run` 通常包含：

- 用户输入。
- 模型回复。
- 工具调用。
- 中间结果。
- 运行指标。
- `run_id`。
- `session_id`。

单个 `run` 只代表一次交互。`Session` 负责把多次 `run` 串起来。

```text
session_id = etf_300_thread

run_1: 用户问“沪深 300 ETF 为什么跌”
run_2: 用户问“还能不能继续定投”
run_3: 用户问“刚才说的估值变化展开讲讲”
```

如果三个 `run` 使用同一个 `session_id`，Agno 就知道它们属于同一条对话。

### 核心机制二：Session 是一条对话线程

Session 不是 Memory。它更像一条聊天线程的档案。

Agno 的 session record 会保存这些字段：

| 字段 | 作用 |
|---|---|
| `session_id` | 对话线程 ID |
| `user_id` | 用户 ID |
| `runs` | 这条线程里的多次交互 |
| `metadata` | 自定义业务信息 |
| `session_data` | 会话状态 |
| `summary` | 长会话摘要 |
| `created_at` / `updated_at` | 创建和更新时间 |

Agno 的 Session Storage 文档说明，添加数据库后，runs 会按 `session_id` 持久化。默认 session 表是 `agno_sessions`，也可以通过 `session_table` 自定义表名；每条 session 记录包含 `session_id`、`session_type`、`agent_id`、`user_id`、`session_data`、`metadata`、`runs`、`summary` 等字段。来源：[Agno Session Storage](https://docs.agno.com/database/session-storage)。

在本 demo 里，表名配置在 `build_db()`：

```python
db = SqliteDb(
    db_file="data/session_memory.db",
    session_table="demo_05_sessions",
)
```

### 核心机制三：存下来，不等于放进上下文

这是最容易误解的地方。

Session 存在数据库里，只说明历史可查。模型下一次是否能看到历史，取决于 `add_history_to_context`。

```python
agent = Agent(
    db=SqliteDb(db_file="agent.db"),
    add_history_to_context=True,
    num_history_runs=3,
)
```

这表示：每次调用时，Agno 会从当前 `session_id` 对应的历史里取最近 3 轮，放进模型上下文。

如果不打开 `add_history_to_context`，历史仍然可以存，但模型不会自动看到它。Agno Sessions 文档中也把 `db=...`、`add_history_to_context=True` 和 `num_history_runs=N` 的效果分开说明。来源：[Agno Sessions](https://docs.agno.com/sessions/overview)。

### 核心机制四：长会话靠 summary 控制成本

如果一个 session 聊了几十轮，把所有历史都塞进上下文会很贵，也容易超过上下文窗口。

Agno 可以用 session summary 压缩长会话：

```python
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.models.openai import OpenAIResponses


agent = Agent(
    model=OpenAIResponses(id="gpt-5.2"),
    db=PostgresDb(
        db_url="postgresql+psycopg://ai:ai@localhost:5532/ai",
    ),
    enable_session_summaries=True,
    add_session_summary_to_context=True,
    add_history_to_context=True,
    num_history_runs=2,
)
```

这里的策略是：

- 老内容压成 `summary`。
- 最近 2 轮保留原始细节。
- 每次请求时，把 `summary + 最近历史` 放进上下文。

这样模型还能理解前文，但 token 不会随着对话轮数无限增长。Agno 的 Session Summaries 文档说明，session summaries 用于把长对话压缩成摘要，并可把摘要放进上下文来控制成本和上下文长度。来源：[Agno Session Summaries](https://docs.agno.com/sessions/session-summaries)。

### 核心机制五：Session 和 Memory 分工不同

这部分要讲清楚，否则很容易混。

Session History 解决的是：

```text
这条对话刚才说到哪了？
```

Memory 解决的是：

```text
这个用户长期有什么偏好？
```

| 内容 | 应该放哪里 |
|---|---|
| 用户刚才问了沪深 300 ETF | Session History |
| 用户偏好中文回答 | Memory |
| 用户上一轮要求展开估值变化 | Session History |
| 用户长期风险偏好低 | Memory |
| 用户常看宽基 ETF | Memory |

Agno Memory 文档把 Memory 定位为保存跨会话的用户事实、偏好和长期信息；而 session history 用于当前对话连续性。来源：[Agno Memory Overview](https://docs.agno.com/memory/overview)。

### 小结

Agno Session 的实现并不神秘。

它没有让模型“真的记住”。它做的是工程上的上下文管理：

1. 每次调用生成一个 `run`。
2. 用 `session_id` 把多个 `run` 串成一条线程。
3. 用 `db` 把线程持久化。
4. 用 `add_history_to_context` 决定是否把历史放回模型上下文。

这就是 Agno Session 的核心。它把“多轮对话”从 Prompt 技巧变成了可存储、可恢复、可审计的工程结构。

## 运行准备

在仓库根目录、`agno-demos/.env` 或本目录 `.env` 中配置：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_ID=deepseek-chat
```

加载优先级是：

```text
05-session-memory/.env -> agno-demos/.env -> 仓库根目录 .env
```

如果本机设置了不可用代理，真实 LLM 调用前可以临时清掉：

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
```

## 安装依赖

```bash
cd agno-demos/05-session-memory
pip install -r requirements.txt
```

## 运行

查看路由，不调用 LLM：

```bash
python session_memory_agentos.py --routes
```

查看数据库位置和 session 数量，不调用 LLM：

```bash
python session_memory_agentos.py --db-info
```

启动服务：

```bash
python session_memory_agentos.py
```

从统一脚本目录运行：

```bash
../script/run_05.sh
```

也可以从仓库上层目录同时启动 `05` 后端和 Agent UI：

```bash
../scripts/run_agno_05_agentos_ui.sh
```

脚本会启动：

```text
AgentOS: http://127.0.0.1:7778
Agent UI: Next.js dev server 输出的本地地址，通常是 http://localhost:3000
```

进入 Agent UI 后，把左侧 endpoint 改成：

```text
http://127.0.0.1:7778
```

默认服务地址：

```text
http://127.0.0.1:7778
```

默认 SQLite 文件：

```text
05-session-memory/data/session_memory.db
```

## 验证会话续问

使用一个固定 session id 发第一问：

```bash
curl -s -X POST http://127.0.0.1:7778/agents/finance-session-agent/runs \
  -F 'message=比较 SH510300 和 SH588000 的行情、新闻和因子，输出结构化摘要' \
  -F 'session_id=demo-session-001' \
  -F 'user_id=demo-user' \
  -F 'stream=false'
```

再用同一个 session id 发续问：

```bash
curl -s -X POST http://127.0.0.1:7778/agents/finance-session-agent/runs \
  -F 'message=刚才哪个标的波动率更高？请基于前面的分析回答。' \
  -F 'session_id=demo-session-001' \
  -F 'user_id=demo-user' \
  -F 'stream=false'
```

查看 sessions：

```bash
curl -s http://127.0.0.1:7778/sessions
```

当前注册的 Agent ID 是：

```text
finance-session-agent
```

## 你应该观察什么

- 第一次请求会创建 SQLite 数据库文件。
- `/sessions` 可以看到已有 session。
- 第二次请求使用同一个 `session_id` 时，Agent 会读取最近历史。
- `num_history_runs=3` 控制进入模型上下文的历史轮数。
- SQLite 保存的是 session/run 记录，不等于长期用户记忆。

## 和后续 demo 的关系

这个 demo 解决“会话如何保存、续问如何带历史”。后续会继续推进：

- `06-streaming-events`：把 token、工具调用和状态事件流式返回。
- `07-human-confirmation`：在高风险动作前加入人工确认。
- `08-team-research`：把多个角色的研究过程放入同一会话上下文。
