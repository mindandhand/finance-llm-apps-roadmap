# 项目中文学习手册

本手册覆盖金融优先学习路线中的 22 个项目。仓库暂未为这些项目提供完整的项目级中文简介，以下内容根据各项目的 README、源码结构和依赖文件整理生成。难度按本仓库内的相对复杂度评定。

> 金融、投资和保险项目仅用于技术学习与原型验证，不构成投资、保险或法律建议。涉及外部 API、网页操作和消息投递时，应使用测试账户、最小权限和人工确认。

## 一、金融 Agent 主线

### 1. AI 金融分析 Agent

- **路径**：[`01-ai_finance_agent/`](01-ai_finance_agent/)
- **中文简介**：使用 DeepSeek、Yahoo Finance 和 DuckDuckGo 查询股票行情、公司信息与相关新闻，并通过 AgentOS Playground 展示结构化金融分析结果。
- **核心技术**：Agno、AgentOS、YFinance、DuckDuckGo、工具调用。
- **学习重点**：最小 Agent 结构、模型与工具绑定、实时数据和自然语言结论的边界。
- **难度/前置条件**：入门；Python 基础、DeepSeek API Key。
- **建议产出**：增加数据时间戳、来源和风险声明的单股票分析页。

### 2. AI 投资分析 Agent

- **路径**：[`02-ai_investment_agent/`](02-ai_investment_agent/)
- **中文简介**：基于 DeepSeek 和 Yahoo Finance 获取公司资料、行情、新闻和分析师建议，生成两只或多只股票的比较报告。
- **核心技术**：Agno、AgentOS、DeepSeek、YFinance。
- **学习重点**：金融工具封装、比较型 Prompt、表格输出和报告结构。
- **难度/前置条件**：入门；Python、DeepSeek API Key。
- **建议产出**：三家公司基本面比较工具，并为缺失字段提供明确标记。

### 3. AI 个人财务规划师

- **路径**：[`03-ai_personal_finance_agent/`](03-ai_personal_finance_agent/)
- **中文简介**：收集用户的收入、支出、目标与财务状况，由 DeepSeek 驱动的研究和规划 Agent 生成个性化预算、储蓄及投资建议。
- **核心技术**：Agno、Streamlit、DeepSeek、DuckDuckGo、双 Agent 流程。
- **学习重点**：表单输入、会话状态、Researcher 到 Planner 的上下文传递。
- **难度/前置条件**：初中级；Python、Streamlit、DeepSeek API Key。
- **建议产出**：可解释的月度预算方案，计算逻辑使用普通 Python 实现。

### 4. AI 金融 Agent 团队

- **路径**：[`04-ai_finance_agent_team/`](04-ai_finance_agent_team/)
- **中文简介**：由 DeepSeek 驱动的网页研究 Agent、金融数据 Agent 和协调 Team 共同完成公司研究与金融分析，并用 SQLite 保存交互记录。
- **核心技术**：Agno Team、DeepSeek、YFinance、DuckDuckGo、SQLite、AgentOS。
- **学习重点**：多 Agent 分工、任务委派、工具隔离和结果汇总。
- **难度/前置条件**：中级；理解单 Agent 和工具调用。
- **建议产出**：加入独立风险审查 Agent，检查来源、时效和结论冲突。

### 5. 人寿保险保额顾问

- **路径**：[`starter_ai_agents/ai_life_insurance_advisor_agent/`](starter_ai_agents/ai_life_insurance_advisor_agent/)
- **中文简介**：根据收入、负债、家庭责任和已有保障估算定期寿险需求，并用 DuckDuckGo 检索用户所在地区的相关产品或渠道线索。
- **核心技术**：Agno、Streamlit、DeepSeek、DuckDuckGo、本地确定性财务计算。
- **学习重点**：确定性财务计算、实时网页研究、模型结构化 JSON 输出和安全声明。
- **难度/前置条件**：中级；需要 Python、Streamlit、DeepSeek API Key。
- **建议产出**：为保额计算、百分比解析和异常输入补充单元测试。

### 6. AI 财务教练

