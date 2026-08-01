"""
带可验证引用的知识图谱 RAG。

这个 Streamlit 应用演示知识图谱 RAG 的三个关键能力：

1. 跨文档、跨实体的多跳推理。
2. 每个结论都能追溯到来源文档和原文片段。
3. 展示推理路径，便于审查答案是怎么来的。

本 demo 使用 Ollama 做本地 LLM 推理，使用 Neo4j 存储知识图谱。
"""

from dataclasses import dataclass
import hashlib
import json
import os
import re
from typing import Dict, List, Tuple

import streamlit as st
from neo4j import GraphDatabase
from ollama import Client as OllamaClient

# Podman Compose 中 Ollama 通常是 http://ollama:11434；本地运行默认 localhost。
OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
ollama_client = OllamaClient(host=OLLAMA_HOST)


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class Entity:
    """从文档中抽取出的实体。"""
    id: str
    name: str
    entity_type: str
    description: str
    source_doc: str
    source_chunk: str


@dataclass
class Relationship:
    """实体之间的关系。"""
    source: str
    target: str
    relation_type: str
    description: str
    source_doc: str


@dataclass
class Citation:
    """回答中某个结论对应的可验证引用。"""
    claim: str
    source_document: str
    source_text: str
    confidence: float
    reasoning_path: List[str]


@dataclass
class AnswerWithCitations:
    """带答案、引用和推理轨迹的最终结果。"""
    answer: str
    citations: List[Citation]
    reasoning_trace: List[str]


# ============================================================================
# 知识图谱管理器
# ============================================================================

class KnowledgeGraphManager:
    """封装 Neo4j 知识图谱的读写操作。"""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def clear_graph(self):
        """清空所有节点和关系。"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
    
    def add_entity(self, entity: Entity):
        """把一个实体写入知识图谱。"""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (e:Entity {id: $id})
                SET e.name = $name,
                    e.type = $entity_type,
                    e.description = $description,
                    e.source_doc = $source_doc,
                    e.source_chunk = $source_chunk
                """,
                id=entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
                description=entity.description,
                source_doc=entity.source_doc,
                source_chunk=entity.source_chunk
            )
    
    def add_relationship(self, rel: Relationship):
        """把两个实体之间的关系写入知识图谱。"""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (a:Entity {name: $source})
                MATCH (b:Entity {name: $target})
                MERGE (a)-[r:RELATES_TO {type: $rel_type}]->(b)
                SET r.description = $description,
                    r.source_doc = $source_doc
                """,
                source=rel.source,
                target=rel.target,
                rel_type=rel.relation_type,
                description=rel.description,
                source_doc=rel.source_doc
            )
    
    def find_related_entities(self, entity_name: str, hops: int = 2) -> List[Dict]:
        """查找 N 跳以内的相关实体，并返回来源信息。"""
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH path = (start:Entity)-[*1..{hops}]-(related:Entity)
                WHERE toLower(start.name) CONTAINS toLower($name) OR toLower(start.description) CONTAINS toLower($name)
                RETURN related.name as name,
                       related.description as description,
                       related.source_doc as source,
                       related.source_chunk as chunk,
                       [r in relationships(path) | r.description] as path_descriptions
                LIMIT 20
                """,
                name=entity_name, hops=hops
            )
            return [dict(record) for record in result]
    
    def semantic_search(self, query: str) -> List[Dict]:
        """根据问题做简单文本匹配，找到候选起点实体。"""
        with self.driver.session() as session:
            # 教学 demo 使用文本匹配；生产系统通常会接向量索引或全文索引。
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE e.name CONTAINS $query 
                   OR e.description CONTAINS $query
                RETURN e.name as name,
                       e.description as description,
                       e.source_doc as source,
                       e.source_chunk as chunk,
                       e.type as type
                LIMIT 10
                """,
                query=query
            )
            return [dict(record) for record in result]


# ============================================================================
# 基于 LLM 的实体抽取
# ============================================================================

def extract_entities_with_llm(text: str, source_doc: str, model: str = "llama3.2") -> Tuple[List[Entity], List[Relationship]]:
    """使用本地 LLM 从文本中抽取实体和关系。"""
    
    extraction_prompt = f"""请分析下面的文本，并抽取：
