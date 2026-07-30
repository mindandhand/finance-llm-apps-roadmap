# 11 Next.js Chat UI：聊天前端

这个 demo 是一个最小 Next.js 聊天界面，用来消费 10 的官方 AG-UI `/agui` SSE 接口。它包含线程 ID、流式消息区域、工具事件和运行状态。

## 运行

先启动 10：

```bash
cd agno-demos
./script/run_10.sh --serve --port 7777
```

再启动 11：

```bash
cd agno-demos/11-nextjs-chat-ui
npm install
NEXT_PUBLIC_AGUI_URL=http://127.0.0.1:7777 npm run dev
```

默认访问 `http://127.0.0.1:3000`。

## 执行流程

```text
用户在输入框提交问题
        |
        v
Next.js fetch POST /agui/runs
        |
        v
读取 SSE response.body
        |
        +--> tool_call_started / tool_call_completed -> Tools 区域
        +--> text_delta -> 持续追加到回答区域
        |
        v
SSE 流结束，保留最终回答和工具事件
```

前端通过 `NEXT_PUBLIC_AGUI_URL` 找到 10 的服务端。它不直接调用模型，也不实现工具逻辑，只负责发送 AG-UI `RunAgentInput`、解析 `data.type` 和更新界面状态。先启动 10，再启动 11，才能看到完整链路。
