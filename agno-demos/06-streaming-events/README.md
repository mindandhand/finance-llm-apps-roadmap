# 06 Streaming Events：流式内容与工具状态

这是 `agno-demos/` 的第六个 demo。它展示的不只是逐字输出，而是一条可供终端或前端消费的完整运行事件流：

```text
RunStarted
  -> ToolCallStarted
  -> ToolCallCompleted
  -> RunContent（多次）
  -> RunCompleted / RunError
```

本目录可以独立运行，不要求先复制 `04-agentos-basic` 或 `05-session-memory` 的代码。它暂不实现历史记忆，重点只放在 streaming 和事件边界。

## 新增能力

- 使用 `stream=True` 流式返回回答内容。
- 使用 `stream_events=True` 同时获得工具开始、工具完成和运行状态。
- 在终端中区分内容 chunk 与状态事件。
- 通过 AgentOS 把同一个 Agent 暴露为 SSE 接口。
- 提供 `--sample-events`，无需 API key 即可观察事件形态。

## 安装依赖

```bash
cd agno-demos/06-streaming-events
python3 -m pip install -r requirements.txt
```

## 配置

在仓库根目录、`agno-demos/.env` 或本目录 `.env` 中配置：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_ID=deepseek-chat
```

加载优先级为：

```text
06-streaming-events/.env -> agno-demos/.env -> 仓库根目录 .env
```

## 终端观察事件

先查看不调用模型的稳定事件样例：

```bash
python3 streaming_events_agent.py --sample-events
```

运行真实 Agent：

```bash
python3 streaming_events_agent.py
```

传入自定义问题：

```bash
python3 streaming_events_agent.py "分析 SH588000 的样例波动率，并说明工具调用过程"
```

也可以从 `agno-demos/` 目录运行：

```bash
./script/run_06.sh --sample-events
```

终端中，正文会连续输出；生命周期和工具状态使用 `[event]` 单独标记。前端可用同样的事件分别渲染回答、进度条和工具卡片。

## 启动 AgentOS

```bash
python3 streaming_events_agent.py --serve
```

默认地址：

- API 文档：`http://127.0.0.1:7777/docs`
- AgentOS 配置：`http://127.0.0.1:7777/config`
- 健康检查：`http://127.0.0.1:7777/health`

也可以使用环境变量或参数修改监听地址：

```bash
AGENT_OS_PORT=8000 python3 streaming_events_agent.py --serve
python3 streaming_events_agent.py --serve --host 0.0.0.0 --port 8000
```

## 用 curl 消费 SSE

先从 `/docs` 或下面的接口取得 Agent 列表：

```bash
curl http://127.0.0.1:7777/agents
```

再发起流式运行。AgentOS 的 run 接口使用 multipart form：

```bash
curl -N -X POST \
  http://127.0.0.1:7777/agents/streaming-finance-agent/runs \
  -F 'message=比较 SH510300 和 SH588000 的波动率' \
  -F 'stream=true'
```

`-N` 会关闭 curl 的输出缓冲，因此 SSE 事件可以到达一条显示一条。

## 你应该观察什么

- `RunContent` 是可直接追加到消息气泡的文本 chunk。
- `ToolCallStarted` 适合把工具卡片切换为“执行中”。
- `ToolCallCompleted` 带工具结果，适合显示摘要、耗时或失败原因。
- `RunCompleted` 和 `RunError` 用于结束 loading 状态。
- 工具返回的是本地固定样例，不是实时行情，也不构成投资建议。

## 与前后 demo 的关系

- `05-session-memory` 负责“同一会话记住什么”。
- 本 demo 负责“运行过程中实时发生了什么”。
- `07-human-confirmation` 会在事件流中加入暂停、确认、拒绝和继续。
- `10-agui-fastapi` 会进一步把事件转换为面向前端的标准 AG-UI 协议。
