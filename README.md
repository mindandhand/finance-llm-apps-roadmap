# finance-llm-apps-roadmap

这个工作区用于本地学习和调试金融类 LLM 应用与 Agent 示例。项目包含 LangGraph、Agno 等多种 Agent 框架，也包含 Streamlit、RAG、MCP 和直接调用 DeepSeek 的应用。示例集中放在 `awesome-llm-apps` 目录，Agno 渐进式学习规划放在 `agno-demos`，Agno 开源 AgentUI 放在 `tools/agent-ui`，运行脚本放在 `scripts/` 和 `awesome-llm-apps/scripts/`。

## 本地运行方式

先在工作区根目录配置 `.env`：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_ID=deepseek-chat
```

各示例也支持在自己的项目目录下放 `.env`。加载优先级通常是：项目目录 `.env`、`awesome-llm-apps/.env`、工作区根目录 `.env`。

## AgentOS 示例

下面这些项目会启动本地 AgentOS 服务，默认地址是：

```text
http://localhost:7777
```

启动 01 AI 金融 Agent：

```bash
cd awesome-llm-apps
./scripts/run_01_agent.sh
```

启动 02 AI 投资分析 Agent：

```bash
cd awesome-llm-apps
./scripts/run_02_agent.sh
```

启动 04 AI 金融 Agent 团队：

```bash
cd awesome-llm-apps
./scripts/run_04_agent.sh
```

启动 07 AI VC 尽职调查 Agent 团队：

```bash
cd awesome-llm-apps
./scripts/run_07_agent.sh
```

## 本地 AgentUI

01、02、04、07 使用 Agno AgentOS，可以通过本地 AgentUI 聊天测试。

在第二个终端从工作区根目录启动 AgentUI：

```bash
./scripts/run_agent_ui.sh
```

浏览器打开：

```text
http://localhost:3000
```

在 AgentUI 中连接本地 AgentOS 地址：

```text
http://localhost:7777
```

## Agno Demos 规划

`agno-demos/` 规划了一条从最小 Agno Agent 到交互友好前后端的学习路径：

```text
Agent -> Tools -> Memory -> Team -> Workflow -> AgentOS -> AG-UI / 自定义前端
```

详见 [`agno-demos/README.md`](agno-demos/README.md)。

## Streamlit 示例

下面这些项目是 Streamlit 应用，不需要连接 AgentUI。启动后直接访问本地页面：

```text
http://localhost:8501
```

启动 03 AI 个人财务规划师：

```bash
cd awesome-llm-apps
./scripts/run_03_agent.sh
```

启动 05 人寿保险保额顾问：

```bash
cd awesome-llm-apps
./scripts/run_05_agent.sh
```

启动 06 AI 财务教练：

```bash
cd awesome-llm-apps
./scripts/run_06_agent.sh
```

启动 08 AI 创业趋势分析 Agent：

```bash
cd awesome-llm-apps
./scripts/run_08_agent.sh
```

启动 12 AI 金融数据分析 Agent：

```bash
cd awesome-llm-apps
./scripts/run_12_agent.sh
```

启动 15 金融 MCP Agent Router：

```bash
cd awesome-llm-apps
./scripts/run_15_agent.sh
```

启动 16 本地混合金融 RAG：

```bash
cd awesome-llm-apps
./scripts/run_16_agent.sh
```

启动 18 金融研究工作台：

```bash
cd awesome-llm-apps
./scripts/run_18_agent.sh
```

启动 19 市场事件 Radar Agent：

```bash
cd awesome-llm-apps
./scripts/run_19_agent.sh
```

启动 20 保险理赔文本 Agent 团队：

```bash
cd awesome-llm-apps
./scripts/run_20_agent.sh
```

启动 21 金融仪表盘生成器：

```bash
cd awesome-llm-apps
./scripts/run_21_agent.sh
```

## 项目列表

- `01-ai_finance_agent`：DeepSeek + Agno AgentOS + Yahoo Finance + DuckDuckGo。
- `02-ai_investment_agent`：DeepSeek + Agno AgentOS + Yahoo Finance，适合做股票对比。
- `03-ai_personal_finance_agent`：DeepSeek + DuckDuckGo + Streamlit，生成个人财务规划建议。
- `04-ai_finance_agent_team`：DeepSeek + Agno Team + AgentOS，多 Agent 协作完成金融研究。
- `05-ai_life_insurance_advisor_agent`：DeepSeek + DuckDuckGo + Streamlit，估算寿险保额。
- `06-ai_financial_coach_agent`：DeepSeek + Agno + Streamlit，生成预算、储蓄和债务优化建议。
- `07-ai_vc_due_diligence_agent_team`：DeepSeek + Agno Team + DuckDuckGo，生成创业公司 VC 尽调分析和本地报告文件。
- `08-ai_startup_trend_analysis_agent`：DeepSeek + DuckDuckGo + Streamlit，生成创业趋势分析和机会建议。
- `09-deepseek_local_rag_agent`：本地 DeepSeek RAG 示例。
- `10-rag_failure_diagnostics_clinic`：RAG 故障诊断与 JSON 报告。
- `11-agentic_typed_rag_pydanticai`：类型化 RAG 和引用契约示例。
- `12-ai_financial_data_analysis_agent`：DeepSeek + DuckDB + Streamlit，自然语言分析 CSV/Excel。
- `13-knowledge_graph_rag_citations`：知识图谱 RAG 和可验证引用。
- `14-browser_mcp_agent`：浏览器 MCP Agent，用于只读网页操作和信息提取。
- `15-finance_mcp_agent_router`：金融工具路由器，按任务选择行情、新闻、风险或报告 Agent。
- `16-local_hybrid_financial_rag`：本地关键词/BM25 混合检索金融 RAG。
- `17-github_mcp_agent`：GitHub MCP 只读仓库分析 Agent。
- `18-financial_research_workspace`：金融研究工作台，生成投研备忘录。
- `19-market_event_radar_agent`：市场公告、新闻和监管事件 Radar。
- `20-insurance_claim_text_agent_team`：纯文本保险理赔 intake 和交接包。
- `21-finance_dashboard_generator`：模板化本地金融仪表盘生成器。

## 常见问题

如果 AgentUI 打不开，先确认 `./scripts/run_agent_ui.sh` 正常运行，并访问 `http://localhost:3000`。

如果 AgentOS 示例无法连接，先确认对应 `run_0x_agent.sh` 正常运行，并访问 `http://localhost:7777`。

如果 Streamlit 示例无法打开，先确认对应脚本正常运行，并访问 `http://localhost:8501`。

如果模型认证失败，检查 `.env` 中是否已经配置 `DEEPSEEK_API_KEY`。