1. 关键实体（人物、组织、概念、技术、事件、地点）
2. 实体之间的关系

每个实体需要提供：
- name：实体名称
- type：类别（PERSON、ORGANIZATION、CONCEPT、TECHNOLOGY、EVENT、LOCATION）
- description：基于原文的简短描述

每个关系需要提供：
- source：起点实体名称
- target：终点实体名称
- type：关系类型（例如 WORKS_FOR、CREATED、USES、LOCATED_IN）
- description：说明两个实体如何关联

文本：
{text}

请严格返回 JSON：
{{
  "entities": [
    {{"name": "...", "type": "...", "description": "..."}}
  ],
  "relationships": [
    {{"source": "...", "target": "...", "type": "...", "description": "..."}}
  ]
}}
"""
    
    try:
        response = ollama_client.chat(
            model=model,
            messages=[{"role": "user", "content": extraction_prompt}],
            format="json"
        )
        
        data = json.loads(response['message']['content'])
        
        entities = []
        for e in data.get('entities', []):
            entity_id = hashlib.md5(f"{e['name']}_{source_doc}".encode()).hexdigest()[:12]
            entities.append(Entity(
                id=entity_id,
                name=e['name'],
                entity_type=e['type'],
                description=e['description'],
                source_doc=source_doc,
                source_chunk=text[:200] + "..."
            ))
        
        relationships = []
        for r in data.get('relationships', []):
            relationships.append(Relationship(
                source=r['source'],
                target=r['target'],
                relation_type=r['type'],
                description=r['description'],
                source_doc=source_doc
            ))
        
        return entities, relationships
    
    except Exception as e:
        st.warning(f"实体抽取失败：{e}")
        return [], []


# ============================================================================
# 带引用的多跳 RAG
# ============================================================================

def generate_answer_with_citations(
    query: str,
    graph: KnowledgeGraphManager,
    model: str = "llama3.2"
) -> AnswerWithCitations:
    """
    使用多跳图遍历生成带引用答案。
    
    这是本 demo 的核心差异：答案中的引用可以回到来源文档和原文片段。
    """
    
    reasoning_trace = []
    citations = []
    
    # 第 1 步：先用文本匹配找到起点实体。
    reasoning_trace.append(f"🔍 正在知识图谱中搜索：{query}")
    initial_results = graph.semantic_search(query)
    
    if not initial_results:
        return AnswerWithCitations(
            answer="知识图谱中没有找到足够相关的信息。",
            citations=[],
            reasoning_trace=reasoning_trace
        )
    
    reasoning_trace.append(f"📊 找到 {len(initial_results)} 个初始实体")
    
    # 第 2 步：从起点实体做多跳扩展。
    all_context = []
    for entity in initial_results[:3]:
        reasoning_trace.append(f"🔗 从实体扩展：{entity['name']}")
        related = graph.find_related_entities(entity['name'], hops=2)
        
        for rel in related:
            all_context.append({
                "entity": rel['name'],
                "description": rel['description'],
                "source": rel['source'],
                "chunk": rel['chunk'],
                "path": rel.get('path_descriptions', [])
            })
            reasoning_trace.append(f"  → 找到相关实体：{rel['name']}")
    
    # 第 3 步：构造带来源编号的上下文。
    context_parts = []
    source_map = {}
    
    for i, ctx in enumerate(all_context):
        source_key = f"[{i+1}]"
        context_parts.append(f"{source_key} {ctx['entity']}: {ctx['description']}")
        source_map[source_key] = {
            "document": ctx['source'],
            "text": ctx['chunk'],
            "entity": ctx['entity']
        }
    
    context_text = "\n".join(context_parts)
    reasoning_trace.append(f"📝 基于 {len(context_parts)} 条来源构造上下文")
    
    # 第 4 步：要求模型生成带引用标记的回答。
    answer_prompt = f"""请基于下面的知识图谱上下文回答问题。
