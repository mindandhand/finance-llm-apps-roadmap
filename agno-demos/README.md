# Agno Demos：从入门 Agent 到交互友好的前后端

这是一条面向本仓库的 Agno 学习和实现路线。目标不是堆很多独立 demo，而是逐步回答一个具体问题：

```text
如何用 Agno 把金融 Agent 从一个 Python 脚本，推进到可调试、可交互、可接前端的本地应用？
```

## 定位

本目录建议作为 `awesome-llm-apps/` 的前置工程化学习线：

- `awesome-llm-apps/`：偏完整金融应用。
- `agent-demos/`：偏 Agent 原理、状态、工具边界和研究约束。
- `agno-demos/`：偏 Agno 框架、AgentOS 服务化、前后端交互和产品化体验。

## 核心主线

Agno 的学习路径可以按这条线组织：

```text
Agent
  ↓
Tools
  ↓
Memory / Storage
  ↓
Team
  ↓
Workflow
  ↓
AgentOS
  ↓
AG-UI / AgentUI / 自定义前端
```

其中前半段解决 Agent 能力，后半段解决工程交付：

- Agent 负责理解任务、调用工具、生成答案。
- Tool 负责确定性数据读取、计算、检索和外部动作。
- Memory / Storage 负责会话、偏好和可追溯记录。
- Team 负责多角色协作，不用来替代事实校验。
- Workflow 负责可控步骤编排。
- AgentOS 负责把 Agent、Team、Workflow 暴露为 FastAPI 服务。
- AG-UI 或自定义前端负责把流式输出、工具状态、确认动作和结果展示做成友好的交互体验。

## 学习路径

| # | 目录 | 主题 | 新增能力 | 前端形态 |
|---|---|---|---|---|
| 1 | `01-hello-agent` | 最小 Agno Agent | 跑通模型调用、指令和 Markdown 输出 | 终端 |
| 2 | `02-agent-with-finance-tools` | 金融工具调用 | 行情、新闻、指标查询工具 | 终端 |
| 3 | `03-structured-output` | 结构化输出 | Pydantic schema、可解析 JSON、错误提示 | 终端 |
| 4 | `04-agentos-basic` | AgentOS 服务化 | FastAPI app、`/docs`、本地服务启动 | Swagger / AgentOS |
| 5 | `05-session-memory` | 会话记忆 | session、历史上下文、用户偏好 | AgentUI |
| 6 | `06-streaming-events` | 流式交互 | token streaming、工具进度、状态事件 | AgentUI |
| 7 | `07-human-confirmation` | 人工确认 | 高风险操作前暂停、确认、拒绝和修改 | AgentUI |
| 8 | `08-team-research` | 多 Agent 金融研究团队 | Researcher、Analyst、Reviewer 分工 | AgentUI |
| 9 | `09-workflow-report` | 工作流生成报告 | 固定步骤、artifact、最终报告文件 | AgentUI |
| 10 | `10-agui-fastapi` | AG-UI 接口 | 面向前端的标准事件协议 | 自定义前端 |
| 11 | `11-nextjs-chat-ui` | Next.js 聊天前端 | 会话列表、流式消息、工具卡片 | Web UI |
| 12 | `12-finance-research-console` | 交互式研究台 | 表单输入、任务状态、报告预览、下载 | Web UI |

## Agno 应用专家补充路径

前 12 个 demo 的目标是达到 Agno 应用工程能力。要继续推进到 Agno 应用专家水平，重点不是研究框架底层源码，而是把 Agno 用在可维护、可部署、可观测、体验良好的真实应用里。

| # | 目录 | 主题 | 新增能力 | 目标 |
|---|---|---|---|---|
| 13 | `13-storage-and-long-term-memory` | 存储和长期记忆 | SQLite/Postgres storage、用户偏好、长期记忆检索 | 会话和记忆可长期维护 |
| 14 | `14-knowledge-and-vector-db` | Knowledge 和向量库 | 文档入库、检索、引用、更新和失效 | 可追溯 RAG 能力 |
| 15 | `15-auth-and-multi-tenant` | 鉴权和多租户 | 用户隔离、session 权限、artifact 权限 | 多用户安全使用 |
| 16 | `16-observability-and-tracing` | 观测性和 trace | 请求日志、工具耗时、token 成本、错误追踪 | 能定位线上问题 |
| 17 | `17-agent-evaluation` | Agent 评测 | golden tasks、回归测试、工具调用断言、报告质量检查 | 改动后不靠肉眼验收 |
| 18 | `18-guardrails-and-risk-control` | 安全护栏和风险控制 | 工具权限、预算、限流、敏感动作审批 | 降低误操作风险 |
| 19 | `19-production-deployment` | 生产部署 | Podman、环境变量、健康检查、后台任务、持久卷 | 可部署和可恢复 |
| 20 | `20-performance-and-cost` | 性能和成本优化 | 缓存、并发、streaming 优化、模型路由、token 压缩 | 控制延迟和成本 |
| 21 | `21-custom-agui-components` | 自定义 AG-UI 组件 | 工具卡片、图表、确认面板、artifact 预览 | 前端体验产品化 |
| 22 | `22-application-operations-playbook` | 应用运营手册 | 故障处理、版本升级、数据备份、用户反馈闭环 | 能长期运行和迭代 |

