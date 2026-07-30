# 12 Finance Research Console：交互式研究台

这个 demo 把 10 的 AG-UI Agent 运行整理成研究台形态：任务提交、状态查看、事件时间线、报告预览和 artifact 下载。

## 运行

```bash
cd agno-demos
./script/run_12.sh --sample-task
./script/run_12.sh --serve --port 7777
```

12 默认连接 `http://127.0.0.1:7777` 的 10 服务。可以用 `AGUI_AGENT_URL` 指定其他地址：

```bash
AGUI_AGENT_URL=http://127.0.0.1:7780 ./script/run_12.sh --serve --port 7777
```

接口：

- `POST /api/tasks`
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `GET /api/tasks/{task_id}/report`

浏览器访问 `http://127.0.0.1:7777/` 可以提交任务并预览报告。

## 执行流程

```text
浏览器提交研究主题
        |
        v
POST /api/tasks
        |
        v
创建 task_id，状态 pending
        |
        v
后台调用 10 的 POST /agui
        |
        v
保存 AG-UI 事件时间线
        |
        v
生成 Markdown artifact，状态 completed
        |
        +--> GET /api/tasks/{task_id} 查看状态和事件
        +--> GET /api/tasks/{task_id}/report 预览报告
```

12 是产品层控制台，10 是 Agent 层。12 的任务会异步调用 10，页面轮询任务状态；如果 10 或模型不可用，任务会进入 `failed`，错误会保留在任务记录中。`--sample-task` 仍然提供不依赖 10 的离线 artifact 测试。
