# Agent 驱动的金融知识图谱构建

这是第 13 个示例的进阶项目。它把供应链知识图谱构建场景改造成中国上市公司关系与风险追踪，同时保留原案例的完整技术链路，而不是只做一次实体抽取。

> 学习顺序：`13-knowledge_graph_rag_citations` → `22-agentic_knowledge_graph_construction`

## 学习目标

完成示例后，你应能解释并实现：

1. 如何通过意图 Agent 澄清研究目标，并在人工确认后进入数据选择。
2. 为什么 Schema 提议 Agent 与批判 Agent 应当分工。
3. 如何用 LangGraph `interrupt()` 和 `Command(resume=...)` 建立真正的人工审批门禁。
4. 如何分别处理 CSV 结构化关系和 Markdown 非结构化事实，再执行实体链接。
5. 如何在 Neo4j 中为每条事实保留来源、位置、原文片段与置信度。
6. 如何执行多跳 GraphRAG，并让答案中的 `[n]` 引用回到原始证据。

## 功能等价改写的技术链路

| 原案例能力 | 本示例实现 |
| --- | --- |
| 用户意图分析 | Agent 形成 perceived goal，研究员明确批准后保存 approved goal |
| 文件推荐 Agent | DeepSeek 读取文件名、CSV 表头、样例行和 Markdown 摘要，研究员确认范围 |
| 结构化 Schema 提议 | 为普通业务 CSV 生成可执行字段映射和有方向的关系规则 |
| 非结构化抽取方案 | 独立提出实体类型、事实类型和 Markdown 分块策略 |
| Proposal + Critic | Critic 意见必须进入修订版计划，而不是只显示意见 |
| Human-in-the-loop | 意图、文件、结构化计划、非结构化计划分别使用 LangGraph 动态中断 |
| CSV 图谱构建 | 严格执行批准后的字段映射规则，保留行号，不要求预制三元组 |
| Markdown 事实抽取 | DeepSeek 抽取实体关系、段落、原文与置信度 |
| 实体链接 | 将结构化实体标准名注入抽取 Prompt，要求非结构化事实优先复用 |
| Neo4j 图谱 | `Entity → Fact → Entity`，`Evidence → Fact` |
| GraphRAG | 路由 Agent 选择直接或多跳检索，再生成证据上下文和带引用回答 |

Google ADK 被替换为 LangGraph，默认模型改为 DeepSeek；这是技术栈替换，不是删除多 Agent、工作流状态或人工审批能力。

## 架构

```text
研究描述 → 意图 Agent → 人工确认研究目标
  → 文件内容采样 → 文件推荐 Agent → 人工确认文件
  → 结构化 Proposal ↔ Critic → 人工批准可执行映射
  → 非结构化实体/事实计划 → 人工批准抽取方案
  → CSV 确定性转换 ─┐
                     ├→ 实体链接 → Neo4j Entity / Fact / Evidence
  → Markdown 抽取 ───┘
  → 图路径检索 → DeepSeek 基于证据回答 → [n] 引用账本
```

`Fact` 使用节点而不是动态 Cypher 关系类型，是为了让同一个事实安全挂接多份证据，同时避免把模型输出直接拼进 Cypher。

## 文件结构

```text
22-agentic_knowledge_graph_construction/
├── app.py               # Streamlit 研究工作台
├── agents.py            # DeepSeek 文件推荐、Schema、批判、抽取和回答 Agent
├── core.py              # 数据契约、审批门禁、CSV 解析和内存图检索
├── user_intent.py       # 研究意图感知、澄清与批准状态
├── file_suggestion.py   # 文件内容采样、推荐 Prompt 和结果校验
├── structured_schema_proposal.py   # CSV 可执行映射与 Critic 修订
├── unstructured_schema_proposal.py # Markdown 实体与事实抽取计划
├── kg_construction.py   # 按批准计划执行双通道构图
├── graph_utilities.py   # 面向 Agent 的 Neo4j 与 GraphRAG 工具
├── tools.py             # 安全文件采样和通用工具结果协议
├── workflow.py          # LangGraph 中断/恢复工作流
├── neo4j_store.py       # 幂等构图、溯源存储和多跳检索
├── data/                 # 可重复运行的金融样例数据
├── tests/                # 离线单元与工作流测试
├── compose.yaml          # 独立 Neo4j 服务
└── requirements.txt
```

## 启动

从仓库根目录执行：

```bash
./finance-llm-agent-demos/scripts/run_22_services.sh
./finance-llm-agent-demos/scripts/run_22_agent.sh
```

首次运行先安装依赖：

```bash
cd finance-llm-agent-demos/22-agentic_knowledge_graph_construction
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

默认地址：

- Streamlit：`http://localhost:8501`
- Neo4j Browser：`http://localhost:7475`
- Neo4j Bolt：`bolt://localhost:7688`

在仓库根目录或本目录的 `.env` 中配置 `DEEPSEEK_API_KEY`。其余变量可参考 `.env.example`。

## 操作顺序

1. 输入初步研究描述，由意图 Agent 形成规范目标并人工批准。
2. 文件推荐 Agent 分析内容样本，研究员确认最终文件范围。
3. 结构化 Proposal Agent 生成字段映射，Critic 提出意见并触发修订，再人工批准。
4. 非结构化 Agent 独立生成实体和事实抽取计划，再人工批准。
5. 系统严格按两份批准计划构图；任一必要计划未批准都会阻止写库。
6. 在 GraphRAG 页提问，检查检索策略、推理路径与证据账本是否一致。

自定义 CSV 不需要预先整理成三元组。Schema Agent 会根据真实表头生成映射；构图前仍应检查字段选择和关系方向是否正确。

## 测试

```bash
cd finance-llm-agent-demos/22-agentic_knowledge_graph_construction
python3.11 -m unittest discover -s tests -v
```

测试不调用 DeepSeek，也不要求正在运行 Neo4j；外部交互通过假对象验证。

## 安全边界

- 未完成人工审批时禁止构图。
- 构图只能执行批准后的文件范围和 Schema，不读取临时或未批准计划。
- 模型关系类型作为参数保存，不直接拼接到 Cypher。
- GraphRAG 证据不足时必须明确拒答。
- 清空图谱必须输入完整确认短语。
- 示例只用于技术学习，不构成投资建议。

## 来源说明

功能边界参考 [`adityas2410/agentic-knowledge-graph-construction`](https://github.com/adityas2410/agentic-knowledge-graph-construction) 的课程架构。本示例仅把数据和业务语义改写为金融场景，并使用 DeepSeek、LangGraph 和 Streamlit 独立实现；没有直接复制许可证不明的上游源码。