## 每个 demo 的交付标准

每个目录尽量保持小而完整：

- 一个 `README.md` 说明学习目标、运行方式和本 demo 新增了什么。
- 一个最小后端入口，例如 `app.py` 或 `server.py`。
- 必要时提供 `requirements.txt`。
- 涉及前端时提供独立可运行的 `web/` 或复用 `tools/agent-ui`。
- 示例默认使用金融场景，但避免真实交易动作。
- 所有工具输出都应可追踪，不把 LLM 文本当作数值事实。

## 后端规划

后端建议分三层推进。

第一层是脚本化 Agent：

- 从 `Agent` 开始，跑通指令、模型、工具调用。
- 工具先用本地 fake data 或公开只读数据，避免一开始接复杂数据源。
- 输出尽量结构化，方便后续前端消费。

第二层是 AgentOS 服务：

- 使用 `AgentOS` 注册 agents、teams、workflows。
- 暴露 FastAPI app，保留 `/docs` 方便调试。
- 加入 session、storage、trace，能复盘一次任务怎么完成。

第三层是前端友好 API：

- 普通 REST 用于健康检查、任务列表、artifact 下载。
- 流式接口用于聊天、工具进度和状态更新。
- AG-UI 用于标准化 Agent 和前端之间的事件协议。
- 对高风险动作提供 confirmation，而不是让 Agent 直接执行。
- 会话 API 用于创建、加载、重命名、删除和搜索历史会话。
- 后端按 `session_id` 读取历史消息、任务状态、工具调用和 artifact，让用户能基于上下文继续追问。
- 长会话需要 summary / memory compaction，避免每次续问都把完整历史原样塞回模型。

## 前端规划

前端不要只做一个聊天框。金融研究类 Agent 至少需要这些交互：

- 左侧会话列表：保留历史研究任务。
- 会话管理：创建、重命名、删除、搜索和恢复历史会话。
- 上下文续问：打开历史会话后继续提问，保留上一轮研究目标、关键结论、工具结果和报告产物。
- 中间消息区：支持流式消息、Markdown、表格和引用。
- 右侧任务面板：展示目标、步骤、工具调用、当前状态。
- 工具卡片：展示工具名、参数摘要、耗时、成功或失败。
- 人工确认条：展示待确认动作、风险说明、确认和拒绝按钮。
- Artifact 区：报告、CSV、图表、日志可预览和下载。
- 错误状态：展示可恢复建议，而不是只显示 traceback。

## 会话和上下文模型

交互友好的前后端需要把聊天消息和研究状态分开保存：

```text
Session
  id
  title
  created_at
  updated_at
  summary
  user_preferences

Message
  session_id
  role
  content
  created_at

ToolCall
  session_id
  tool_name
  args
  result_summary
  status
  latency_ms

Artifact
  session_id
  type
  path
  title
  metadata
```

续问时后端不只读取消息列表，还要组合：

- 最近若干轮 messages。
- session summary。
- 当前研究任务状态。
- 关键 tool results。
- 已生成 artifacts 的摘要和引用。

这样用户打开一段历史会话后，可以继续问：

```text
刚才那个组合里，为什么你说银行股风险更高？
把前面的结论改成面向投资委员会的摘要。
基于刚才的结果，再加一个压力测试。
```

## 建议技术栈

后端：

```text
Python + Agno + AgentOS + FastAPI + SQLite/Postgres
```

前端：

```text
Next.js + TypeScript + Tailwind + streaming fetch / AG-UI client
```

本仓库已经包含 `tools/agent-ui`，前几个 AgentOS demo 可以先复用它；从 `10-agui-fastapi` 开始再建设自定义前端。

## 里程碑

第一阶段：入门可运行

- `01-hello-agent`
- `02-agent-with-finance-tools`
- `03-structured-output`
- 目标：理解 Agno Agent 和工具调用边界。

第二阶段：服务化可调试

