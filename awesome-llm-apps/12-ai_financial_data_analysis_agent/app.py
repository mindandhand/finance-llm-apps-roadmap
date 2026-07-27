"""
AI 金融数据分析 Agent。

这个应用的核心流程是：

1. 用户上传 CSV 或 Excel。
2. Pandas 读取成 DataFrame。
3. DeepSeek 根据字段结构和样例数据生成只读 DuckDB SQL。
4. Python 先校验 SQL 只允许 SELECT，再交给 DuckDB 本地执行。
5. DeepSeek 基于真实查询结果生成中文解释。

这里的安全边界很重要：LLM 只负责生成查询计划和解释结果，
真正的数据读取和 SQL 执行都在本地受控代码里完成。
"""
import json
import os
import re
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
WORKSPACE_DIR = REPO_DIR.parent

# 依次加载当前项目、awesome-llm-apps 根目录、仓库根目录的 .env。
# 这样可以给单个 demo 单独配置，也可以复用全局 DeepSeek 配置。
for env_path in (APP_DIR / ".env", REPO_DIR / ".env", WORKSPACE_DIR / ".env"):
    load_dotenv(env_path)


def ask_deepseek(prompt: str, max_tokens: int = 2048) -> str:
    """调用 DeepSeek chat completions 接口并返回模型文本。"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 DEEPSEEK_API_KEY。请先配置 .env。")

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": os.getenv("DEEPSEEK_MODEL_ID", "deepseek-chat"),
            "messages": [
                {
                    "role": "system",
                    "content": "你是金融数据分析助手。只输出用户要求的格式，不要编造数据。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def parse_json(text: str) -> dict[str, Any]:
    """从模型输出中提取 JSON 对象。

    DeepSeek 有时会把 JSON 包在 Markdown code fence 里。这里先去掉
    ```json，再截取第一个 `{` 到最后一个 `}`，避免自然语言前后缀影响解析。
    """
    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        (text or "").strip(),
        flags=re.I | re.S,
    )
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def load_table(uploaded_file) -> pd.DataFrame:
    """读取用户上传的 CSV 或 Excel 文件。"""
    if uploaded_file.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded_file)
    return pd.read_excel(uploaded_file)


def safe_sql(sql: str) -> str:
    """校验 LLM 生成的 SQL，只允许只读 SELECT。"""
    sql = sql.strip().rstrip(";")
    if not re.match(r"(?is)^select\b", sql):
        raise ValueError("只允许执行 SELECT 查询。")
    blocked = r"\b(insert|update|delete|drop|alter|create|copy|attach|detach|pragma)\b"
    if re.search(blocked, sql, flags=re.I):
        raise ValueError("SQL 包含不允许的写入或管理语句。")
    return sql


def dataframe_schema(df: pd.DataFrame) -> str:
    """把 DataFrame 字段和 dtype 转成给模型看的简洁 schema。"""
    return "\n".join(f"- {col}: {df[col].dtype}" for col in df.columns)


def build_sql_prompt(question: str, df: pd.DataFrame) -> str:
    """构造让 DeepSeek 生成只读 SQL 的提示词。"""
    schema = dataframe_schema(df)
    sample = df.head(8).to_csv(index=False)
    return f"""
表名固定为 data。
请根据用户问题生成只读 DuckDB SQL，并返回严格 JSON：
{{"sql":"SELECT ...", "reason":"为什么这样查询"}}

用户问题：{question}
字段结构：
{schema}

样例数据：
{sample}

要求：
- 只能生成 SELECT。
- 字段名如有空格或中文，请用双引号引用。
- 不要使用不存在的字段。
"""


def execute_query(df: pd.DataFrame, sql: str) -> pd.DataFrame:
    """在本地 DuckDB 中执行已校验的只读 SQL。"""
    con = duckdb.connect()
    try:
        con.register("data", df)
        return con.execute(sql).df()
    finally:
        con.close()


def build_explain_prompt(question: str, sql: str, result: pd.DataFrame) -> str:
    """构造让 DeepSeek 解释查询结果的提示词。"""
    result_sample = result.head(30).to_csv(index=False)
    return f"""
请用中文解释下面的金融数据查询结果，包含关键发现、异常点、可能原因和下一步分析建议。
用户问题：{question}
SQL：{sql}
结果：
{result_sample}
"""


st.set_page_config(page_title="AI 金融数据分析 Agent", layout="wide")
st.title("AI 金融数据分析 Agent")
st.caption("上传 CSV/Excel，用自然语言分析财务、交易、经营或投研数据。")

uploaded = st.file_uploader("上传 CSV 或 Excel 文件", type=["csv", "xlsx", "xls"])
question = st.text_input("想问这个数据什么？", value="按类别汇总金额，并找出占比最高的前 5 项。")

if uploaded:
    df = load_table(uploaded)
    st.subheader("数据预览")
    st.dataframe(df.head(30), use_container_width=True)
    st.caption(f"行数：{len(df)}，列数：{len(df.columns)}")

    if st.button("生成分析", use_container_width=True):
        with st.spinner("正在生成 SQL、执行查询并解释结果..."):
            try:
                # 第一步：让模型根据 schema 和样例数据生成查询计划。
                plan = parse_json(
                    ask_deepseek(build_sql_prompt(question, df), max_tokens=1200)
                )
                sql = safe_sql(str(plan.get("sql", "")))

                # 第二步：本地执行 SQL。模型不能直接读文件，也不能绕过 safe_sql。
                result = execute_query(df, sql)

                st.subheader("SQL")
                st.code(sql, language="sql")
                st.subheader("查询结果")
                st.dataframe(result, use_container_width=True)

                # 第三步：只把真实查询结果发回模型，让它写中文解释。
                explain_prompt = build_explain_prompt(question, sql, result)
                st.subheader("中文解释")
                st.markdown(ask_deepseek(explain_prompt, max_tokens=2000))
            except Exception as exc:
                st.error(f"分析失败：{exc}")
else:
    st.info("请先上传一个 CSV 或 Excel 文件。")