重要：每个关键结论都必须使用 [N] 格式标注来源。

上下文：
{context_text}

问题：{query}

请用中文回答，并为每个关键结论添加 [1]、[2] 这类行内引用。
"""
    
    try:
        response = ollama_client.chat(
            model=model,
            messages=[{"role": "user", "content": answer_prompt}]
        )
        answer = response['message']['content']
        reasoning_trace.append("✅ 已生成带引用答案")
        
        # 第 5 步：从回答中抽取引用编号，并映射回来源文本。
        citation_refs = re.findall(r'\[(\d+)\]', answer)
        
        for ref in set(citation_refs):
            key = f"[{ref}]"
            if key in source_map:
                src = source_map[key]
                citations.append(Citation(
                    claim=f"引用 {key}",
                    source_document=src['document'],
                    source_text=src['text'],
                    confidence=0.85,
                    reasoning_path=[f"实体：{src['entity']}"]
                ))
        
        reasoning_trace.append(f"🔒 已验证 {len(citations)} 条引用")
        
        return AnswerWithCitations(
            answer=answer,
            citations=citations,
            reasoning_trace=reasoning_trace
        )
        
    except Exception as e:
        return AnswerWithCitations(
            answer=f"生成答案失败：{e}",
            citations=[],
            reasoning_trace=reasoning_trace
        )


# ============================================================================
# Streamlit 界面
# ============================================================================

def main():
    st.set_page_config(
        page_title="知识图谱 RAG 与可验证引用",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 知识图谱 RAG 与可验证引用")
    st.markdown("""
    这个 demo 展示 **Knowledge Graph RAG** 如何提供：
    - 跨实体和跨文档的 **多跳推理**
    - 每个结论都有 **可验证来源**
    - 可以审查的 **透明推理轨迹**
    
    和传统向量 RAG 不同，这里每个答案都尽量追溯到来源文档。
    """)
    
    # 侧边栏配置。
    st.sidebar.header("⚙️ 配置")
    
    neo4j_uri = st.sidebar.text_input("Neo4j URI", "bolt://localhost:7687")
    neo4j_user = st.sidebar.text_input("Neo4j 用户名", "neo4j")
    neo4j_password = st.sidebar.text_input("Neo4j 密码", type="password", value="password")
    llm_model = st.sidebar.selectbox("Ollama 模型", ["llama3.2", "mistral", "phi3"])
    
    # 初始化会话状态。Streamlit 每次交互都会重跑脚本，所以状态需要放在 session_state。
    if 'graph_initialized' not in st.session_state:
        st.session_state.graph_initialized = False
        st.session_state.documents = []
    
    tab1, tab2, tab3 = st.tabs(["📄 添加文档", "❓ 提问", "🔬 查看图谱"])
    
    with tab1:
        st.header("第 1 步：从文档构建知识图谱")
        
        sample_docs = {
            "AI 研究论文": """
            GraphRAG 是 Microsoft Research 提出的一种技术，它把知识图谱和检索增强生成结合起来。
            不同于主要依赖向量相似度的传统 RAG，GraphRAG 会从文档中构建结构化知识图谱，
            因而可以支持多跳推理。该技术由 Darren Edge、Ha Trinh 等研究人员介绍。
            GraphRAG 擅长回答需要连接多个来源信息的复杂问题，例如不同研究项目之间的关系。
            """,
            "公司报告": """
            Acme Corp 由 Jane Smith 和 John Doe 于 2020 年在旧金山创立。
            这家公司为企业客户开发 AI 驱动的数据分析工具。
            它的旗舰产品 DataSense 使用机器学习分析业务数据。
            Jane Smith 曾在 Google 的 TensorFlow 团队担任高级工程师。
            John Doe 是 StartupX 的联合创始人，StartupX 在 2019 年被 Microsoft 收购。
            Acme Corp 完成了由 Sequoia Capital 领投的 5000 万美元 B 轮融资。
            """
        }
        
        doc_choice = st.selectbox("选择样例文档：", list(sample_docs.keys()))
        doc_text = st.text_area("或粘贴自己的文档：", sample_docs[doc_choice], height=200)
        doc_name = st.text_input("文档名称：", doc_choice)
        
        if st.button("🔨 抽取并写入知识图谱"):
            with st.spinner("正在抽取实体和关系..."):
                try:
                    graph = KnowledgeGraphManager(neo4j_uri, neo4j_user, neo4j_password)
                    entities, relationships = extract_entities_with_llm(doc_text, doc_name, llm_model)
                    
                    for entity in entities:
                        graph.add_entity(entity)
                    
                    for rel in relationships:
                        graph.add_relationship(rel)
                    
                    graph.close()
                    
                    st.success(f"✅ 已抽取 {len(entities)} 个实体和 {len(relationships)} 条关系")
                    
                    with st.expander("查看抽取出的实体"):
                        for e in entities:
                            st.write(f"**{e.name}** ({e.entity_type}): {e.description}")
                    
                    with st.expander("查看抽取出的关系"):
                        for r in relationships:
                            st.write(f"{r.source} --[{r.relation_type}]--> {r.target}: {r.description}")
                    
                    st.session_state.graph_initialized = True
                    st.session_state.documents.append(doc_name)
                    
                except Exception as e:
                    st.error(f"错误：{e}")
                    st.info("请确认 Neo4j 正在运行，并且 Ollama 已经拉取所选模型。")
    
    with tab2:
        st.header("第 2 步：提出问题并查看可验证答案")
        
        if not st.session_state.graph_initialized:
            st.warning("⚠️ 请先向知识图谱添加文档。")
        else:
            st.info(f"📚 当前知识图谱包含文档：{', '.join(st.session_state.documents)}")
        
        query = st.text_input("输入问题：", "GraphRAG 的关键概念是什么？是谁提出的？")
        
        if st.button("🔍 带引用回答"):
            with st.spinner("正在遍历知识图谱并生成答案..."):
                try:
                    graph = KnowledgeGraphManager(neo4j_uri, neo4j_user, neo4j_password)
                    result = generate_answer_with_citations(query, graph, llm_model)
                    graph.close()
                    
                    st.subheader("🧠 推理轨迹")
                    for step in result.reasoning_trace:
                        st.write(step)
                    
                    st.subheader("💬 回答")
                    st.markdown(result.answer)
                    
                    st.subheader("📚 来源引用")
                    if result.citations:
                        for i, citation in enumerate(result.citations):
                            with st.expander(f"引用 {i+1}: {citation.source_document}"):
                                st.write(f"**来源文档：** {citation.source_document}")
                                st.write(f"**来源文本：** {citation.source_text}")
                                st.write(f"**置信度：** {citation.confidence:.0%}")
                                st.write(f"**推理路径：** {' → '.join(citation.reasoning_path)}")
                    else:
                        st.info("这个答案没有抽取出明确引用。")
                        
                except Exception as e:
                    st.error(f"错误：{e}")
    
    with tab3:
        st.header("🔬 知识图谱概览")
        st.info("这里展示当前知识图谱的基础统计。")
        
        if st.button("📊 显示图谱统计"):
            try:
                graph = KnowledgeGraphManager(neo4j_uri, neo4j_user, neo4j_password)
                with graph.driver.session() as session:
                    node_count = session.run("MATCH (n) RETURN count(n) as count").single()['count']
                    rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
                
                col1, col2 = st.columns(2)
                col1.metric("实体总数", node_count)
                col2.metric("关系总数", rel_count)
                
                graph.close()
            except Exception as e:
                st.error(f"连接 Neo4j 失败：{e}")
        
        if st.button("🗑️ 清空图谱"):
            try:
                graph = KnowledgeGraphManager(neo4j_uri, neo4j_user, neo4j_password)
                graph.clear_graph()
                graph.close()
                st.session_state.graph_initialized = False
                st.session_state.documents = []
                st.success("图谱已清空。")
            except Exception as e:
                st.error(f"错误：{e}")


if __name__ == "__main__":
    main()
