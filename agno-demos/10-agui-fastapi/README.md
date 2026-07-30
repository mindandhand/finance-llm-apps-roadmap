# 10 AG-UI Finance Research：Agno 接入标准前端协议

10 现在展示的不是手写 SSE，而是完整的适配链路：

```text
Agno Agent
   -> Agno RunEvent
   -> Agno 官方 AGUI interface
   -> 标准 AG-UI SSE
   -> 11 或其他前端
```

AG-UI 是 Agent 和前端之间的开放事件协议，不属于 Agno。Agno 负责运行 Agent，`AGUI` 负责把 Agno 事件编码成前端可以消费的标准事件。

## 这个例子做什么

这是一个金融研究 Agent，包含三个本地工具：

- `get_market_snapshot`：行情样例
- `get_factor_snapshot`：动量和波动率样例
- `get_news_packet`：新闻样例

用户提问后，Agent 会根据需要调用工具，AG-UI 会通过 SSE 推送运行事件。数据是固定样例，不依赖行情网络；模型仍需要使用上层 `.env` 中的 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY`。

## 运行

安装依赖：

```bash
cd agno-demos/10-agui-fastapi
python -m pip install -r requirements.txt
```

启动：

```bash
./script/run_10.sh --serve --port 7777
```

检查服务：

```bash
curl -s http://127.0.0.1:7777/health
curl -s http://127.0.0.1:7777/
```

## AG-UI 请求格式

AG-UI 的请求不是旧版的 `{message: "..."}`，而是包含线程、运行和消息的结构：

```json
{
  "threadId": "finance-thread-001",
  "runId": "run-001",
  "state": {},
  "messages": [
    {
      "id": "message-001",
      "role": "user",
      "content": "比较 SH510300 和 SH588000 的行情、新闻和因子"
    }
  ],
  "tools": [],
  "context": [],
  "forwardedProps": {}
}
```

发送到：

```text
POST http://127.0.0.1:7777/agui
Content-Type: application/json
Accept: text/event-stream
```

curl 示例：

```bash
curl -N -X POST http://127.0.0.1:7777/agui \
  -H 'content-type: application/json' \
  -H 'accept: text/event-stream' \
  -d '{
    "threadId":"finance-thread-001",
    "runId":"run-001",
    "state":{},
    "messages":[{"id":"message-001","role":"user","content":"比较 SH510300 和 SH588000 的行情、新闻和因子"}],
    "tools":[],
    "context":[],
    "forwardedProps":{}
  }'
```

## 执行流程

```text
用户消息
   |
   v
POST /agui
   |
   v
AGUI 读取 threadId、runId、messages
   |
   v
Agno Agent 规划研究任务
   |
   +--> get_market_snapshot
   +--> get_factor_snapshot
   +--> get_news_packet
   |
   v
Agno RunEvent
   |
   v
AGUI 编码为标准 SSE 事件
   |
   +--> RUN_STARTED
   +--> TOOL_CALL_START / TOOL_CALL_ARGS / TOOL_CALL_END
   +--> TEXT_MESSAGE_START / TEXT_MESSAGE_CONTENT / TEXT_MESSAGE_END
   +--> RUN_FINISHED 或 RUN_ERROR
   |
   v
前端更新回答、工具时间线和错误状态
```

## 和 06、11 的关系

```text
06：观察 Agno 原生 RunEvent
10：把 Agno RunEvent 适配为标准 AG-UI
11：消费 AG-UI SSE，显示聊天和工具时间线
```

因此 10 不是另一个聊天页面，也不是重复实现 06。它是 Agno 和前端之间的协议适配层。11 后续应改为调用 `/agui`，而不是继续解析旧的 `/agui/runs` 自定义事件。
