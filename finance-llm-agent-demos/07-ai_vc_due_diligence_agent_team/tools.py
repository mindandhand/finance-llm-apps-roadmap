"""本地尽调产物生成工具。"""

from __future__ import annotations

import html
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("VCDueDiligenceTeam")

OUTPUTS_DIR = Path(__file__).resolve().parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _parse_rates(rates: str, fallback: list[float]) -> list[float]:
    try:
        values = [float(item.strip()) for item in rates.split(",") if item.strip()]
        return values or fallback
    except ValueError:
        return fallback


def generate_financial_chart(
    company_name: str,
    current_arr: float = 1.0,
    bear_rates: str = "1.5,1.3,1.2,1.1,1.1",
    base_rates: str = "2.5,2.0,1.8,1.5,1.3",
    bull_rates: str = "4.0,3.0,2.3,1.9,1.6",
) -> dict:
    """生成 5 年 ARR 情景预测图，并保存到 outputs 目录。"""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        current_arr = max(float(current_arr), 0.01)
        bear = _parse_rates(bear_rates, [1.5, 1.3, 1.2, 1.1, 1.1])
        base = _parse_rates(base_rates, [2.5, 2.0, 1.8, 1.5, 1.3])
        bull = _parse_rates(bull_rates, [4.0, 3.0, 2.3, 1.9, 1.6])
        horizon = min(len(bear), len(base), len(bull), 5)
        bear, base, bull = bear[:horizon], base[:horizon], bull[:horizon]
        years = list(range(2026, 2026 + horizon + 1))

        def project(start: float, rates: list[float]) -> list[float]:
            values = [start]
            for rate in rates:
                values.append(values[-1] * rate)
            return values

        bear_arr = project(current_arr, bear)
        base_arr = project(current_arr, base)
        bull_arr = project(current_arr, bull)

        plt.style.use("seaborn-v0_8-whitegrid")
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(years, bear_arr, "o-", color="#c2410c", linewidth=2, label="保守情景")
        ax.plot(years, base_arr, "s-", color="#0f766e", linewidth=3, label="基准情景")
        ax.plot(years, bull_arr, "^-", color="#2563eb", linewidth=2, label="乐观情景")
        ax.fill_between(years, bear_arr, bull_arr, alpha=0.08, color="#0f766e")
        ax.set_title(f"{company_name} ARR 情景预测", fontsize=16, fontweight="bold")
        ax.set_xlabel("年份")
        ax.set_ylabel("ARR（百万美元）")
        ax.legend(loc="upper left")
        ax.grid(True, linestyle="--", alpha=0.5)
        for year, value in zip(years, base_arr):
            ax.annotate(f"${value:.1f}M", (year, value), textcoords="offset points", xytext=(0, 10), ha="center")
        plt.tight_layout()

        artifact_name = f"revenue_chart_{_timestamp()}.png"
        filepath = OUTPUTS_DIR / artifact_name
        plt.savefig(filepath, format="png", dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)

        return {
            "status": "success",
            "message": f"收入预测图已保存：{filepath}",
            "artifact": artifact_name,
            "path": str(filepath),
            "summary": {
                "第五年保守情景": f"${bear_arr[-1]:.1f}M",
                "第五年基准情景": f"${base_arr[-1]:.1f}M",
                "第五年乐观情景": f"${bull_arr[-1]:.1f}M",
            },
        }
    except Exception as exc:
        logger.exception("生成收入预测图失败")
        return {"status": "error", "message": str(exc)}


