# 知识图谱 RAG 与可验证引用

这是一个基于 Neo4j 和 DeepSeek 远端模型的 Knowledge Graph RAG demo。应用从文档中抽取实体和关系，写入知识图谱，再通过图遍历生成带来源引用的中文回答。

## 功能

- 使用 DeepSeek 远端模型抽取实体和关系。
- 使用 Neo4j 保存实体节点和关系边。
- 支持内置样例文档和自定义文本。
- 根据问题匹配起点实体，并进行两跳关系扩展。
- 生成带 `[1]`、`[2]` 引用标记的回答。
- 展示推理轨迹、来源文档、来源片段和引用路径。
- 支持查看实体数、关系数和清空图谱。

核心流程：

```text
文档
  -> DeepSeek 抽取实体和关系
  -> 写入 Neo4j
  -> 根据问题找到起点实体
  -> 多跳遍历相关实体
  -> DeepSeek 生成带引用的答案
  -> 展示推理轨迹和来源
```

这个版本不再使用 Ollama，不需要拉取或运行本地 LLM 镜像。只有 Neo4j 需要通过 Podman 在本机运行。

## 技术栈

| 组件 | 作用 |
| --- | --- |
| Streamlit | Web UI |
| DeepSeek API | 远端实体抽取和答案生成 |
| Neo4j | 知识图谱数据库 |
| Python dataclasses | 表示实体、关系、引用和答案 |
| Cypher | Neo4j 图查询 |

## 文件结构

```text
13-knowledge_graph_rag_citations/
├── knowledge_graph_rag.py  # Streamlit 应用和核心图谱 RAG 逻辑
├── requirements.txt        # Python 依赖
├── compose.yaml            # Podman Compose 编排示例
├── Dockerfile              # 可由 Podman 构建的应用镜像
└── README.md               # 本说明文档
```

统一脚本位于：

```text
finance-llm-agent-demos/scripts/pull_13_images.sh
finance-llm-agent-demos/scripts/run_13_services.sh
finance-llm-agent-demos/scripts/run_13_agent.sh
```

## 前置条件

需要准备：

- Podman 和一个能正常运行的 `podman machine`。
- Python 3.9 或更高版本。
- DeepSeek API Key。

Neo4j 默认连接配置为：

```text
Browser:  http://localhost:7474
Bolt:     bolt://localhost:7687
用户名:    neo4j
密码:      password
```

## 配置 DeepSeek

推荐在仓库根目录或本 demo 目录创建 `.env`。`.env` 不要提交到 Git：

```bash
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_ID=deepseek-chat
```

也可以直接设置环境变量：

```bash
export DEEPSEEK_API_KEY="你的 DeepSeek API Key"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
export DEEPSEEK_MODEL_ID="deepseek-chat"
```

代码通过 OpenAI-compatible 的 `/chat/completions` 接口调用远端模型。若使用其他兼容服务，只需替换 `DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL_ID`。

## 启动 Neo4j

从仓库根目录执行：

```bash
./finance-llm-agent-demos/scripts/pull_13_images.sh
./finance-llm-agent-demos/scripts/run_13_services.sh
```

拉取脚本只处理 Neo4j 镜像。默认使用镜像代理，避免直接连接 Docker Hub：

```text
docker.m.daocloud.io/library/neo4j:latest
```

如果需要替换镜像地址：

```bash
NEO4J_IMAGE=<可访问的 Neo4j 镜像地址> \
./finance-llm-agent-demos/scripts/pull_13_images.sh
```

如果 Podman machine 尚未运行：

```bash
podman machine start
```

也可以使用 Compose：

```bash
cd finance-llm-agent-demos/13-knowledge_graph_rag_citations
podman compose up -d neo4j
```

查看状态和日志：

```bash
podman ps
podman logs -f kg-rag-neo4j
```

## 安装 Python 依赖

推荐使用虚拟环境：

```bash
cd finance-llm-agent-demos/13-knowledge_graph_rag_citations
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

依赖包括 Streamlit、Neo4j、Requests 和 python-dotenv，不再需要 `ollama` Python 包。

## 启动应用

从仓库根目录运行：

```bash
./finance-llm-agent-demos/scripts/run_13_agent.sh
```

也可以在 demo 目录运行：

```bash
cd finance-llm-agent-demos/13-knowledge_graph_rag_citations
python -m streamlit run knowledge_graph_rag.py
```

启动脚本会优先使用：

```text
13-knowledge_graph_rag_citations/.venv/bin/python
```

如果没有该环境，会尝试 `python3.11`，再退回 `python3`。使用其他解释器时：

```bash
PYTHON_BIN=/path/to/python ./finance-llm-agent-demos/scripts/run_13_agent.sh
```

启动后打开终端显示的 Streamlit 地址，通常是 `http://localhost:8501` 或 `http://localhost:8502`。

## 使用流程

### 1. 配置连接

侧边栏默认值为：

```text
Neo4j URI:  bolt://localhost:7687
Neo4j 用户: neo4j
Neo4j 密码: password
远端模型:   deepseek-chat
```

API Key 从 `DEEPSEEK_API_KEY` 读取，不会显示在页面上。API 地址默认是 `https://api.deepseek.com`。

### 2. 添加文档

在「添加文档」页签中选择内置样例：

