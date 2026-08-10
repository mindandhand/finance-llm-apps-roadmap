# 04：用 GitHub MCP 分析仓库、Issue 和 PR

本节把 Streamlit UI、Agno Agent 和 GitHub 官方 MCP Server 连在一起。用户用中文提问，模型选择仓库工具，Docker 容器通过 GitHub API 返回实时数据。

## 学习目标

完成本节后，你应该能够：

- 解释 Docker stdio 与普通 stdio 的区别。
- 用 `GITHUB_TOOLSETS` 限制暴露给 Agent 的工具集合。
- 区分模型 API key 和 GitHub Personal Access Token。
- 用代码模型分析仓库活动，而不是让模型凭记忆猜测 GitHub 状态。

## 架构

```text
Streamlit 页面
  -> Agno Agent
  -> deepseek-v4-pro
  -> MCP Client
  -> docker run ghcr.io/github/github-mcp-server
  -> GitHub API
```

当前容器只启用：

```text
repos,issues,pull_requests
```

这比把 GitHub MCP Server 的所有能力都交给 Agent 更容易审计。

## 默认模型：DeepSeek-V4-Pro

本节的主要输入是仓库结构、Issue、PR 和代码上下文。默认使用 `deepseek-v4-pro`，完成工具调用、代码理解和综合分析。只有大型代码生成或专项 Coding Agent 评测显示收益明确时，再切换 `qwen3-coder-plus`。

该示例已经通过 `llm_config.py` 支持 OpenAI-compatible endpoint：

```bash
export DEEPSEEK_API_KEY=your-deepseek-key
export OPENAI_BASE_URL=https://api.deepseek.com
export OPENAI_MODEL=deepseek-v4-pro
```

页面侧边栏也能输入 DeepSeek key。启动前设置环境变量可以同时固定 endpoint 和模型名称，结果更容易复现。

## 准备 GitHub Token

在 GitHub 创建 Personal Access Token。按实际查询范围授予最小权限：

- 只分析公开仓库时，不要默认授予完整私有仓库权限。
- 需要读取私有仓库时，只授权目标仓库。
- 本例以查询为主，不需要写 Issue 或合并 PR 的权限。

不要把 token 写进 README、命令历史或 Git。

## 安装与运行

```bash
cd mcp-demos/04-github-mcp-agent
pip install -r requirements.txt

export DEEPSEEK_API_KEY=your-deepseek-key
export OPENAI_BASE_URL=https://api.deepseek.com
export OPENAI_MODEL=deepseek-v4-pro
export GITHUB_TOKEN=your-github-token

docker --version
docker ps
streamlit run github_agent.py
```

页面默认仓库可以改成任意 `owner/repo`。

## 验证顺序

### 1. 仓库信息

```text
概括 mindandhand/finance-llm-apps-roadmap 最近的仓库活动，并给出原始链接。
```

### 2. Issue

```text
列出当前开放的 bug Issue，按更新时间排序。
```

### 3. Pull Request

```text
列出最近合并的 PR，说明每个 PR 修改了什么。
```

成功标准是回答来自 GitHub MCP Tool 返回值，并包含可核对的仓库链接。模型不能访问的字段应明确说明，不能补造。

## 关键代码

GitHub Server 由 Docker 以 stdio 方式启动：

```python
StdioServerParameters(
    command="docker",
    args=[
        "run", "-i", "--rm",
        "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
        "-e", "GITHUB_TOOLSETS",
        "ghcr.io/github/github-mcp-server",
    ],
)
```

`-i` 保持标准输入，MCP Client 才能和容器内 Server 通信；`--rm` 在进程结束后删除临时容器。

## 常见问题

- Docker daemon 未运行：`docker ps` 会直接失败。
- 容器无法拉取：检查网络和 GitHub Container Registry 访问。
- 401/403：检查 token 是否有效以及是否能访问目标仓库。
- 查询超时：代码设置了 120 秒超时，先缩小仓库和查询范围。
- 模型回答了不存在的字段：要求它只使用工具结果，并返回对应链接。

## 金融场景练习

比较三个开源量化仓库：

```text
最近 90 天提交活跃度
开放 Issue 数量与响应速度
PR 合并节奏
最近版本发布时间
是否存在长期未处理的严重 bug
```

这些指标只能辅助判断项目维护状况，不能直接代表策略收益或代码安全性。

## 参考资料

- [GitHub MCP Server](https://github.com/github/github-mcp-server)
- [DeepSeek Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/)
- [Qwen3-Coder-Plus（需要专项代码模型时）](https://help.aliyun.com/zh/model-studio/qwen3-coder-plus)
