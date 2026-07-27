"""带类型校验、引用和拒答机制的 RAG Streamlit 界面。"""

from __future__ import annotations

import asyncio
import os
from pathlib import PurePath

import streamlit as st
from dotenv import load_dotenv

from agent import (
    Answer,
    RagDependencies,
    answer_question,
    default_deepseek_model_name,
)
from rag import (
    HashingEmbeddingBackend,
    InMemoryVectorStore,
    fetch_url_text,
    ingest_pdf,
)


load_dotenv()

st.set_page_config(
    page_title="类型化 Agentic RAG",
    page_icon="📎",
    layout="wide",
)


def run_async(awaitable):
    """在 Streamlit 的同步脚本里执行一个异步操作。"""
    return asyncio.run(awaitable)


def selected_embedding_backend(mode: str):
    return HashingEmbeddingBackend()


async def build_knowledge_base(files, docs_url: str, embedding_mode: str):
    """根据当前选择的资料重新构建一个内存向量库。"""
    store = InMemoryVectorStore(selected_embedding_backend(embedding_mode))
    indexed = []

    for uploaded_file in files:
        source = PurePath(uploaded_file.name).name
        chunk_count = await ingest_pdf(store, source, uploaded_file.getvalue())
        indexed.append((source, chunk_count))

    if docs_url:
        text = fetch_url_text(docs_url)
        chunk_count = await store.add_document(docs_url, text)
        indexed.append((docs_url, chunk_count))

    return store, indexed


def render_answer(answer: Answer) -> None:
    """渲染有依据的回答，或展示清晰的拒答状态。"""
    if answer.answered:
        st.markdown(answer.text)
        st.progress(answer.confidence)
        st.caption(f"回答置信度：{answer.confidence:.0%}")
        st.markdown("**引用依据**")
        for citation in answer.citations:
            label = f"{citation.source} | {citation.chunk_id}"
            with st.expander(label):
                st.code(citation.quoted_span, language=None)
    else:
        st.warning(answer.text, icon="🛑")
        st.progress(answer.confidence)
        st.caption(f"最佳检索相似度：{answer.confidence:.0%}")


if "rag_store" not in st.session_state:
    st.session_state.rag_store = None
if "indexed_sources" not in st.session_state:
    st.session_state.indexed_sources = []
if "answer_history" not in st.session_state:
    st.session_state.answer_history = []


with st.sidebar:
    st.header("模型设置")
    configured_model = os.getenv("RAG_MODEL", "").strip()
    if os.getenv("DEEPSEEK_API_KEY"):
        st.success("已加载 DEEPSEEK_API_KEY", icon="🔑")
    else:
        st.warning("提问前请在 .env 中配置 DEEPSEEK_API_KEY。")

    model_name = st.text_input(
        "Pydantic AI 模型",
        value=configured_model or default_deepseek_model_name(),
        help="默认使用 deepseek:deepseek-chat，也可以填其他 Pydantic AI 模型字符串。",
    )
    embedding_mode = st.selectbox(
        "Embedding 模式",
        ["本地哈希"],
        help="DeepSeek 只负责生成回答；本 demo 的检索向量使用本地词法哈希。",
    )
    min_relevance = st.slider(
        "拒答阈值",
        min_value=0.05,
        max_value=0.60,
        value=0.20,
        step=0.01,
        help="低于该检索分数的问题会在调用 LLM 前直接拒答。",
    )

    st.divider()
    if st.session_state.rag_store is not None:
        store = st.session_state.rag_store
        st.metric("已索引分块", store.count)
        st.caption(f"Embedding：{store.embedding_backend.name}")
        if st.button("清空知识库", use_container_width=True):
            st.session_state.rag_store = None
            st.session_state.indexed_sources = []
            st.session_state.answer_history = []
            st.rerun()


st.title("📎 类型化 Agentic RAG")
st.write(
    "上传证据资料后提问，系统会返回经过类型校验、带原文引用的答案。"
    "如果检索证据不足，应用会拒答，而不是让模型猜测。"
)

source_column, status_column = st.columns([3, 2])
with source_column:
    st.subheader("1. 添加资料")
    uploaded_files = st.file_uploader(
        "PDF 文档",
        type=["pdf"],
        accept_multiple_files=True,
    )
    docs_url = st.text_input(
        "文档 URL",
        placeholder="https://example.com/docs",
        help="可选。支持 2 MB 以内的 HTML 和纯文本页面。",
    ).strip()
    build_clicked = st.button(
        "构建知识库",
        type="primary",
        disabled=not uploaded_files and not docs_url,
    )

with status_column:
    st.subheader("索引状态")
    if st.session_state.indexed_sources:
        for source, chunks in st.session_state.indexed_sources:
            st.success(f"{source}: {chunks} 个分块", icon="✅")
    else:
        st.info("请至少添加一个 PDF 或文档 URL。")

if build_clicked:
    with st.spinner("正在抽取文本、分块并生成 Embeddings..."):
        try:
            store, indexed_sources = run_async(
                build_knowledge_base(uploaded_files or [], docs_url, embedding_mode)
            )
        except Exception as exc:
            st.error(f"无法构建知识库：{exc}")
        else:
            st.session_state.rag_store = store
            st.session_state.indexed_sources = indexed_sources
            st.session_state.answer_history = []
            st.rerun()

st.divider()
st.subheader("2. 向已索引资料提问")

for item in st.session_state.answer_history:
    with st.chat_message("user"):
        st.markdown(item["question"])
    with st.chat_message("assistant"):
        render_answer(Answer.model_validate(item["answer"]))

question = st.chat_input(
    "针对已索引资料提问",
    disabled=st.session_state.rag_store is None,
)
if question:
    if not os.getenv("DEEPSEEK_API_KEY"):
        st.error("提问前请先配置 DEEPSEEK_API_KEY。")
    else:
        deps = RagDependencies(
            store=st.session_state.rag_store,
            min_relevance=min_relevance,
            top_k=4,
        )
        with st.spinner("正在检索证据并校验回答..."):
            try:
                selected_model = model_name.strip() or default_deepseek_model_name()
                answer = run_async(
                    answer_question(question, deps, model=selected_model)
                )
            except Exception as exc:
                st.error(f"Agent 无法回答：{exc}")
            else:
                st.session_state.answer_history.append(
                    {"question": question, "answer": answer.model_dump()}
                )
                st.rerun()
