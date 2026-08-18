import os

import streamlit as st

from dashboard import build_query, fetch_rows, normalize_rows


st.set_page_config(page_title="组合持仓分析", layout="wide")
st.title("组合持仓分析")

portfolio = st.selectbox(
    "组合",
    ["全部", "Alpha Growth", "Alpha Balanced", "Beta Reserve"],
)

try:
    raw_rows = fetch_rows(
        f"http://127.0.0.1:{os.getenv('CUBE_PORT', '4000')}",
        build_query(None if portfolio == "全部" else portfolio),
    )
    rows = normalize_rows(raw_rows)
except Exception as error:
    st.error(f"Cube 查询失败：{error}")
elif not rows:
    st.info("当前筛选条件没有数据。")
else:
    st.metric("总市值", f"{sum(row['持仓市值'] for row in rows):,.2f}")
    st.dataframe(rows, use_container_width=True)
    chart_data = {row["资产类别"]: float(row["持仓市值"]) for row in rows}
    st.bar_chart(chart_data)
