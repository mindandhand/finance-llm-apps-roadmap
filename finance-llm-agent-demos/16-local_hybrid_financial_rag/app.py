import math
import os
import re
from collections import Counter
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
WORKSPACE_DIR = REPO_DIR.parent
for env_path in (APP_DIR / ".env", REPO_DIR / ".env", WORKSPACE_DIR / ".env"):
    load_dotenv(env_path)


def call_deepseek(prompt: str) -> str:
    """调用 DeepSeek，并要求模型只能使用检索到的证据回答。"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 DEEPSEEK_API_KEY。")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": os.getenv("DEEPSEEK_MODEL_ID", "deepseek-chat"),
            "messages": [
                {"role": "system", "content": "你是严谨的金融文档 RAG 助手。只基于给定片段回答。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 3000,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def read_file(uploaded) -> str:
    """读取上传的 PDF 或文本文件，统一返回纯文本。"""
    if uploaded.name.lower().endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(uploaded)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return uploaded.read().decode("utf-8", errors="ignore")


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\w\u4e00-\u9fff]+", text.lower())


def chunk_text(text: str, size: int = 900, overlap: int = 160) -> list[str]:
    """按字符切分文档，并保留相邻片段之间的少量重叠内容。"""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("切片参数必须满足 size > overlap >= 0。")

    clean = re.sub(r"\s+", " ", text).strip()
    chunks, start = [], 0
    while start < len(clean):
        chunks.append(clean[start : start + size])
        start += size - overlap
    return [chunk for chunk in chunks if chunk.strip()]


def score_chunks(query: str, chunks: list[str], top_k: int = 6) -> list[tuple[int, float, str]]:
    """用轻量 BM25 风格词频分数选择最相关的文档片段。"""
    q_terms = tokenize(query)
    if not q_terms:
        return []
    doc_tokens = [tokenize(chunk) for chunk in chunks]
    df = Counter(term for tokens in doc_tokens for term in set(tokens))
    n_docs = max(1, len(chunks))
    scored = []
    for idx, (chunk, tokens) in enumerate(zip(chunks, doc_tokens)):
        counts = Counter(tokens)
        bm25 = 0.0
        lexical = 0
        for term in q_terms:
            if counts[term]:
                lexical += counts[term]
                bm25 += counts[term] * math.log((n_docs + 1) / (df[term] + 0.5))
        length_penalty = 1 / math.sqrt(max(1, len(tokens)))
        scored.append((idx, bm25 + lexical * 0.3 + length_penalty, chunk))
    return [item for item in sorted(scored, key=lambda item: item[1], reverse=True) if item[1] > 0][:top_k]


st.set_page_config(page_title="本地混合金融 RAG", layout="wide")
st.title("本地混合金融 RAG")
st.caption("上传财报、公告或研报，使用本地关键词/BM25 检索，再由 DeepSeek 基于证据回答。")

uploaded = st.file_uploader("上传 PDF 或 TXT/MD 文件", type=["pdf", "txt", "md"])
question = st.text_input("问题", value="这份文档中最重要的经营风险是什么？请引用证据。")

if uploaded:
    text = read_file(uploaded)
    chunks = chunk_text(text)
    st.caption(f"已解析文本长度：{len(text)} 字符，切分片段：{len(chunks)}")
    if st.button("检索并回答", use_container_width=True):
        with st.spinner("正在检索相关片段并生成回答..."):
            try:
                hits = score_chunks(question, chunks)
                if not hits:
                    st.warning("没有找到包含问题关键词的证据片段，请换一种问法。")
                    st.stop()
                context = "\n\n".join(f"[片段 {idx}] {chunk}" for idx, _, chunk in hits)
                prompt = f"""
请只基于以下检索片段回答问题。若证据不足，请明确拒答并说明缺失信息。

问题：{question}

检索片段：
{context}

输出要求：
- 使用中文。
- 给出结论、证据、引用片段编号和不确定性。
- 不要使用片段外知识补充事实。
"""
                st.subheader("回答")
                st.markdown(call_deepseek(prompt))
                st.subheader("命中片段")
                for idx, score, chunk in hits:
                    st.markdown(f"**片段 {idx}，分数 {score:.3f}**")
                    st.write(chunk)
            except Exception as exc:
                st.error(f"回答失败：{exc}")
else:
    st.info("请上传一个财报、公告、研报或文本文件。")
