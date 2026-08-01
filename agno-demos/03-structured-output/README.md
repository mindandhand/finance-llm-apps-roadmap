# 03 Structured Output：结构化输出

这是 `agno-demos/` 的第三个 demo。它在 `02-agent-with-finance-tools` 的基础上增加 Pydantic 输出模型：工具返回结构化事实，Agent 的最终回答也必须变成可解析 JSON。

这个 demo 仍然只在终端运行，不接 AgentOS，不接前端。

```text
user prompt
  -> Agno Agent
  -> local finance tools
  -> Pydantic output schema
  -> validated JSON
```

## 新增能力

- 定义 `ResearchBrief`、`SymbolAssessment`、`EvidenceItem` 三层 Pydantic schema。
- 使用 `Agent(output_schema=ResearchBrief)` 约束最终输出。
- 把 Agent 返回内容校验成 Pydantic 对象，再打印为 JSON。
- 增加 `--schema`，可以不调用 LLM 查看 JSON schema。
- 增加 `--sample`，可以不调用 LLM 查看稳定样例输出。
- 当模型输出不符合 schema 时，显示校验错误和原始内容。

## 为什么要做结构化输出

自然语言回答适合人读，但不适合后续系统消费。进入 AgentOS 和前端之前，至少要把这些字段固定下来：

- `summary`：一句话摘要。
- `assessments`：每个标的的结构化判断。
- `evidence`：每个判断引用了哪些工具事实。
- `comparison`：跨标的比较。
- `caveats`：数据和投资建议边界。
- `next_questions`：可继续追问的方向。

后续前端可以直接把这些字段渲染成摘要区、风险卡片、证据列表和追问按钮。

## 运行准备

在仓库根目录、`agno-demos/.env` 或本目录 `.env` 中配置：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_ID=deepseek-chat
```

加载优先级是：

```text
03-structured-output/.env -> agno-demos/.env -> 仓库根目录 .env
```

## 安装依赖

```bash
cd agno-demos/03-structured-output
pip install -r requirements.txt
```

## 运行

先不调用 LLM，只看输出 schema：

```bash
python structured_output_agent.py --schema
```

查看稳定样例输出：

```bash
python structured_output_agent.py --sample
```

使用默认问题调用 Agent：

```bash
python structured_output_agent.py
```

从统一脚本目录运行：

```bash
../script/run_03.sh
```

传入自定义问题：

```bash
python structured_output_agent.py "用结构化 JSON 比较 SH510300 和 SH588000 的风险差异"
```

## 你应该观察什么

运行成功后，终端输出的是 JSON，而不是 Markdown。重点确认：

- JSON 字段和 `ResearchBrief` schema 一致。
- `risk_score` 被限制在 0 到 100。
- `risk_level` 只能是 `low`、`medium`、`high`。
- `evidence` 里能看到工具数据源、标的和字段。
- `caveats` 明确说明本地样例数据不是实时行情，也不是投资建议。

## 常见错误

如果看到 `Structured output validation failed.`，说明模型返回内容没有通过 Pydantic 校验。这个错误是本 demo 想展示的重点之一：结构化输出失败时，后端应该明确失败，而不是把不可解析文本传给前端。

可以先用更明确的 prompt 重试：

```bash
python structured_output_agent.py "请严格按 ResearchBrief schema 输出，比较 SH510300 和 SH588000"
```

## 和后续 demo 的关系

这个 demo 解决“Agent 的最终输出如何被程序稳定解析”。后续会继续推进：

- `04-agentos-basic`：把结构化 Agent 暴露成 AgentOS 服务。
- `05-session-memory`：把结构化结果和会话状态关联起来。
- `06-streaming-events`：在流式输出中展示工具进度和状态事件。
