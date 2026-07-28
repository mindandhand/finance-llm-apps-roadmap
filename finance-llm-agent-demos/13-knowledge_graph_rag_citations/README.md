# 知识图谱 RAG 与可验证引用

这是一个基于 Neo4j 和 Ollama 的本地 Knowledge Graph RAG demo。它演示如何从文档中抽取实体和关系，构建知识图谱，再通过图遍历生成带来源引用的回答。

传统向量 RAG 通常按相似度找文本片段；知识图谱 RAG 更关注：

```text
文档
  -> 抽取实体和关系
  -> 写入 Neo4j 知识图谱
  -> 根据问题找到起点实体
  -> 多跳遍历相关实体
  -> 生成带 [1] [2] 引用的答案
  -> 展示推理轨迹和来源文本
```

## 功能

- 使用 Ollama 本地模型抽取实体和关系。
- 使用 Neo4j 存储实体节点和关系边。
- 支持从样例文档或自定义文本构建知识图谱。
- 根据问题做实体匹配和两跳关系扩展。
- 生成带 `[1]`、`[2]` 引用标记的中文回答。
- 展示推理轨迹，说明系统从哪些实体开始扩展。
- 展示来源文档、来源片段、置信度和推理路径。
- 支持查看实体数和关系数。
- 支持清空图谱，重新构建。

## 这个 demo 想说明什么

这个项目不是要替代成熟 GraphRAG 框架，而是用最小代码讲清楚几个关键边界：

- LLM 可以抽取实体和关系，但写入图数据库的结构要由代码控制。
- 回答问题时，不只是找相似文本，还可以沿实体关系做多跳扩展。
- 每个回答引用都应该能追溯到来源文档和原文片段。
- 推理轨迹应该展示给用户，方便判断答案是否可靠。

## 技术栈

| 组件 | 作用 |
| --- | --- |
| Streamlit | Web UI |
| Ollama | 本地 LLM 推理，默认模型 `llama3.2` |
| Neo4j | 知识图谱数据库 |
| Python dataclasses | 表示实体、关系、引用和答案 |
| Cypher | Neo4j 图查询 |

## 文件结构

```text
13-knowledge_graph_rag_citations/
├── knowledge_graph_rag.py  # Streamlit 应用和核心图谱 RAG 逻辑
├── requirements.txt        # Python 依赖
├── compose.yaml            # Podman Compose 编排示例
├── Dockerfile              # Podman 可直接构建的 Streamlit 应用镜像
└── README.md               # 本说明文档
```

仓库根目录还提供统一启动脚本：

```text
finance-llm-agent-demos/scripts/run_13_agent.sh
finance-llm-agent-demos/scripts/run_13_services.sh
finance-llm-agent-demos/scripts/pull_13_images.sh
```

## 前置条件

本 demo 需要两个本地服务：

- Neo4j：存储知识图谱。
- Ollama：运行本地模型。

如果你只想最快跑起来，可以使用 Podman 启动 Neo4j 和 Ollama；如果你已经本地安装了 Neo4j 和 Ollama，也可以手动启动。

## 方式一：Podman 启动依赖

从仓库根目录运行：

```bash
./finance-llm-agent-demos/scripts/pull_13_images.sh
./finance-llm-agent-demos/scripts/run_13_services.sh
```

这个脚本会启动两个容器：

- `kg-rag-neo4j`
- `kg-rag-ollama`

并在 Ollama 容器中拉取默认模型 `llama3.2`。镜像拉取和服务启动分开执行，便于先确认镜像仓库可用。

脚本默认使用以下镜像地址，避免直接连接 Docker Hub：

```text
docker.m.daocloud.io/library/neo4j:latest
docker.m.daocloud.io/ollama/ollama:latest
```

如果默认镜像仓库无法访问，可以替换镜像地址：

```bash
NEO4J_IMAGE=<可访问的 Neo4j 镜像地址> \\
OLLAMA_IMAGE=<可访问的 Ollama 镜像地址> \\
./finance-llm-agent-demos/scripts/pull_13_images.sh
```

如果你要换模型：

```bash
MODEL=mistral ./finance-llm-agent-demos/scripts/run_13_services.sh
```

默认配置：

```text
Neo4j Browser: http://localhost:7474
Neo4j Bolt:    bolt://localhost:7687
Neo4j User:    neo4j
Neo4j Password: password
Ollama Host:   http://localhost:11434
Model:         llama3.2
```

如果 Podman 还没有启动虚拟机，先运行：

```bash
podman machine start
```

也可以使用 Podman Compose：

```bash
cd finance-llm-agent-demos/13-knowledge_graph_rag_citations
podman compose up -d neo4j ollama
podman logs -f kg-rag-ollama
```

## 方式二：手动启动依赖

启动 Neo4j：

```bash
podman run -d --replace \
  --name kg-rag-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  -v kg_rag_neo4j_data:/data \
  neo4j:latest
```

启动 Ollama 容器并拉取模型：

```bash
podman run -d --replace \
  --name kg-rag-ollama \
  -p 11434:11434 \
  -v kg_rag_ollama_data:/root/.ollama \
  ollama/ollama:latest

podman exec kg-rag-ollama ollama pull llama3.2
```

如果 Ollama 不在默认地址，可以设置：

