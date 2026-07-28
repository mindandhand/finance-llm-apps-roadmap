import json
import os
import re
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
for env_path in (APP_DIR / ".env", APP_DIR.parent / ".env", APP_DIR.parent.parent / ".env"):
    load_dotenv(env_path)


def deepseek(prompt: str) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 DEEPSEEK_API_KEY。")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": os.getenv("DEEPSEEK_MODEL_ID", "deepseek-chat"), "messages": [{"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 3000},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


st.set_page_config(page_title="保险理赔文本 Agent 团队", layout="wide")
st.title("保险理赔文本 Agent 团队")
claim = st.text_area("事故/损失描述", value="昨晚暴雨后地下室进水，地板和部分家具受损，已经拍照，暂未联系维修。", height=180)
policy = st.text_input("险种", value="家庭财产保险")

if st.button("生成理赔交接包", use_container_width=True):
    with st.spinner("正在抽取字段、检查缺失材料和风险信号..."):
        try:
            prompt = f"""
请作为保险理赔文本 Agent 团队，基于以下描述生成理赔员交接包。
险种：{policy}
描述：{claim}

输出中文 Markdown，包含：
1. 已抽取字段表
2. 缺失信息
3. 需要补充的证据材料
4. 风险或人工升级信号
5. 下一步话术
6. 免责声明：不承诺赔付，最终以保单和理赔审核为准
"""
            st.markdown(deepseek(prompt))
        except Exception as exc:
            st.error(f"生成失败：{exc}")
else:
    st.info("输入事故描述后生成理赔交接包。")
