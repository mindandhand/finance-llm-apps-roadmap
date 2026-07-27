# 01 Hello Agent：最小 Agno Agent

这是 `agno-demos/` 的第一个 demo。它只做一件事：用 Agno 创建一个最小 Agent，并在终端里向 DeepSeek 发起一次流式回答。

这个 demo 暂时不接工具、不接 AgentOS、不接前端。先把最小闭环跑通：

```text
user prompt -> Agno Agent -> DeepSeek model -> streamed markdown response
```

## 新增能力

- 创建 `Agent`。
- 配置 DeepSeek 模型。
- 使用 `.env` 管理 API key、base URL 和模型名。
- 通过 `agent.print_response(..., stream=True)` 在终端流式输出。
- 用命令行参数传入不同 prompt。

## 运行准备

在仓库根目录、`agno-demos/.env` 或本目录 `.env` 中配置：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_ID=deepseek-chat
```

加载优先级是：

```text
01-hello-agent/.env -> agno-demos/.env -> 仓库根目录 .env
```

## 安装依赖

```bash
cd agno-demos/01-hello-agent
pip install -r requirements.txt
```

## 运行

使用默认问题：

```bash
python hello_agent.py
```

传入自定义问题：

```bash
python hello_agent.py "用一个金融研究例子解释 Agent 和普通脚本的区别"
```

关闭流式输出：

```bash
python hello_agent.py --no-stream "解释 Agno Agent 的最小组成"
```

## 你应该观察什么

运行成功后，终端会直接输出 Markdown 回答。这个 demo 的重点不是回答内容，而是确认：

- Agno 能正常导入。
- DeepSeek 模型配置能被读取。
- Agent 能接收 prompt。
- streaming 输出能正常显示。

## 和后续 demo 的关系

后续 demo 会在这个最小 Agent 上逐步增加能力：

- `02-agent-with-finance-tools`：加入金融工具调用。
- `03-structured-output`：把回答约束成可解析结构。
- `04-agentos-basic`：把 Agent 暴露成 AgentOS 服务。
- `05-session-memory`：加入会话记忆和历史续问。