- **路径**：[`06-ai_financial_coach_agent/`](06-ai_financial_coach_agent/)
- **中文简介**：分析手工输入或 CSV 交易数据，通过 DeepSeek 驱动的预算、储蓄和债务三个 Agent 依次生成个人财务改善方案及可视化图表。
- **核心技术**：Agno、DeepSeek、Pydantic、Pandas、Streamlit、Plotly。
- **学习重点**：结构化 JSON 输出、顺序 Agent 流程、CSV 校验、债务雪球与雪崩法。
- **难度/前置条件**：中高级；Python 数据处理、DeepSeek API Key。
- **建议产出**：带预算、应急金和债务时间线的结构化财务报告。

### 7. AI VC 尽职调查团队

- **路径**：[`07-ai_vc_due_diligence_agent_team/`](07-ai_vc_due_diligence_agent_team/)
- **中文简介**：对创业公司执行公司研究、市场分析、财务建模、风险评估和投资备忘录生成，并输出本地 HTML 报告、收入预测图与 SVG 摘要卡片。
- **核心技术**：Agno Team、AgentOS、DeepSeek、DuckDuckGo、Matplotlib、本地文件生成工具。
- **学习重点**：多 Agent 协作、网页研究、情景预测、风险矩阵和专业报告生成。
- **难度/前置条件**：高级；多 Agent 基础、DeepSeek API Key。
- **建议产出**：为一家创业公司生成可追溯的投资备忘录，并逐条核验事实来源和估计假设。

### 8. AI 创业趋势分析 Agent

- **路径**：[`08-ai_startup_trend_analysis_agent/`](08-ai_startup_trend_analysis_agent/)
- **中文简介**：围绕用户输入的赛道或技术方向检索创业新闻、融资事件、产品发布和市场线索，并生成中文趋势分析与创业机会建议。
- **核心技术**：Agno、DeepSeek、DuckDuckGo、Newspaper4k、Streamlit。
- **学习重点**：网页研究、文章摘要、趋势归纳、机会评估和验证实验设计。
- **难度/前置条件**：中级；Python、Streamlit、DeepSeek API Key。
- **建议产出**：围绕一个金融科技或 AI 应用方向生成趋势对比表、创业机会清单和风险假设。

## 二、RAG 学习主线

### 9. DeepSeek 本地 RAG 推理 Agent

- **路径**：[`rag_tutorials/deepseek_local_rag_agent/`](rag_tutorials/deepseek_local_rag_agent/)
- **中文简介**：通过 Ollama 本地运行 DeepSeek，使用 Snowflake Embedding 和 Qdrant 检索 PDF 或网页内容，并可在检索不足时补充网络搜索。
- **核心技术**：Ollama、Agno、Qdrant、LangChain Qdrant、Streamlit。
- **学习重点**：文档切分、向量化、相似度检索、上下文注入和来源展示。
- **难度/前置条件**：中级；Ollama、本地模型和 Qdrant 环境。
- **建议产出**：本地年报问答系统，记录命中文档块和相似度。

### 10. RAG 故障诊断诊所

- **路径**：[`rag_tutorials/rag_failure_diagnostics_clinic/`](rag_tutorials/rag_failure_diagnostics_clinic/)
- **中文简介**：输入真实 RAG 故障描述，由模型将问题归类到 12 种常见失效模式，并输出最小结构修复建议和 JSON 诊断报告。
- **核心技术**：OpenAI-compatible API、故障模式库、CLI、JSON 报告。
- **学习重点**：召回失败、切分错误、上下文污染、错误引用和系统化调试。
- **难度/前置条件**：初中级；Python 和任意兼容的聊天模型 API。
- **建议产出**：为自己的年报 RAG 建立故障案例库和回归测试集。

### 11. PydanticAI 类型化 Agentic RAG

- **路径**：[`rag_tutorials/agentic_typed_rag_pydanticai/`](rag_tutorials/agentic_typed_rag_pydanticai/)
- **中文简介**：从 PDF 或文档网站检索内容，将回答验证为带原文引句、块编号、置信度和是否可回答标志的类型化对象；证据不足时在调用模型前拒答。
- **核心技术**：PydanticAI、Streamlit、结构化输出、本地哈希或 OpenAI Embedding、pytest。
- **学习重点**：类型约束、引用契约、检索门槛、拒答机制和离线测试。
- **难度/前置条件**：中级；Pydantic、基础 RAG。
- **建议产出**：定义 `FinancialAnswer` 模型并评测引用正确率与拒答准确率。

