import os
import re
import time
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv
from pypdf import PdfReader
from rank_bm25 import BM25Okapi


APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
WORKSPACE_DIR = REPO_DIR.parent
for env_path in (APP_DIR / ".env", REPO_DIR / ".env", WORKSPACE_DIR / ".env"):
    load_dotenv(env_path)


def split_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    chunks = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(normalized[start:end])
        if end == len(normalized):
            break
        start = end - overlap
    return chunks


def read_uploaded_file(uploaded_file: Any) -> str:
    if uploaded_file.name.lower().endswith(".pdf"):
        reader = PdfReader(uploaded_file)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return uploaded_file.getvalue().decode("utf-8", errors="ignore")


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]", text.lower())
    return [word for word in words if len(word.strip()) > 0]


def retrieve(query: str, documents: list[dict[str, str]], limit: int = 5) -> list[dict[str, str]]:
    if not documents:
        return []
    tokenized_documents = [tokenize(document["content"]) for document in documents]
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    scores = BM25Okapi(tokenized_documents).get_scores(query_tokens)
    ranked_indexes = sorted(range(len(documents)), key=lambda index: scores[index], reverse=True)
    return [documents[index] for index in ranked_indexes[:limit] if scores[index] > 0]


def call_deepseek(question: str, context: str) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 DEEPSEEK_API_KEY，请在 .env 中配置。")

    model = os.getenv("DEEPSEEK_MODEL_ID", "deepseek-chat")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    prompt = f"""请用中文回答用户问题。

你是一个严谨的本地文档问答助手。只能把文档上下文作为事实依据；如果上下文没有答案，请明确说“文档中没有足够信息”，并给出需要补充的资料。区分文档事实和你的推断，不要编造数字、日期或来源。

文档上下文：
{context or "没有检索到相关文档。"}

用户问题：
{question}
"""
    request_body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    retryable_statuses = {429, 500, 502, 503, 504}
    last_error = "未知错误"

    for attempt in range(3):
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=request_body,
                timeout=60,
            )
        except requests.RequestException as exc:
            last_error = str(exc)
            if attempt == 2:
                break
            time.sleep(2**attempt)
            continue

        if response.status_code < 400:
            data = response.json()
            return data["choices"][0]["message"]["content"]

        last_error = response.text[:300]
        if response.status_code not in retryable_statuses or attempt == 2:
            break
        retry_after = response.headers.get("Retry-After")
        try:
            delay = min(float(retry_after), 10) if retry_after else 2**attempt
        except ValueError:
            delay = 2**attempt
        time.sleep(delay)

    if "service_unavailable_error" in last_error or "Service is too busy" in last_error:
        raise RuntimeError("DeepSeek 当前服务繁忙，已自动重试 3 次，请稍后再次提交问题。")
    raise RuntimeError(f"DeepSeek 请求失败：{last_error}")


st.set_page_config(page_title="本地 DeepSeek RAG", page_icon="📚", layout="wide")
st.title("本地 DeepSeek RAG 文档问答")
st.caption("本地读取文档并检索相关片段，再使用 DeepSeek 生成中文回答。")

if "documents" not in st.session_state:
    st.session_state.documents = []
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("文档库")
    uploaded_files = st.file_uploader(
        "上传 PDF、TXT 或 Markdown",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
    )
    if st.button("导入文档", use_container_width=True):
        imported = 0
        for uploaded_file in uploaded_files or []:
            try:
                text = read_uploaded_file(uploaded_file)
                chunks = split_text(text)
                st.session_state.documents = [
                    document
                    for document in st.session_state.documents
                    if document["source"] != uploaded_file.name
                ]
                st.session_state.documents.extend(
                    {"source": uploaded_file.name, "content": chunk} for chunk in chunks
                )
                imported += 1
            except Exception as exc:
                st.error(f"读取 {uploaded_file.name} 失败：{exc}")
        if imported:
            st.success(f"已导入 {imported} 个文件，共 {len(st.session_state.documents)} 个文本片段。")

    if st.button("清空文档和对话", use_container_width=True):
        st.session_state.documents = []
        st.session_state.messages = []
        st.rerun()

    if os.getenv("DEEPSEEK_API_KEY"):
        st.success("已检测到 DeepSeek API Key")
    else:
        st.warning("未检测到 DEEPSEEK_API_KEY")
    st.caption("检索在本地内存中完成，不需要 Qdrant、Exa 或 Ollama。")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("例如：这份材料中提到的主要风险是什么？")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    matches = retrieve(question, st.session_state.documents)
    context = "\n\n".join(f"[{item['source']}]\n{item['content']}" for item in matches)
    with st.chat_message("assistant"):
        with st.spinner("正在检索本地文档并请求 DeepSeek..."):
            try:
                answer = call_deepseek(question, context)
                st.markdown(answer)
                if matches:
                    with st.expander("查看引用片段"):
                        for item in matches:
                            st.markdown(f"**{item['source']}**\n\n{item['content']}")
                else:
                    st.info("未检索到匹配文档，回答应视为信息不足提示。")
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as exc:
                if matches:
                    fallback = (
                        "DeepSeek 当前暂时不可用，无法生成总结。下面是本地检索到的相关文档片段，"
                        "请稍后重新提交问题以获得完整中文回答。"
                    )
                    st.warning(fallback)
                    with st.expander("查看本地检索结果"):
                        for item in matches:
                            st.markdown(f"**{item['source']}**\n\n{item['content']}")
                    st.session_state.messages.append({"role": "assistant", "content": fallback})
                else:
                    error_message = f"回答失败：{exc}"
                    st.error(error_message)
                    st.session_state.messages.append({"role": "assistant", "content": error_message})
