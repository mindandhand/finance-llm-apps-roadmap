## AI 个人财务规划师

这个应用是一个个人财务规划 Streamlit 应用，使用 DeepSeek 模型服务，并结合 DuckDuckGo 网页搜索，为用户生成个性化预算、储蓄策略和投资规划建议。

### 功能

- 支持 DeepSeek API
- 通过 DuckDuckGo 检索财务建议、储蓄策略和投资机会
- 根据用户目标和当前财务状况生成个性化规划
- 将研究 Agent 的检索结果传递给规划 Agent
- 提供本地 Streamlit 交互式界面

### 快速开始

1. 进入项目目录

```bash
cd 03-ai_personal_finance_agent
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 配置模型服务

在 `03-ai_personal_finance_agent/.env` 或仓库根目录 `finance-llm-agent-demos/.env` 中填入你的 DeepSeek API key、服务地址和模型名：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_ID=deepseek-chat
```

如果需要使用其他 DeepSeek 模型，可以把 `DEEPSEEK_MODEL_ID` 设置为服务支持的模型名，例如 `deepseek-chat`、`deepseek-reasoner`、`deepseek-v4-flash` 或 `deepseek-v4-pro`。

4. 运行 Streamlit 应用

```bash
streamlit run finance_agent.py
```

也可以从 `finance-llm-agent-demos` 仓库根目录运行：

```bash
./scripts/run_03_agent.sh
```

启动成功后，浏览器会打开本地页面：

```text
http://localhost:8501
```

### 示例输入

可以在页面中尝试下面这些输入：

- **财务目标**：三年内攒够 30 万元首付，同时保留 6 个月应急金。
- **当前状况**：月收入 25000 元，房租 6000 元，日常支出 8000 元，已有存款 120000 元，没有信用卡债务。

- **财务目标**：一年内还清信用卡债务，并建立稳定预算。
- **当前状况**：月收入 18000 元，信用卡欠款 50000 元，月最低还款 3000 元，房租 4500 元，日常支出约 7000 元。

- **财务目标**：为 10 年后的子女教育准备资金，并开始长期投资。
- **当前状况**：家庭月收入 42000 元，月支出 26000 元，已有基金和现金共 300000 元，每月可投资 8000 元。

- **财务目标**：准备提前退休，希望评估储蓄率和投资方向。
- **当前状况**：月收入 60000 元，月支出 28000 元，已有投资资产 1500000 元，房贷每月 12000 元。

### 访问方式说明

`http://localhost:8501` 是本地 Streamlit 页面。这个项目不是 AgentOS API 服务，因此不需要连接本地 AgentUI。

如果页面无法使用，可按下面顺序排查：

1. 确认终端中 `streamlit run finance_agent.py` 正常运行。
2. 打开 `http://localhost:8501`。
3. 确认页面中已经填写 DeepSeek API Key，或 `.env` 中已经配置对应变量。

> 本项目仅用于技术学习与原型验证，不构成投资、税务、保险或法律建议。