### 12. AI 金融数据分析 Agent

- **路径**：[`12-ai_financial_data_analysis_agent/`](12-ai_financial_data_analysis_agent/)
- **中文简介**：上传 CSV 或 Excel 文件，用自然语言生成只读 DuckDB SQL，本地执行后由 DeepSeek 解释查询结果。
- **核心技术**：Streamlit、DeepSeek、DuckDB、Pandas、只读 SQL 防护。
- **学习重点**：结构化数据上传、字段推断、自然语言到 SQL、查询安全和结果解释。
- **难度/前置条件**：中级；Python、Pandas、SQL 基础、DeepSeek API Key。
- **建议产出**：上传交易流水、财务报表或经营数据，生成可复核的数据分析报告。

### 13. 带可验证引用的知识图谱 RAG

- **路径**：[`rag_tutorials/knowledge_graph_rag_citations/`](rag_tutorials/knowledge_graph_rag_citations/)
- **中文简介**：从文档抽取实体和关系写入 Neo4j，通过多跳图遍历回答跨文档问题，并为推理链中的每个结论保留来源。
- **核心技术**：Neo4j、Ollama、知识图谱、Streamlit、引用追踪。
- **学习重点**：实体关系建模、多跳查询、图检索与向量检索的差异、数据溯源。
- **难度/前置条件**：高级；Docker、Neo4j、RAG 基础。
- **建议产出**：构建“公司—子公司—供应商—风险事件”关系图谱。

## 三、MCP 学习主线

### 14. 浏览器 MCP Agent

- **路径**：[`mcp_ai_agents/browser_mcp_agent/`](mcp_ai_agents/browser_mcp_agent/)
- **中文简介**：通过 MCP-Agent 连接 Playwright MCP Server，让用户用自然语言完成网页导航、点击、表单操作、截图和信息提取。
- **核心技术**：MCP、MCP-Agent、Playwright、Streamlit、OpenAI-compatible 模型。
- **学习重点**：MCP Client/Server/Tool 分工、stdio 连接、多步工具调用和浏览器安全边界。
- **难度/前置条件**：中级；Python、Node.js、浏览器自动化基础。
- **建议产出**：只读访问公司投资者关系页面并提取财报链接的 Agent。

### 15. 金融 MCP Agent Router

- **路径**：[`15-finance_mcp_agent_router/`](15-finance_mcp_agent_router/)
- **中文简介**：根据用户任务自动路由到行情数据、公告新闻、风险审查或综合报告 Agent，演示金融工具的最小权限分工。
- **核心技术**：Agno、DeepSeek、DuckDuckGo、YFinance、Streamlit、工具路由。
- **学习重点**：任务分类、工具选择、Agent 职责边界和只读金融研究流程。
- **难度/前置条件**：中级；工具调用和多 Agent 基础。
- **建议产出**：扩展为“行情、财报、网页研究、风险审查”四类金融专职 Agent。

### 16. 本地混合金融 RAG

- **路径**：[`16-local_hybrid_financial_rag/`](16-local_hybrid_financial_rag/)
- **中文简介**：上传财报、公告或研报，用本地关键词/BM25 检索选取证据，再由 DeepSeek 基于证据回答问题。
- **核心技术**：Streamlit、DeepSeek、Pypdf、本地 BM25/关键词评分、证据引用。
- **学习重点**：本地检索、片段切分、Top K 证据选择、拒答和引用约束。
- **难度/前置条件**：中级；基础 RAG、Python 文本处理。
- **建议产出**：在同一份年报上比较本地检索命中片段和最终回答质量。

### 17. GitHub MCP Agent

- **路径**：[`mcp_ai_agents/github_mcp_agent/`](mcp_ai_agents/github_mcp_agent/)
- **中文简介**：连接官方 GitHub MCP Server，以自然语言查询仓库、Issue、Pull Request、活动和代码统计信息。
- **核心技术**：Agno、MCP、Docker、GitHub MCP Server、Streamlit。
- **学习重点**：官方 MCP Server 部署、令牌权限、工具发现和实时仓库分析。
- **难度/前置条件**：中级；Docker、GitHub PAT、LLM API Key。
- **建议产出**：只读仓库健康报告，并限制 Token 权限和可调用工具集合。

## 四、高级应用与工程化

