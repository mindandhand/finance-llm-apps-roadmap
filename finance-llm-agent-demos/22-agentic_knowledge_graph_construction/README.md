# Agent 驱动的金融知识图谱构建

这是第 13 个示例的进阶项目。它把供应链知识图谱构建场景改造成中国上市公司关系与风险追踪，同时保留原案例的完整技术链路，而不是只做一次实体抽取。

> 学习顺序：`13-knowledge_graph_rag_citations` → `22-agentic_knowledge_graph_construction`

## 学习目标

完成示例后，你应能解释并实现：

1. 如何通过意图 Agent 澄清研究目标，并在人工确认后进入数据选择。
2. 为什么 Schema 提议 Agent 与批判 Agent 应当分工。
3. 如何用 LangGraph `interrupt()` 和 `Command(resume=...)` 保留多轮澄清、反馈重试和独立审批门禁。
4. 如何分别批准结构化施工计划、实体类型和事实类型，再执行双通道构图与实体链接。
5. 如何在 Neo4j 中为每条事实保留来源、位置、原文片段与置信度。
6. 如何执行多跳 GraphRAG，并让答案中的 `[n]` 引用回到原始证据。

## 功能等价改写的技术链路

| 原案例能力 | 本示例实现 |
| --- | --- |
| 用户意图分析 | 多轮澄清、perceived goal、拒绝反馈、重新理解和独立批准 |
| 文件推荐 Agent | Agent 先决定按需采样文件，用户拒绝后结合反馈重新推荐 |
| 结构化 Schema 提议 | 节点、唯一键、节点属性、关系方向、外键和关系属性施工规则 |
| 非结构化抽取方案 | NER Agent 与 Fact Agent 分离，实体类型和事实类型分别批准 |
| Proposal + Critic | Critic 意见进入修订版，重新审核，最多三轮不收敛则阻止审批 |
| Human-in-the-loop | 目标、文件、施工计划、实体类型、事实类型五个独立动态门禁 |
| CSV 图谱构建 | 先创建唯一约束和领域节点，再按外键创建带属性关系 |
| Markdown 事实抽取 | 保留标题、按分隔符分块、生成 embedding，并按批准 Schema 抽取 |
| 实体链接 | 比较抽取实体键和领域键，建立 `CORRESPONDS_TO` 图融合关系 |
| Neo4j 图谱 | `Entity → Fact → Entity`，`Evidence → Fact` |
| GraphRAG | 路由 Agent 选择直接或多跳检索，再生成证据上下文和带引用回答 |

Google ADK 被替换为 LangGraph，默认模型改为 DeepSeek；这是技术栈替换，不是删除多 Agent、工作流状态或人工审批能力。

## 架构

```text
研究描述 ↔ 意图 Agent 澄清/修订 → 批准研究目标
  → 文件 Agent 按需采样 ↔ 用户反馈 → 批准文件
  → 结构化 Proposal ↔ Critic ↔ 用户反馈 → 批准施工计划
  → NER Agent ↔ 用户反馈 → 批准实体类型
  → Fact Agent ↔ 用户反馈 → 批准事实类型
  → CSV 领域节点/关系 ───────────┐
  → Markdown Chunk/Embedding/事实 ├→ CORRESPONDS_TO → 融合图谱
                                  └→ Evidence 溯源
  → 图路径检索 → DeepSeek 基于证据回答 → [n] 引用账本
```

`Fact` 使用节点而不是动态 Cypher 关系类型，是为了让同一个事实安全挂接多份证据，同时避免把模型输出直接拼进 Cypher。

## 文件结构

```text
22-agentic_knowledge_graph_construction/
├── app.py               # Streamlit 研究工作台
├── agents.py            # DeepSeek 文件推荐、Schema、批判、抽取和回答 Agent
├── core.py              # 数据契约、审批门禁、CSV 解析和内存图检索
├── helper.py            # 消息历史和 Agent 共享会话状态
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
3. 结构化 Proposal Agent 生成节点/关系施工规则，Critic 提出意见并触发修订，再人工批准。
4. NER Agent 提议实体类型；可拒绝并反馈，满意后单独批准。
5. Fact Agent 只使用已批准实体定义主语、谓语和宾语；再次独立批准。
6. 系统构建领域图、文档 Chunk 和抽取图，再通过 `CORRESPONDS_TO` 融合。
7. 在 GraphRAG 页提问，检查检索策略、图路径、Chunk 和证据账本是否一致。

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
