import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
for env_path in (APP_DIR / ".env", APP_DIR.parent / ".env", APP_DIR.parent.parent / ".env"):
    load_dotenv(env_path)


def deepseek(prompt: str) -> str:
    """调用 DeepSeek 生成理赔文本交接包。"""
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
                {
                    "role": "system",
                    "content": "你是严谨的保险理赔文本整理助手，不做最终赔付决定。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 3000,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("DeepSeek 返回格式不符合 chat completions 规范。") from exc


st.set_page_config(page_title="保险理赔文本 Agent 团队", layout="wide")
st.title("保险理赔文本 Agent 团队")
claim = st.text_area("事故/损失描述", value="昨晚暴雨后地下室进水，地板和部分家具受损，已经拍照，暂未联系维修。", height=180)
policy = st.text_input("险种", value="家庭财产保险")

if st.button("生成理赔交接包", use_container_width=True, type="primary"):
    if not claim.strip():
        st.error("请填写事故或损失描述。")
        st.stop()
    if not policy.strip():
        st.error("请填写险种。")
        st.stop()

    st.caption("请先脱敏姓名、电话、地址、保单号和身份证件信息。")
    with st.spinner("正在抽取字段、检查缺失材料和风险信号..."):
        try:
            # 输出面向理赔员交接，不直接给出是否赔付的结论。
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