### 18. 金融研究工作台

- **路径**：[`18-financial_research_workspace/`](18-financial_research_workspace/)
- **中文简介**：输入公司和研究重点，整合行情、新闻、公司信息和风险问题，生成结构化投研备忘录。
- **核心技术**：Agno、DeepSeek、DuckDuckGo、YFinance、Streamlit。
- **学习重点**：研究任务组织、信息来源标记、风险清单和备忘录结构。
- **难度/前置条件**：中级；单 Agent 和工具调用基础。
- **建议产出**：标准化公司研究模板，支持多公司横向对比。

### 19. 市场事件 Radar Agent

- **路径**：[`19-market_event_radar_agent/`](19-market_event_radar_agent/)
- **中文简介**：读取关注列表，检索公告、财报、监管、产品和重大新闻，按影响等级生成 dry-run 摘要。
- **核心技术**：Agno、DeepSeek、DuckDuckGo、Streamlit、事件分级。
- **学习重点**：事件监控、去重、影响分级、人工审核和 dry-run 保护。
- **难度/前置条件**：中级；网页检索和提示词设计。
- **建议产出**：每日市场事件摘要，不自动发送邮件或触发交易。

### 20. 保险理赔文本 Agent 团队

- **路径**：[`20-insurance_claim_text_agent_team/`](20-insurance_claim_text_agent_team/)
- **中文简介**：通过纯文本描述采集首次损失通知，抽取理赔字段、缺失材料和风险信号，生成理赔员交接包。
- **核心技术**：DeepSeek、Streamlit、结构化抽取、规则化缺失项检查。
- **学习重点**：保险 intake、字段抽取、证据材料、人工升级和审计话术。
- **难度/前置条件**：中级；保险业务基础、结构化输出。
- **建议产出**：不同险种的字段模板和缺失材料清单，不自动承诺赔付。

### 21. 金融仪表盘生成器

- **路径**：[`21-finance_dashboard_generator/`](21-finance_dashboard_generator/)
- **中文简介**：根据用户填写的指标和备注，用受限模板生成本地 HTML 金融仪表盘，不执行任意代码，也不依赖沙箱服务。
- **核心技术**：Streamlit、Pandas、HTML 模板、本地文件生成。
- **学习重点**：模板化生成、权限边界、可审阅产物和前端展示。
- **难度/前置条件**：初中级；HTML 和 Streamlit 基础。
- **建议产出**：投资组合、风险监控或经营指标仪表盘模板。

### 22. Agent 驱动的金融知识图谱构建

- **路径**：[`22-agentic_knowledge_graph_construction/`](22-agentic_knowledge_graph_construction/)
- **中文简介**：根据金融研究意图推荐结构化与非结构化文件，由 Schema Agent 和批判 Agent 设计图谱，经人工审批后融合 CSV 关系和公告事实写入 Neo4j，最后通过 GraphRAG 输出带证据引用的回答。
- **核心技术**：DeepSeek、LangGraph interrupt/Command、Neo4j、Streamlit、多 Agent、实体链接、证据溯源、GraphRAG。
- **学习重点**：文件推荐、Proposal + Critic、人工审批门禁、双通道构图、幂等写入、多跳检索与引用账本。
- **难度/前置条件**：高级；建议先完成 11、12、13，理解结构化输出、CSV 数据和知识图谱 RAG。
- **建议产出**：构建“公司—供应商—股东—风险事件”图谱，验证每条回答都能回到 CSV 行号或公告段落。

## 推荐学习顺序

1. 完成 2、3、4，掌握单 Agent、交互界面和多 Agent。
2. 完成 9、10、11、16，掌握基础 RAG、故障诊断、类型化回答和本地混合检索。
3. 完成 12，掌握结构化金融数据分析和只读 SQL 防护。
4. 完成 14、15、17，并自行实现只读金融数据 MCP Server。
5. 按 `13 → 22` 完成知识图谱进阶路线，掌握从单次抽取到 Agentic 构图工作流的升级。
6. 根据方向选修 18、19、20、21，分别强化投研工作台、事件监控、保险 intake 和仪表盘生成。

最终综合项目建议整合行情工具、财报 RAG、网页 MCP、风险 Agent、结构化引用、FastAPI 服务和人工审核，不包含自动交易功能。
