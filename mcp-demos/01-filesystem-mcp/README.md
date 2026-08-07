# 01：用 Agno 连接 Filesystem MCP

本节从最小 MCP 链路开始：Agno Agent 通过 stdio 启动 Filesystem MCP Server，获取文件工具，再由 DeepSeek 根据用户请求选择工具。

## 学习目标

- 理解 Agent、MCP Client、MCP Server、stdio 和 Tool 的关系；
- 找到 Filesystem Server 的目录授权边界；
- 观察模型如何选择目录查询、文件读取和文件写入工具；
- 区分模型决策与文件系统操作。

## 默认模型

默认使用 `deepseek-v4-flash`。本例只有少量、结构清晰的文件工具，用 Flash 模型即可验证工具调用循环，通常无需切换其他模型。

代码通过 `../llm_config.py` 创建 Agno 的 `OpenAIChat`，已经支持 DeepSeek 的 OpenAI-compatible API：

```python
model=create_agno_openai_model(
    OpenAIChat,
    default_model="deepseek-v4-flash",
)
```

## 架构

```text
用户请求
  ↓
Agno Agent + DeepSeek V4 Flash
  ↓
MCPTools
  ↓ stdio
Filesystem MCP Server
  ↓
当前示例的 data/ 目录
```

Filesystem Server 只能访问 `01-filesystem-mcp/data/`。程序首次运行会创建目录和 `sample.txt`，不会再把整个 `mcp-demos` 目录暴露给模型。

## 运行

进入当前目录后安装依赖：

```bash
pip install -r requirements.txt
```

设置 DeepSeek：

```bash
export DEEPSEEK_API_KEY=your-deepseek-key
export OPENAI_BASE_URL=https://api.deepseek.com/v1
export OPENAI_MODEL=deepseek-v4-flash
```

确认 Node.js 和 `npx` 可用，然后启动：

```bash
node --version
npx --version
python agent.py
```

## 可以尝试

- “列出授权目录中的文件。”
- “读取 `sample.txt` 并总结内容。”
- “创建 `notes.txt`，写入今天的学习要点。”
- “把 `notes.txt` 的内容翻译成英文。”

输入 `exit`、`quit` 或 `退出` 结束会话。

## 阅读代码时重点关注

1. `DEMO_FOLDER` 如何把权限限制在当前示例的 `data/`。
2. `StdioServerParameters` 如何声明 `npx` 启动命令。
3. `async with MCPTools(...)` 如何管理 Server 生命周期。
4. `tools=[mcp_tools]` 如何把发现的工具交给 Agent。
5. instructions 为什么要求覆盖或删除文件前确认。

## 安全边界

- 不要把授权路径改成用户主目录或仓库根目录。
- 演示目录中不要放密钥、账户文件或真实业务数据。
- 模型生成的文件参数仍需由 MCP Server 和应用层校验。
- 生产环境应进一步限制可用工具，并记录写操作审计日志。

## 常见问题

- 提示缺少模型 Key：检查 `DEEPSEEK_API_KEY`。
- 找不到模型：确认设置了 `OPENAI_MODEL=deepseek-v4-flash`。
- `npx` 找不到：安装 Node.js 并确认 npm 的可执行目录在 `PATH` 中。
- Server 启动失败：检查网络是否允许下载 `@modelcontextprotocol/server-filesystem`。
- Agent 不调用工具：确认模型支持 Tool Calling，并打开 Agno 调试日志继续排查。
