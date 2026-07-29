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
