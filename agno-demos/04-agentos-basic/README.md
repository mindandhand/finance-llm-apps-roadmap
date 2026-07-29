# 04 AgentOS Basic：AgentOS 服务化

这是 `agno-demos/` 的第四个 demo。它把前面已经能调用工具、能输出结构化结果的金融 Agent 注册到 Agno AgentOS，并暴露为本地 FastAPI 服务。

这个 demo 仍然不做前端、不做数据库、不做会话记忆。先把服务化最小闭环跑通：

```text
Agno Agent
  -> AgentOS(agents=[...])
  -> FastAPI app
  -> /health /docs /agents/{agent_id}/runs
```

## 新增能力

- 创建 `AgentOS`。
- 把一个 Agno `Agent` 注册到 AgentOS。
- 暴露 FastAPI `app`，可被 `uvicorn` 加载。
- 使用 `/health` 验证服务是否启动。
- 使用 `/docs` 查看 AgentOS 自动生成的 Swagger 文档。
- 使用 `/agents/finance-research-agent/runs` 通过 HTTP 调用 Agent。

## 运行准备

在仓库根目录、`agno-demos/.env` 或本目录 `.env` 中配置：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_ID=deepseek-chat
```

加载优先级是：

```text
04-agentos-basic/.env -> agno-demos/.env -> 仓库根目录 .env
```

如果本机设置了不可用代理，可能需要临时清掉代理环境变量：

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
```

## 安装依赖

```bash
cd agno-demos/04-agentos-basic
pip install -r requirements.txt
```

## 运行

先不启动服务，只查看路由：

```bash
python agentos_basic.py --routes
```

启动服务：

```bash
python agentos_basic.py
```

从统一脚本目录运行：

```bash
../script/run_04.sh
```

指定端口：

```bash
python agentos_basic.py --port 7788
```

启动后访问：

```text
http://127.0.0.1:7777/health
http://127.0.0.1:7777/docs
```

## HTTP 调用 Agent

AgentOS 的 agent run 接口接收表单字段。可以用 `curl` 测试：

```bash
curl -s -X POST http://127.0.0.1:7777/agents/finance-research-agent/runs \
  -F 'message=比较 SH510300 和 SH588000 的行情、新闻和因子，输出结构化摘要' \
  -F 'stream=false'
```

当前注册的 Agent ID 是：

```text
finance-research-agent
```

## 你应该观察什么

这个 demo 的重点不是回答内容，而是确认：

- `AgentOS(...).get_app()` 可以生成 FastAPI app。
- `/health` 能返回服务状态。
- `/docs` 能看到 AgentOS 自动暴露的 agents、sessions、memory 等路由。
- `POST /agents/finance-research-agent/runs` 能调用同一个结构化金融 Agent。
- 没有传数据库时，session、memory、approvals 等需要 db 的能力还不能真正使用。

## 和后续 demo 的关系

这个 demo 解决“Agent 如何变成本地服务”。后续会继续推进：

- `05-session-memory`：加入 session、storage 和历史上下文。
- `06-streaming-events`：展示 token streaming、工具进度和状态事件。
- `07-human-confirmation`：在高风险动作前加入人工确认。