- `04-agentos-basic`
- `05-session-memory`
- `06-streaming-events`
- 目标：把 Agent 变成本地服务，并能通过 UI 调试。

第三阶段：交互可控

- `07-human-confirmation`
- `08-team-research`
- `09-workflow-report`
- 目标：支持多步骤、多角色、人工确认和报告产物。

第四阶段：产品化前后端

- `10-agui-fastapi`
- `11-nextjs-chat-ui`
- `12-finance-research-console`
- 目标：形成一个交互友好的金融研究 Agent 控制台。

第五阶段：Agno 应用专家工程化

- `13-storage-and-long-term-memory`
- `14-knowledge-and-vector-db`
- `15-auth-and-multi-tenant`
- `16-observability-and-tracing`
- `17-agent-evaluation`
- `18-guardrails-and-risk-control`
- `19-production-deployment`
- `20-performance-and-cost`
- `21-custom-agui-components`
- `22-application-operations-playbook`
- 目标：形成可维护、可观测、可测试、可部署、可扩展的 Agno 应用能力。

## Agno 应用专家验收标准

完成补充路径后，应该能独立回答和实现这些应用层问题：

- 如何选择 `Agent`、`Team`、`Workflow`，而不是所有问题都用多 Agent。
- 如何设计工具 schema、权限、超时、重试、预算和审计日志。
- 如何保存历史会话，并让用户在几天后基于上下文继续追问。
- 如何让 RAG 结果带引用、可更新、可失效，而不是一次性塞文档。
- 如何把 AgentOS 服务部署到生产环境，并保留健康检查和故障恢复路径。
- 如何观察一次 Agent 调用的 token、延迟、工具耗时、错误和中间状态。
- 如何写 Agent 回归测试，防止提示词或工具变更导致能力退化。
- 如何处理多用户、多租户、artifact 权限和敏感数据隔离。
- 如何控制成本、上下文长度、并发请求和模型路由。
- 如何基于 AG-UI 或自定义协议做高质量前端，而不是只有聊天流。
- 如何制定应用运维手册，包括升级、备份、回滚、故障排查和用户反馈闭环。

## 应用专家能力说明

这些能力是把 Agno 应用从“能跑 demo”推进到“能长期给用户用”的工程要求。

权限：

```text
控制谁能做什么。
```

例如普通用户只能查看自己的会话、报告和 artifact；管理员可以查看系统状态；高风险工具调用需要人工确认；某些工具只允许特定角色使用。

多租户：

```text
多个用户、团队或客户共用同一套系统，但数据相互隔离。
```

例如 A 公司不能看到 B 公司的会话、文件、向量库、报告、工具调用记录和长期记忆。

观测：

```text
知道系统运行时发生了什么。
```

例如一次 Agent 请求用了多少 token、耗时多久、调用了哪些工具、哪个工具失败、哪个模型返回慢、哪个用户请求异常。

评测：

```text
验证 Agent 改动后能力有没有退化。
```

例如准备一批固定问题和期望行为，检查 Agent 是否调用正确工具、是否引用证据、是否生成合格报告、是否拒绝高风险请求。

部署：

```text
把本地应用稳定放到服务器或云上运行。
```

本路线默认使用 Podman，而不是 Docker。部署内容包括容器镜像、环境变量、数据库、健康检查、日志、HTTPS、后台任务、服务重启和版本发布。

成本控制：

```text
控制模型和基础设施开销。
```

例如限制最大上下文、压缩历史会话、缓存重复结果、按任务选择便宜或更强的模型、限制并发和单次任务 token 预算。

运维闭环：

```text
应用上线后的维护流程。
```

例如故障排查、数据备份、版本回滚、用户反馈收集、问题复现、修复发布、监控告警和定期清理无用数据。

可以把这些能力归纳为：

```text
权限 / 多租户 = 安全边界
观测 / 评测 = 知道系统好不好
部署 / 运维 = 能长期稳定运行
成本控制 = 用得起、控得住
```

## 和现有项目的衔接

完成这条路径后，可以把 `awesome-llm-apps/` 里的示例逐步迁移成更统一的形态：

- 简单 Streamlit demo 保留为轻量体验。
- 复杂 Agent demo 迁移到 AgentOS。
- 多 Agent 和报告类应用统一接入 AgentUI 或自定义 Next.js 前端。
- 工具、schema、artifact、日志格式在各项目之间复用。

## 参考

- Agno Agents: https://docs.agno.com/agents/overview
- Agno AgentOS: https://docs.agno.com/agent-os/overview
- Agno AG-UI: https://docs.agno.com/agent-os/interfaces/ag-ui/introduction
- Agno Demo OS: https://docs.agno.com/demo-os/overview