```bash
export OLLAMA_HOST=http://localhost:11434
```

## 安装 Python 依赖

建议使用虚拟环境：

```bash
cd finance-llm-agent-demos/13-knowledge_graph_rag_citations
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

如果依赖装在其他 Python 环境里，也可以通过 `PYTHON_BIN` 指定解释器。

## 启动应用

在当前目录启动：

```bash
python -m streamlit run knowledge_graph_rag.py
```

或从仓库根目录运行：

```bash
./finance-llm-agent-demos/scripts/run_13_agent.sh
```

启动脚本会优先使用：

```text
finance-llm-agent-demos/13-knowledge_graph_rag_citations/.venv/bin/python
```

如果没有 `.venv`，脚本会优先尝试 `python3.11`，再退回 `python3`。

如果依赖装在其他环境里：

```bash
PYTHON_BIN=/path/to/python ./finance-llm-agent-demos/scripts/run_13_agent.sh
```

## 使用流程

### 1. 配置连接

侧边栏默认配置为：

```text
Neo4j URI: bolt://localhost:7687
Neo4j 用户名: neo4j
Neo4j 密码: password
Ollama 模型: llama3.2
```

如果你用 Podman 默认配置，通常不用修改。

### 2. 添加文档

在「添加文档」页签中，可以选择内置样例：

- `AI 研究论文`
- `公司报告`

也可以粘贴自己的文档。点击「抽取并写入知识图谱」后，系统会：

1. 让 Ollama 模型抽取实体和关系。
2. 将实体写入 Neo4j 的 `Entity` 节点。
3. 将关系写入 `RELATES_TO` 边。
4. 展示抽取出的实体和关系。

### 3. 提问

在「提问」页签中输入问题，例如：

```text
GraphRAG 的关键概念是什么？是谁提出的？
```

系统会：

1. 在图谱中查找相关实体。
2. 从起点实体做两跳关系扩展。
3. 构造带来源编号的上下文。
4. 要求模型用 `[1]`、`[2]` 格式引用来源。
5. 展示回答、推理轨迹和引用详情。

### 4. 查看图谱

在「查看图谱」页签中，可以查看：

- 实体总数。
- 关系总数。
- 清空当前图谱。

## 核心代码解读

### 数据模型

`Entity` 表示实体：

```text
id, name, entity_type, description, source_doc, source_chunk
```

`Relationship` 表示实体关系：

```text
source, target, relation_type, description, source_doc
```

`Citation` 表示可验证引用：

```text
claim, source_document, source_text, confidence, reasoning_path
```

### KnowledgeGraphManager

`KnowledgeGraphManager` 封装 Neo4j 操作：

- `add_entity()`：写入实体节点。
- `add_relationship()`：写入实体关系。
- `semantic_search()`：用文本匹配查找起点实体。
- `find_related_entities()`：从起点实体做 N 跳扩展。
- `clear_graph()`：清空图谱。

### 实体和关系抽取

`extract_entities_with_llm()` 会把文档文本发给 Ollama，要求模型返回 JSON：

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

代码会把 JSON 转换成 `Entity` 和 `Relationship` 对象，再写入 Neo4j。

### 带引用回答

`generate_answer_with_citations()` 是核心流程：

1. `semantic_search()` 找到初始实体。
2. `find_related_entities()` 扩展相关实体。
3. 为每条上下文生成 `[1]`、`[2]` 这类来源编号。
4. 让模型回答时使用编号引用。
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

### 连接 Neo4j 失败

确认 Neo4j 已启动：

```bash
podman ps | grep neo4j
```

确认端口：

```text
7474: Neo4j Browser
7687: Bolt 连接
```

默认密码是 `password`。如果你换过密码，需要在侧边栏同步修改。

### Ollama 模型不可用

确认模型已拉取：

```bash
podman exec kg-rag-ollama ollama list
podman exec kg-rag-ollama ollama pull llama3.2
```

如果使用 Podman 容器，查看日志：

```bash
podman logs -f kg-rag-ollama
```

### 抽取出的实体为空

可能原因：

- Ollama 服务没启动。
- 模型还没拉取完成。
- 文档太短或结构不清晰。
- 模型没有返回合法 JSON。

可以先使用内置样例文档测试。

### 回答没有引用

可能原因：

- 图谱中没有相关实体。
- 回答模型没有按 `[1]`、`[2]` 格式输出引用。
- 上下文为空或相关性太弱。

可以先清空图谱，重新添加内置样例，再用默认问题测试。

## 安全边界

这个 demo 会把你粘贴的文本发给本地 Ollama 服务，但不会调用外部云模型。仍然需要注意：

- 不要粘贴未经授权的敏感文档。
- Neo4j 默认密码 `password` 只适合本地 demo。
- 生产环境不要暴露默认端口和默认密码。
- LLM 抽取的实体和关系需要人工复核。

## 扩展方向

- 增加 PDF / Markdown 文件上传。
- 使用 Neo4j 全文索引或向量索引替代简单文本匹配。
- 为关系增加置信度和来源片段。
- 将引用粒度从 entity chunk 提升到具体句子。
- 增加图可视化组件，显示节点和关系。
- 增加 Pydantic schema 校验 LLM 抽取结果。

本项目仅用于技术学习和原型验证，不构成投资、法律、审计或其他专业建议。
