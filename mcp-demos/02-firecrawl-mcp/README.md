# 02：用 Agno 和 Firecrawl MCP 研究网页

本节在 stdio MCP 的基础上增加外部服务密钥和长文本结果。Agno Agent 负责选择工具，Firecrawl MCP Server 负责访问网页，DeepSeek 汇总返回内容并生成中文结果。

## 学习目标

- 通过 `env` 把 `FIRECRAWL_API_KEY` 注入 MCP Server 子进程；
- 根据任务选择单页抓取、搜索、站点发现、批量抓取或深度研究工具；
- 控制抓取范围，避免无限爬取、超时和不必要的 Token 消耗；
- 区分 Firecrawl API Key 与模型 API Key；
- 在结果中保留来源并区分原文与模型判断。

## 默认模型

默认使用 `deepseek-v4-pro`。网页研究可能返回较长的 Markdown，多页任务还需要模型连续处理多个工具结果，因此优先使用 Pro 模型。只有实际评测显示质量、延迟或成本不符合要求时，才考虑其他模型。

代码已经通过共享的 `llm_config.py` 接入 DeepSeek：

```python
model=create_agno_openai_model(
    OpenAIChat,
    default_model="deepseek-v4-pro",
)
```

## 架构

```text
用户研究问题
  ↓
Agno Agent + DeepSeek V4 Pro
  ↓
MCPTools
  ↓ stdio
Firecrawl MCP Server
  ↓
Firecrawl API → 网页内容
```

`DEEPSEEK_API_KEY` 供模型服务使用，`FIRECRAWL_API_KEY` 只传给 Firecrawl MCP 子进程。两类密钥职责不同。

## 运行

```bash
pip install -r requirements.txt
```

创建 `.env`：

```env
DEEPSEEK_API_KEY=your-deepseek-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-pro
FIRECRAWL_API_KEY=your-firecrawl-key
```

确认 Node.js 可用并启动：

```bash
node --version
npx --version
python agent.py
```

程序会校验模型 Key 和 Firecrawl Key，缺少任意一项都会在启动 MCP Server 前退出。

## 可以尝试

- “抓取 `https://example.com` 并用中文概括。”
- “找出某个文档站点的主要页面，但最多返回 20 个 URL。”
- “搜索最近的 MCP 官方更新，列出来源和发布日期。”
- “从给定商品页提取名称、价格和规格，无法确认的字段留空。”

进行 Crawl 或批量抓取前，应明确域名、最大页面数、深度和输出字段。不要默认抓取整个网站。

## 阅读代码时重点关注

1. 启动时如何分别校验两类 API Key。
2. `env={**os.environ, ...}` 如何把 Firecrawl Key 传入子进程。
3. `MCPTools` 如何连接 `firecrawl-mcp`。
4. instructions 如何限制抓取范围并要求保留来源。
5. `agent.acli_app()` 如何提供流式命令行对话。

## 金融场景改造

可以用于抓取公司公告、交易所规则和公开研究资料。建议固定允许域名与页面上限，并为每条结论保存 URL、发布日期和抓取时间。网页内容可能过期或有误，不能仅凭模型摘要执行交易。

## 常见问题

- 缺少环境变量：检查 `.env` 的两个 Key。
- Firecrawl 返回鉴权错误：确认 Key 有效且账户额度充足。
- 抓取失败：检查目标站点限制、robots 规则和 Firecrawl 支持情况。
- 返回内容太长：缩小页面范围，优先使用结构化抽取。
- `npx` 启动失败：检查 Node.js、网络和 npm 包下载权限。