- `AI 研究论文`
- `公司报告`

也可以粘贴自定义文档并填写文档名称。点击「抽取并写入知识图谱」后，系统会：

1. 把文档和 JSON 输出要求发送给 DeepSeek。
2. 解析 `entities` 和 `relationships`。
3. 将实体写入 Neo4j 的 `Entity` 节点。
4. 将关系写入 `RELATES_TO` 边。
5. 展示抽取出的实体和关系。

### 3. 提问

在「提问」页签输入问题，例如：

```text
GraphRAG 的关键概念是什么？是谁提出的？
```

系统会：

1. 在图谱中查找相关实体。
2. 从起点实体做两跳关系扩展。
3. 为来源生成 `[1]`、`[2]` 编号。
4. 要求 DeepSeek 为关键结论添加行内引用。
5. 将引用编号映射回来源文档和原文片段。

### 4. 查看图谱

在「查看图谱」页签可以查看实体总数、关系总数，也可以清空当前图谱。

## 核心代码解读

### `call_remote_model()`

该函数负责远端模型调用：

- 从环境变量读取 `DEEPSEEK_API_KEY`。
- 使用 `DEEPSEEK_BASE_URL` 拼接 `/chat/completions`。
- 使用 `DEEPSEEK_MODEL_ID` 指定模型。
- 设置请求超时，检查 HTTP 状态码和返回结构。
- 不在日志或异常中打印 API Key。

### `extract_entities_with_llm()`

该函数将文档发送给远端模型，并要求严格返回：

```json
{
  "entities": [
    {"name": "...", "type": "...", "description": "..."}
  ],
  "relationships": [
    {"source": "...", "target": "...", "type": "...", "description": "..."}
  ]
}
```

`parse_json_response()` 兼容模型把 JSON 包在 Markdown code fence 中的情况。解析后的数据会转换为 `Entity` 和 `Relationship` 对象，再写入 Neo4j。

### `KnowledgeGraphManager`

这个类封装 Neo4j 操作：

- `add_entity()`：写入实体节点。
- `add_relationship()`：写入实体关系。
- `semantic_search()`：用文本匹配查找起点实体。
- `find_related_entities()`：从起点实体做 N 跳扩展。
- `clear_graph()`：清空图谱。

### `generate_answer_with_citations()`

这是带引用回答的核心流程：

1. `semantic_search()` 找到初始实体。
2. `find_related_entities()` 扩展相关实体。
3. 为每条上下文生成来源编号。
4. 把上下文发送给远端模型。
5. 用正则提取回答中的引用编号。
6. 将引用编号映射回来源文档和原文片段。

## 与传统向量 RAG 的区别

| 传统向量 RAG | 知识图谱 RAG |
| --- | --- |
| 找相似文本块 | 找实体和关系 |
| 适合局部事实问答 | 适合多跳关系问题 |
| 引用通常是文本块 | 引用可以绑定实体、关系和路径 |
| 推理过程不一定透明 | 可以展示图遍历轨迹 |

## 常见问题

### Neo4j 连接失败

确认 machine 和容器：

```bash
podman machine start
podman ps | grep neo4j
```

确认端口 `7474` 和 `7687` 没有被其他进程占用。默认密码是 `password`；如果启动容器时修改过密码，需要同步修改侧边栏。

### DeepSeek API 调用失败

检查配置是否存在：

```bash
printenv DEEPSEEK_API_KEY
printenv DEEPSEEK_BASE_URL
printenv DEEPSEEK_MODEL_ID
```

不要把真实 API Key 写入 README、Python 文件或 Git。HTTP 401 通常表示 Key 不正确，HTTP 429 表示额度或频率限制，HTTP 5xx 通常表示远端服务暂时不可用。

### 实体抽取失败或实体为空

可能原因：

- DeepSeek API Key 未配置。
- 远端模型返回的内容不是合法 JSON。
- 文档太短或结构不清晰。
- 远端服务繁忙或网络请求超时。

可以先用内置样例文档测试，并确认 `DEEPSEEK_MODEL_ID` 是当前账号可用的模型。

### 回答没有引用

可能原因：

- 图谱中没有匹配到相关实体。
- 回答没有按 `[1]`、`[2]` 格式输出引用。
- 上下文为空或相关性太弱。

可以先清空图谱，重新添加内置样例，再用默认问题测试。

## 安全边界

这个 demo 会把你粘贴的文档和问题发送给远端 DeepSeek API。请注意：

- 不要上传未经授权的敏感文档或个人信息。
- `DEEPSEEK_API_KEY` 只放在环境变量或未跟踪的 `.env` 文件中。
- Neo4j 默认密码 `password` 只适合本地 demo。
- 生产环境不要暴露默认端口和默认密码。
- LLM 抽取的实体、关系和回答需要人工复核。

## 扩展方向

- 增加 PDF / Markdown 文件上传。
- 使用 Neo4j 全文索引或向量索引替代简单文本匹配。
- 为关系增加置信度和来源片段。
- 将引用粒度从 entity chunk 提升到具体句子。
- 增加图可视化组件，显示节点和关系。
- 增加 Pydantic schema 校验远端模型的抽取结果。

本项目仅用于技术学习和原型验证，不构成投资、法律、审计或其他专业建议。
