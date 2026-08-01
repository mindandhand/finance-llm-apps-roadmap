# RAG 故障诊断门诊

这是一个命令行 RAG 故障诊断工具。用户可以选择内置案例或粘贴真实故障描述，程序会让 DeepSeek 从 P01 到 P12 的故障模式中选择主要模式，并给出最小结构性修复建议。

## 功能

- 诊断检索、分块、索引、路由、工具调用、配置和多 Agent 等常见问题
- 内置 P01 到 P12 故障模式库
- DeepSeek 直接 HTTP 接口，不使用 OpenAI SDK
- 中文交互和中文诊断结果
- 对临时网络错误、429 和 5xx 自动重试 3 次
- 将每轮诊断保存为 `rag_failure_report.json`
- 不需要 Qdrant、Exa、Google 或代理

## 故障模式

| 编号 | 模式 | 典型症状 |
| --- | --- | --- |
| P01 | 检索幻觉 / 事实依据漂移 | 回答违背或忽略检索文档 |
| P02 | 文本分块边界问题 | 事实被拆散、截断或错误组合 |
| P03 | Embedding 不匹配 | 向量相似度与真实相关性不一致 |
| P04 | 索引偏移或过期 | 返回旧数据或缺失数据 |
| P05 | 查询改写或路由错位 | 问题被发送到错误工具或数据集 |
| P06 | 长链推理漂移 | 多步骤任务逐渐忘记约束 |
| P07 | 工具调用误用 | 参数错误或缺少事实依据 |
| P08 | 会话记忆泄漏或上下文缺失 | 对话丢失重要事实 |
| P09 | 评估盲区 | 测试通过但真实故障仍失败 |
| P10 | 启动顺序或依赖未就绪 | 部署初期出现崩溃或 5xx |
| P11 | 环境配置或密钥漂移 | 本地正常，测试或生产环境失败 |
| P12 | 多租户或多 Agent 相互干扰 | 状态或资源被相互覆盖 |

## 运行

```bash
cd 10-rag_failure_diagnostics_clinic
python -m pip install -r requirements.txt
```

在当前目录、`finance-llm-agent-demos` 根目录或工作区根目录的 `.env` 中配置：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_ID=deepseek-chat
```

启动：

```bash
python rag_failure_diagnostics_clinic.py
```

或从仓库根目录运行：

```bash
./scripts/run_10_agent.sh
```

## 使用流程

1. 启动命令行程序。
2. 输入 `1`、`2` 或 `3`，选择内置故障案例；输入 `p` 可以粘贴自己的故障描述。
3. 自定义描述输入完成后，输入空行提交。
4. 程序调用 DeepSeek，输出主要模式、次要候选、判断依据和最小结构性修复。
5. 输入 `y` 可以继续诊断其他问题，报告会覆盖写入当前目录的 `rag_failure_report.json`。

## 代码解读

核心代码位于 `rag_failure_diagnostics_clinic.py`，主要分为以下部分：

1. `PATTERNS` 保存 P01 到 P12 的模式编号、名称和典型症状，是诊断提示词的知识边界。
2. `build_system_prompt()` 将模式库转换为中文系统提示，要求模型只能选择已有编号，并按照固定 Markdown 结构回答。
3. `choose_bug_description()` 负责命令行输入，支持三个内置案例和用户自定义的多行故障描述。
4. `read_model_config()` 从 `.env` 加载 DeepSeek 配置，不打印 API Key。
5. `call_deepseek()` 使用 `requests` 直接调用 `/chat/completions`，对临时网络错误和服务端错误进行重试。
6. `run_once()` 组织一次诊断，并把原始故障、模型名称和诊断结果写入 JSON 报告。
7. `main()` 负责循环诊断，直到用户选择结束。

## 扩展方向

- 将内置模式抽取到单独的 YAML 或 JSON 文件。
- 为每个模式增加日志关键词、严重程度和验证步骤。
- 给报告增加负责人、影响范围和修复状态字段。
- 使用 BM25 或本地 RAG 检索历史故障报告，辅助相似案例分析。

本项目仅用于技术学习和研究参考，不构成生产事故处理、投资或其他专业建议。
