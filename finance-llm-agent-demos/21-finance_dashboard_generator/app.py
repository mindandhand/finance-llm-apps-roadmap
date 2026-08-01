from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="金融仪表盘生成器", layout="wide")
st.title("金融仪表盘生成器")
st.caption("模板驱动生成本地 HTML 金融仪表盘，不执行任意代码，不依赖沙箱服务。")

title = st.text_input("仪表盘标题", value="投资组合风险监控")
metrics = st.text_area("核心指标，每行一个，格式：名称=数值", value="组合收益率=12.4%\n最大回撤=-8.1%\n现金占比=18%\n高风险事件=3", height=140)
notes = st.text_area("备注", value="本周重点关注财报季、利率预期和行业监管事件。", height=120)

if st.button("生成 HTML 仪表盘", use_container_width=True):
    rows = []
    for line in metrics.splitlines():
        if "=" in line:
            name, value = line.split("=", 1)
            rows.append((name.strip(), value.strip()))
    df = pd.DataFrame(rows, columns=["指标", "数值"])
    cards = "\n".join(f"<div class='card'><span>{name}</span><strong>{value}</strong></div>" for name, value in rows)
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:40px;background:#f6f7f9;color:#172026}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px}}.card{{background:white;border:1px solid #d0d5dd;border-radius:8px;padding:18px}}.card span{{color:#667085}}.card strong{{display:block;font-size:28px;margin-top:8px;color:#0f766e}}section{{background:white;border:1px solid #d0d5dd;border-radius:8px;padding:20px;margin-top:18px}}</style>
</head><body><h1>{title}</h1><div class="grid">{cards}</div><section><h2>备注</h2><p>{notes}</p></section></body></html>"""
    path = OUTPUT_DIR / "finance_dashboard.html"
    path.write_text(html, encoding="utf-8")
    st.success(f"已生成：{path}")
    st.dataframe(df, use_container_width=True)
    components.html(html, height=460, scrolling=True)
else:
    st.info("填写指标后生成本地 HTML 仪表盘。")
