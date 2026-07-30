# 14 浏览器 MCP Agent

这是一个基于 Streamlit、MCP-Agent 和 Playwright MCP 的浏览器自动化示例。用户用自然语言描述任务，Agent 调用浏览器工具完成打开网页、点击、滚动、输入、截图和内容提取。

本项目使用远端 DeepSeek 模型，不使用 Ollama，也不需要本地大模型容器。

## 运行前提

- Python 3.11 或更高版本
- Node.js 和 npm
- 可访问的 Chromium 浏览器环境。Playwright MCP 会通过 `npx @playwright/mcp@latest` 管理浏览器工具
- DeepSeek API Key

检查 Node.js：

```bash
node --version
npm --version
```

## 安装依赖

在仓库根目录执行：

```bash
cd finance-llm-agent-demos/14-browser_mcp_agent
python3.11 -m pip install -r requirements.txt
```

第一次启动时，`npx` 可能需要下载 `@playwright/mcp`，请保持网络可用。

## 配置 DeepSeek

推荐使用仓库根目录或项目目录下未跟踪的 `.env` 文件：

```env
DEEPSEEK_API_KEY=你的DeepSeek API Key
```

程序会把 `DEEPSEEK_API_KEY` 兼容映射到 MCP-Agent 使用的 `OPENAI_API_KEY`。模型地址和模型名称配置在 `mcp_agent.config.yaml` 中：

```yaml
openai:
  base_url: "https://api.deepseek.com/v1"
  default_model: "deepseek-chat"
```

也可以使用未跟踪的密钥文件：

```bash
cp mcp_agent.secrets.yaml.example mcp_agent.secrets.yaml
```

然后填写：

```yaml
openai:
  api_key: 你的DeepSeek API Key
```

不要把真实 API Key 写入 Git 跟踪文件或提交记录。

## 启动

从仓库根目录执行统一启动脚本：

```bash
./finance-llm-agent-demos/scripts/run_14_agent.sh
```

或者在项目目录直接启动：

```bash
cd finance-llm-agent-demos/14-browser_mcp_agent
python3.11 -m streamlit run main.py
```

默认地址：`http://127.0.0.1:8501`。

## 使用示例

在“浏览器指令”中输入：

```text
打开 https://www.python.org，提取首页标题和主要导航链接。
```

```text
打开 https://github.com/Shubhamsaboo/awesome-llm-apps，向下滚动，找到浏览器 MCP 相关目录并总结 README。
```

```text
打开一个网页，截取页面主要内容区域，并说明页面的核心信息。
```

Agent 会通过 Playwright MCP 执行浏览器动作，然后把结果返回到页面中。

## 工作流程

1. Streamlit 收集用户的自然语言指令。
2. `MCPApp` 启动 `@playwright/mcp` server。
3. `Agent` 连接 `playwright` server 并发现可用工具。
4. `OpenAIAugmentedLLM` 使用 DeepSeek 的 OpenAI-compatible API 规划任务。
5. Agent 多次调用浏览器工具完成导航和信息提取。
6. Streamlit 展示最终结果。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `main.py` | Streamlit 页面、MCP-App、浏览器 Agent 和请求处理逻辑 |
| `mcp_agent.config.yaml` | MCP server、DeepSeek API 地址和默认模型配置 |
| `mcp_agent.secrets.yaml.example` | 本地密钥文件模板 |
| `requirements.txt` | Python 依赖 |
| `../../scripts/run_14_agent.sh` | 统一启动脚本 |

## 常见问题

### 未找到 DeepSeek API Key

确认 `.env` 位于以下任一位置：

- `finance-llm-agent-demos/14-browser_mcp_agent/.env`
- `finance-llm-agent-demos/.env`
- 仓库根目录 `.env`

并且变量名称必须是：

```env
DEEPSEEK_API_KEY=你的Key
```

### `npx` 或 Playwright MCP 启动失败

检查 Node.js 和 npm：

```bash
node --version
npm --version
npx @playwright/mcp@latest --help
```

如果是网络问题，先确认 npm 能访问包仓库，再重新启动。

### 浏览器任务执行失败

浏览器自动化任务需要清晰的目标和步骤。建议提供完整 URL，并把复杂任务拆成导航、操作和提取三个阶段。某些需要登录、验证码或强交互的网站可能无法自动完成。

### MCP server 没有工具

查看 `mcp_agent.config.yaml` 中的 server 名称是否为 `playwright`，并确认 `main.py` 中的 `server_names=["playwright"]` 一致。

## 安全说明

- API Key 只放在环境变量或未跟踪的 `mcp_agent.secrets.yaml` 中。
- 不要让浏览器 Agent 访问包含账号、密码、Cookie 或内部数据的页面。
- 浏览器操作可能产生真实副作用，提交表单、发送消息和删除数据前应使用明确的人工确认流程。
