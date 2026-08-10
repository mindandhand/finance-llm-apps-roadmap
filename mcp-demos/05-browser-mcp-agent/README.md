# 05：用 Playwright MCP 控制浏览器

本节让 Agent 通过 Playwright MCP 打开网页、读取页面、点击控件、填写表单和截图。浏览器是真实执行环境，模型只负责规划下一步动作。

## 学习目标

完成本节后，你应该能够：

- 解释浏览器状态为什么必须跨多次 Tool Call 保持。
- 区分页面文本、DOM/可访问性信息和截图。
- 观察“读取页面 → 选择元素 → 执行动作 → 再次检查”的 Agent 循环。
- 为浏览器自动化设置只读、安全和权限边界。

## 架构

```text
Streamlit 页面
  -> mcp-agent
  -> deepseek-v4-pro
  -> Playwright MCP Server
  -> 浏览器进程
  -> 页面状态、文本或截图返回模型
```

核心配置位于：

```text
mcp_agent.config.yaml
mcp_agent.secrets.yaml
```

## 默认模型：DeepSeek-V4-Pro

浏览器任务往往需要多步工具调用。默认使用 `deepseek-v4-pro`，先依赖 DOM、可访问性树和页面文本完成操作。如果任务必须让模型直接理解截图，再切换支持视觉输入的千问模型。

仓库中的 `mcp_agent.config.yaml` 仍使用已经停用的 `deepseek-chat`，运行前应改成：

```yaml
openai:
  base_url: "https://api.deepseek.com"
  default_model: "deepseek-v4-pro"
```

然后创建密钥文件：

```bash
cp mcp_agent.secrets.yaml.example mcp_agent.secrets.yaml
```

编辑 `mcp_agent.secrets.yaml`：

```yaml
openai:
  api_key: "your-deepseek-key"
```

该密钥文件已用于本地配置，不应提交到 Git。

## 安装与运行

```bash
cd mcp-demos/05-browser-mcp-agent
pip install -r requirements.txt

node --version
npx --version

streamlit run main.py
```

Playwright MCP Server 由 `mcp-agent` 根据 `mcp_agent.config.yaml` 启动。

## 建议的验证顺序

先从公开页面和只读动作开始：

```text
1. 打开 https://example.com。
2. 返回页面标题和主要文本。
3. 截取页面截图。
4. 打开一个公开文档页，列出所有一级标题。
```

确认读取稳定后，再测试点击和表单。不要一开始就登录真实账户。

## 浏览器 Agent 的循环

一次完整操作通常不是一个 Tool Call：

```text
读取当前页面
  -> 找到目标元素
  -> 点击或输入
  -> 等待页面变化
  -> 再读取页面
  -> 判断任务是否完成
```

如果模型在点击后不再检查页面，它可能把“发出了动作”误当成“动作已成功”。

## 本地模型选项

本地模型必须支持 OpenAI-compatible API 和工具调用。配置示例：

```yaml
openai:
  base_url: "http://localhost:11434/v1"
  default_model: "your-tool-capable-model"
```

```yaml
openai:
  api_key: "local"
```

浏览器任务对模型要求高。小模型常见问题包括选错元素、参数格式错误、动作后停止，以及无法根据页面变化修正计划。

## 安全边界

- 默认只访问公开页面。
- 不在测试中输入真实密码、支付信息或高权限 token。
- 点击“提交、发布、删除、购买”前增加人工确认。
- 限制可访问域名，避免模型跟随页面内容跳转到未知站点。
- 网页文本是不可信输入，不能把页面中的提示当成系统指令。

## 常见问题

- 浏览器未启动：检查 Node.js、`npx` 和 Playwright MCP 日志。
- 模型不调用工具：检查模型是否支持 Function Calling，以及 base URL 是否生效。
- 点击失败：先让 Agent 重新读取页面，确认元素名称和页面状态。
- 页面一直加载：增加等待或缩小任务，不要连续重复点击。
- 截图不能被理解：确认当前框架确实把图像内容传给多模态模型，而不是只返回文件路径。

## 金融场景练习

只读访问交易所或上市公司公开页面：

1. 打开公告列表。
2. 找到最新公告标题和日期。
3. 进入公告详情。
4. 提取原始链接并生成摘要。

不要用浏览器 Agent 绕过登录、验证码、反爬机制或网站授权边界。

## 参考资料

- [Playwright MCP](https://github.com/microsoft/playwright-mcp)
- [mcp-agent](https://github.com/lastmile-ai/mcp-agent)
- [DeepSeek Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/)
- [千问视觉理解（必须处理截图时）](https://help.aliyun.com/zh/model-studio/vision-model/)
