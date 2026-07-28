# MCP 示例学习路线

这个目录收集了从
`/Users/neil/python-project/awesome-llm-apps` 搬过来的 10 个 MCP 示例，并按
“从简单到复杂”的顺序重新编号。学习目标是先理解 MCP 的基本模式，再逐步改造成使用
DeepSeek、通义千问、智谱、Kimi、Ollama/vLLM 等中国或本地 OpenAI-compatible 模型的示例。

## 模型配置

默认按 DeepSeek 配置：

```bash
cp .env.example .env
# 编辑 .env
export DEEPSEEK_API_KEY=your-key
export OPENAI_BASE_URL=https://api.deepseek.com/v1
export OPENAI_MODEL=deepseek-chat
```

多数 Python 示例仍使用 Agno 的 `OpenAIChat` 适配器，但通过
[llm_config.py](/Users/neil/python-project/finance-llm-apps-roadmap/mcp-demos/llm_config.py)
统一读取 OpenAI-compatible 配置：

- `DEEPSEEK_API_KEY` or `OPENAI_API_KEY` or `LLM_API_KEY`
- `OPENAI_BASE_URL` or `LLM_BASE_URL`
- `OPENAI_MODEL` or `LLM_MODEL`

可替换为：

```bash
# 通义千问 DashScope
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus

# 智谱
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
OPENAI_MODEL=glm-4-plus

# Kimi
OPENAI_BASE_URL=https://api.moonshot.cn/v1
OPENAI_MODEL=moonshot-v1-8k

# 本地 Ollama/vLLM/LM Studio
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=qwen2.5:7b
```

## 学习路径

| Stage | Directory | Focus | Complexity |
| --- | --- | --- | --- |
| 1 | `01-adk-filesystem-mcp` | ADK Agent 通过 stdio 连接 filesystem MCP | 简单 |
| 2 | `02-adk-firecrawl-mcp` | 带 API key 的爬取/搜索 MCP | 简单 |
| 3 | `03-notion-mcp-agent` | 终端 Agent、Notion MCP、记忆 | 中等 |
| 4 | `04-github-mcp-agent` | Streamlit UI、Docker 运行 GitHub MCP Server | 中等 |
| 5 | `05-browser-mcp-agent` | Playwright 浏览器自动化 MCP | 中等 |
| 6 | `06-multi-mcp-agent` | 一个 Agent 同时连接多个 MCP Server | 中等偏上 |
| 7 | `07-multi-mcp-agent-router` | Router 把任务分发给不同专业 Agent | 进阶 |
| 8 | `08-travel-planner-mcp-agent-team` | 多 MCP 业务流、搜索、日历导出 | 进阶 |
| 9 | `09-mcp-apps-generative-ui-showcase` | MCP Apps、资源、聊天内交互 UI | 高阶 |
| 10 | `10-ai-mcp-app-builder` | 运行时生成 MCP App、沙箱、动态 UI | 专家级 |

## 每个示例怎么学

1. 先读当前目录的 `学习说明.md`。
2. 只看入口文件，例如 `agent.py`、`app.py`、`server.ts` 或 API route。
3. 找出 MCP transport：stdio、Docker stdio、Streamable HTTP、或 MCP Apps UI。
4. 列出 MCP server 暴露了哪些 tools/resources/prompts。
5. 用一个很小的 prompt 跑通。
6. 再切换到 DeepSeek 或 Qwen。
7. 最后把业务场景改成金融。

## 金融场景改造方向

- Filesystem MCP：读取本地 CSV 因子数据，写出分析笔记。
- Firecrawl MCP：抓取公司公告、券商研报、产品页、新闻页面。
- Notion MCP：维护投资研究 notebook。
- GitHub MCP：分析量化策略仓库、issue、PR 活跃度。
- Browser MCP：从公开网页采集金融数据。
- Multi-MCP Agent：组合 GitHub、搜索、日历、笔记，形成投研工作流。
- Router：把问题路由给因子研究、风控审查、报告写作、数据质量 Agent。
- Travel Planner：改成“投资研究计划生成器”。
- MCP Apps Showcase：重点学习里面的 Investment Simulator / Portfolio UI。
- MCP App Builder：生成自定义金融 dashboard。

## 当前改造状态

Python Agno 示例已经做了最小模型兼容改造：优先读取 DeepSeek/OpenAI-compatible
配置。TypeScript/Next.js 大项目仍基本保持原样，下一步重点是把它们的
`OPENAI_API_KEY`、`OPENAI_MODEL`、`baseURL` 配置改成统一的中国模型入口。