def generate_html_report(report_data: str, company_name: str = "目标公司") -> dict:
    """将投资备忘录保存为本地 HTML 报告。"""
    try:
        current_date = datetime.now().strftime("%Y-%m-%d")
        safe_company = html.escape(company_name)
        safe_report = html.escape(report_data).replace("\n", "<br>\n")
        html_content = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{safe_company} 投资尽调报告</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #172026; background: #f6f7f9; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 40px 28px; background: #ffffff; min-height: 100vh; }}
    h1 {{ color: #0f766e; margin-bottom: 6px; }}
    .meta {{ color: #667085; margin-bottom: 28px; }}
    .content {{ line-height: 1.72; font-size: 15px; }}
    @media print {{ body {{ background: #ffffff; }} main {{ padding: 24px; }} }}
  </style>
</head>
<body>
  <main>
    <h1>{safe_company} 投资尽调报告</h1>
    <div class="meta">生成日期：{current_date}</div>
    <section class="content">{safe_report}</section>
  </main>
</body>
</html>
"""
        artifact_name = f"investment_report_{_timestamp()}.html"
        filepath = OUTPUTS_DIR / artifact_name
        filepath.write_text(html_content, encoding="utf-8")
        return {
            "status": "success",
            "message": f"HTML 尽调报告已保存：{filepath}",
            "artifact": artifact_name,
            "path": str(filepath),
        }
    except Exception as exc:
        logger.exception("生成 HTML 报告失败")
        return {"status": "error", "message": str(exc)}


def generate_infographic(
    company_name: str,
    recommendation: str = "待定",
    market_size: str = "待确认",
    risk_score: str = "待评估",
    key_metrics: str = "公开数据有限",
) -> dict:
    """生成本地 SVG 摘要卡片，不依赖外部图片模型。"""
    try:
        safe_company = html.escape(company_name)
        safe_recommendation = html.escape(recommendation)
        safe_market_size = html.escape(market_size)
        safe_risk_score = html.escape(risk_score)
        safe_key_metrics = html.escape(key_metrics)
        svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" viewBox="0 0 1200 720">
  <rect width="1200" height="720" fill="#f7fafc"/>
  <rect x="64" y="56" width="1072" height="608" rx="8" fill="#ffffff" stroke="#d0d5dd"/>
  <text x="96" y="128" font-family="Arial, sans-serif" font-size="44" font-weight="700" fill="#0f766e">{safe_company}</text>
  <text x="96" y="172" font-family="Arial, sans-serif" font-size="22" fill="#475467">VC 投资尽调摘要</text>
  <rect x="96" y="230" width="300" height="150" rx="8" fill="#ecfdf3"/>
  <text x="124" y="282" font-family="Arial, sans-serif" font-size="20" fill="#344054">投资建议</text>
  <text x="124" y="336" font-family="Arial, sans-serif" font-size="36" font-weight="700" fill="#027a48">{safe_recommendation}</text>
  <rect x="450" y="230" width="300" height="150" rx="8" fill="#eff6ff"/>
  <text x="478" y="282" font-family="Arial, sans-serif" font-size="20" fill="#344054">市场规模</text>
  <text x="478" y="336" font-family="Arial, sans-serif" font-size="34" font-weight="700" fill="#175cd3">{safe_market_size}</text>
  <rect x="804" y="230" width="300" height="150" rx="8" fill="#fff7ed"/>
  <text x="832" y="282" font-family="Arial, sans-serif" font-size="20" fill="#344054">风险评分</text>
  <text x="832" y="336" font-family="Arial, sans-serif" font-size="36" font-weight="700" fill="#c2410c">{safe_risk_score}</text>
  <text x="96" y="458" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#172026">关键指标与判断</text>
  <foreignObject x="96" y="486" width="1008" height="120">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family: Arial, sans-serif; color:#344054; font-size:22px; line-height:1.5;">{safe_key_metrics}</div>
  </foreignObject>
</svg>
"""
        artifact_name = f"infographic_{_timestamp()}.svg"
        filepath = OUTPUTS_DIR / artifact_name
        filepath.write_text(svg_content, encoding="utf-8")
        return {
            "status": "success",
            "message": f"SVG 尽调摘要已保存：{filepath}",
            "artifact": artifact_name,
            "path": str(filepath),
        }
    except Exception as exc:
        logger.exception("生成 SVG 摘要失败")
        return {"status": "error", "message": str(exc)}
