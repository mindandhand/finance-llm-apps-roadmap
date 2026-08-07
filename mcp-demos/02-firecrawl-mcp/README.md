# 02：用 Agno 和 Firecrawl MCP 研究网页

本节使用 Firecrawl Keyless 免费模式抓取网页。Agno Agent 负责选择工具，Firecrawl MCP Server 负责访问网页，DeepSeek 汇总返回内容并生成中文结果。无需注册 Firecrawl 账号，也不需要 `FIRECRAWL_API_KEY`。

## 学习目标

- 通过 Keyless 模式连接 Firecrawl MCP；
- 根据任务选择免费开放的单页抓取或网页搜索工具；
- 控制搜索结果和页面内容，避免不必要的 Token 消耗；
- 理解 Keyless 免费额度与 DeepSeek 模型密钥的职责边界；
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

`DEEPSEEK_API_KEY` 只供模型服务使用。Firecrawl MCP 直接使用 Keyless 免费额度，不接收任何 Firecrawl 账号凭证。官方当前提供每月 1,000 个免费 Credits，额度和计费规则以 Firecrawl 官方页面为准。

Keyless MCP 当前只开放：

- `firecrawl_scrape`：抓取单个网页；
- `firecrawl_search`：搜索网页。

Crawl、Map、Extract、批量抓取和深度研究等工具需要 API Key，本示例不会把它们暴露给 Agent。

## 运行

```bash
pip install -r requirements.txt
```

创建 `.env`：

```env
DEEPSEEK_API_KEY=your-deepseek-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-pro
```

确认 Node.js 可用并启动：

```bash
node --version
npx --version
python agent.py
```

程序只校验模型 Key。Firecrawl 部分不登录账号，也不读取 API Key。

## 可以尝试

- “抓取 `https://example.com` 并用中文概括。”
- “搜索最近的 MCP 官方更新，列出来源和发布日期。”
- “抓取给定商品页，整理页面中明确出现的名称、价格和规格。”

Keyless 模式按 IP 限速。查询时应限制搜索结果数量，不要连续重复抓取同一页面。

## 阅读代码时重点关注

1. 启动时如何只校验模型 API Key。
2. `MCPTools` 如何在无 Firecrawl 凭证的情况下连接 `firecrawl-mcp`。
3. `include_tools` 如何只暴露两个 Keyless 免费工具。
4. instructions 如何限制工具范围并要求保留来源。
5. `agent.acli_app()` 如何提供流式命令行对话。

## 金融场景改造

可以用于抓取公司公告、交易所规则和公开研究资料。建议固定允许域名与页面上限，并为每条结论保存 URL、发布日期和抓取时间。网页内容可能过期或有误，不能仅凭模型摘要执行交易。

## 常见问题

- 缺少环境变量：检查 DeepSeek 模型 Key。
- Firecrawl 返回额度错误：Keyless 免费额度可能已用完，等待下个额度周期或检查官方政策。
- 抓取失败：检查目标站点限制、robots 规则和 Firecrawl 支持情况。
- 返回内容太长：缩小问题范围，并要求模型只保留必要字段。
- `npx` 启动失败：检查 Node.js、网络和 npm 包下载权限。

## 官方参考

- [Firecrawl Keyless 说明](https://www.firecrawl.dev/blog/firecrawl-keyless-launch)
- [Firecrawl 免费额度与计费](https://www.firecrawl.dev/pricing)
