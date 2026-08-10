# 03：用 Notion MCP 构建中文知识库助手

本节把 MCP 从本地文件扩展到 SaaS：终端 Agent 通过 Notion 官方 MCP Server 读取、搜索和修改指定页面，并用 SQLite 保存 Agno 会话数据。

## 学习目标

完成本节后，你应该能够：

- 创建 Notion Integration，并把最小页面权限授予它。
- 理解模型密钥、Notion token 和 page ID 的不同职责。
- 通过 stdio 启动 `@notionhq/notion-mcp-server`。
- 观察多轮对话、MCP 工具调用和 SQLite 记忆如何协作。

## 架构

```text
终端输入
  -> Agno Agent
  -> deepseek-v4-flash
  -> Notion MCP Tools
  -> stdio 启动 Notion MCP Server
  -> Notion API

Agno Agent -> agno.db（会话数据）
```

入口文件是 `notion_mcp_agent.py`。Server 通过以下环境变量获得 Notion 凭据：

```python
env={
    "OPENAPI_MCP_HEADERS": json.dumps({
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": "2022-06-28",
    })
}
```

## 默认模型：DeepSeek-V4-Flash

Notion 场景通常包含中文会议纪要、项目文档和多轮编辑记录。默认使用 `deepseek-v4-flash`，兼顾工具调用、响应速度和成本。只有超长文档或中文整理效果经过验证仍不满足要求时，再切换其他模型。

该示例已经通过共享的 `llm_config.py` 支持 OpenAI-compatible endpoint，可以直接配置：

```bash
export DEEPSEEK_API_KEY=your-deepseek-key
export OPENAI_BASE_URL=https://api.deepseek.com
export OPENAI_MODEL=deepseek-v4-flash
```

## 准备 Notion

### 1. 创建 Integration

在 [Notion Integrations](https://www.notion.so/my-integrations) 创建 Integration，并复制 Internal Integration Token。

学习阶段只授予当前页面需要的能力：

- 只读练习：读取内容。
- 编辑练习：额外开启插入和更新内容。

### 2. 把页面共享给 Integration

打开目标页面，在连接设置中添加刚创建的 Integration。只有创建 token 但没有共享页面时，MCP Server 无法读取该页面。

### 3. 找到 page ID

page ID 位于 Notion 页面 URL 中。运行脚本时可以作为命令行参数传入，代码不会读取 `NOTION_PAGE_ID` 环境变量。

## 安装与运行

```bash
cd mcp-demos/03-notion-mcp-agent
pip install -r requirements.txt

export NOTION_API_KEY=your-notion-integration-token
export DEEPSEEK_API_KEY=your-deepseek-key
export OPENAI_BASE_URL=https://api.deepseek.com
export OPENAI_MODEL=deepseek-v4-flash

python notion_mcp_agent.py your-notion-page-id
```

还需要 Node.js，因为 Notion MCP Server 由 `npx` 启动：

```bash
node --version
npx --version
```

如果不传 page ID，程序会在终端询问；空输入会直接报错，不会自动选择默认页面。

## 建议的验证顺序

先只读，再写入：

```text
1. 读取当前页面标题和一级标题，不要修改内容。
2. 搜索页面中是否出现“风险”一词，并返回对应段落。
3. 在页面末尾新增一个“测试记录”段落，写入当前日期。
```

每一步都应看到对应 MCP Tool。第三步有副作用，执行前确认页面和 Integration 权限正确。

## 会话记忆

代码使用：

```python
SqliteDb(db_file="agno.db")
```

每次启动会生成新的 `user_id` 和 `session_id`。数据库文件可以保留历史记录，但当前实现不会自动复用上一次的 ID，因此“写入数据库”不等于“重启后自动续接同一会话”。

## 常见问题

- 找不到页面：确认页面已共享给 Integration，而不只是 workspace 中存在。
- 401/403：检查 `NOTION_API_KEY`、Integration capabilities 和页面权限。
- `npx` 失败：安装 Node.js，并单独测试 `npx -y @notionhq/notion-mcp-server`。
- 模型能读不能写：确认 Integration 有写权限，并检查 Agent 是否调用了写入工具。
- 页面 ID 为空：通过命令行参数或交互提示提供，当前代码没有默认值。

## 金融场景练习

把一个 Notion 页面作为投研 notebook：

1. 搜索某家公司的历史会议纪要。
2. 新增“核心假设、验证数据、主要风险”三个区块。
3. 把每次更新写成带日期的记录，而不是覆盖原文。

写入属于外部状态变更，正式使用时应增加预览和人工确认。

## 参考资料

- [Notion MCP Server](https://github.com/makenotion/notion-mcp-server)
- [DeepSeek Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/)
