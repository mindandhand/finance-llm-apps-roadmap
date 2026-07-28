import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st
from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from agno.tools.duckduckgo import DuckDuckGoTools
from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
SHARED_WORKSPACE_DIR = REPO_DIR.parent

for env_path in (
    APP_DIR / ".env",
    REPO_DIR / ".env",
    SHARED_WORKSPACE_DIR / ".env",
):
    load_dotenv(env_path)

model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat"))
base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")

st.set_page_config(
    page_title="人寿保险保额顾问",
    layout="centered",
)

st.title("人寿保险保额顾问")
st.caption(
    "使用 DeepSeek、DuckDuckGo 搜索和本地确定性计算，估算定期寿险保额并整理产品研究线索。"
)

with st.sidebar:
    st.header("模型配置")
    st.write("API Key 仅保存在当前本地 Streamlit 会话中。")
    deepseek_api_key = st.text_input(
        "DeepSeek API Key",
        value=deepseek_api_key or "",
        type="password",
        key="deepseek_api_key",
    )
    st.markdown("---")
    st.caption(
        "保额计算由本地 Python 函数完成；Agent 使用 DuckDuckGo 做产品和市场信息研究。"
    )

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

def safe_number(value: Any) -> float:
    """Best-effort conversion to float for agent outputs."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        if isinstance(value, str):
            stripped = value
            for token in [",", "$", "€", "£", "₹", "C$", "A$"]:
                stripped = stripped.replace(token, "")
            stripped = stripped.strip()
            try:
                return float(stripped)
            except ValueError:
                return 0.0
        return 0.0


def format_currency(amount: float, currency_code: str) -> str:
    symbol_map = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "CAD": "C$",
        "AUD": "A$",
        "INR": "₹",
    }
    code = (currency_code or "USD").upper()
    symbol = symbol_map.get(code, "")
    formatted = f"{amount:,.0f}"
    return f"{symbol}{formatted}" if symbol else f"{formatted} {code}"


def extract_json(payload: str) -> Optional[Dict[str, Any]]:
    if not payload:
        return None

    content = payload.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def parse_percentage(value: Any, fallback: float = 0.02) -> float:
    """Convert percentage-like values to decimal form (e.g., "2%" -> 0.02)."""
    if value is None:
        return fallback
    if isinstance(value, (int, float)):
        # assume already decimal if less than 1, otherwise treat as percentage value
        return float(value) if value < 1 else float(value) / 100
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "")
        try:
            numeric = float(cleaned)
            return numeric if numeric < 1 else numeric / 100
        except ValueError:
            return fallback
    return fallback


def compute_local_breakdown(profile: Dict[str, Any], real_rate: float) -> Dict[str, float]:
    """Replicate the coverage math locally so we can show it to the user."""
    income = safe_number(profile.get("annual_income"))
    years = max(0, int(profile.get("income_replacement_years", 0) or 0))
    total_debt = safe_number(profile.get("total_debt"))
    savings = safe_number(profile.get("available_savings"))
    existing_cover = safe_number(profile.get("existing_life_insurance"))

    if real_rate <= 0:
        discounted_income = income * years
        annuity_factor = years
    else:
        annuity_factor = (1 - (1 + real_rate) ** (-years)) / real_rate if years else 0
        discounted_income = income * annuity_factor

    assets_offset = savings + existing_cover
    recommended = max(0.0, discounted_income + total_debt - assets_offset)

    return {
        "income": income,
        "years": years,
        "real_rate": real_rate,
        "annuity_factor": annuity_factor,
        "discounted_income": discounted_income,
        "debt": total_debt,
        "assets_offset": -assets_offset,
        "recommended": recommended,
    }


@st.cache_resource(show_spinner=False)
def get_agent(deepseek_key: str) -> Optional[Agent]:
    if not deepseek_key:
        return None

    return Agent(
        name="人寿保险保额顾问",
        model=DeepSeek(
            id=model_id,
            api_key=deepseek_key,
            base_url=base_url,
        ),
        tools=[
            DuckDuckGoTools(),
        ],
        instructions=[
            "你提供审慎的人寿保险保额规划参考。所有内容必须使用中文。",
            "用户会提供客户画像 JSON 和本地 Python 已计算好的保额结果。不要重新发明计算公式。",
            "你可以使用 DuckDuckGo 搜索客户所在地的定期寿险产品、保险公司和购买注意事项。",
            "最终只能返回 JSON，不要包含 markdown、解释性前后缀或工具调用痕迹。",
            "JSON 顶层字段必须包含：coverage_amount, coverage_currency, breakdown, assumptions, recommendations, research_notes, timestamp。",
            "`coverage_amount` 必须使用本地计算结果中的 recommended 数值并取整。",
            "`coverage_currency` 使用客户画像中的 currency。",
            "`breakdown` 包含 income_replacement, debt_obligations, assets_offset, methodology。",
            "`assumptions` 包含 income_replacement_years, real_discount_rate, additional_notes。",
            "`recommendations` 最多 3 条，每条包含 name, summary, link, source；如果无法确认具体产品，给出机构或购买渠道研究线索并说明不确定性。",
            "`research_notes` 必须包含中文风险提示：本内容仅用于技术学习与规划参考，不构成投资、保险、税务或法律建议。",
        ],
        markdown=False,
    )


# -----------------------------------------------------------------------------
# User input form
# -----------------------------------------------------------------------------
st.subheader("填写基本信息")

with st.form("coverage_form"):
    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("年龄", min_value=18, max_value=85, value=35)
        annual_income = st.number_input(
            "年收入",
            min_value=0.0,
            value=85000.0,
            step=1000.0,
        )
        dependents = st.number_input(
            "需要供养的人数",
            min_value=0,
            max_value=10,
            value=2,
            step=1,
        )
        location = st.text_input(
            "国家或地区",
            value="United States",
            help="用于检索本地可选保险机构或产品线索。",
        )
    with col2:
        total_debt = st.number_input(
            "未偿债务总额（含房贷）",
            min_value=0.0,
            value=200000.0,
            step=5000.0,
        )
        savings = st.number_input(
            "可供家庭使用的储蓄和投资资产",
            min_value=0.0,
            value=50000.0,
            step=5000.0,
        )
        existing_cover = st.number_input(
            "已有寿险保额",
            min_value=0.0,
            value=100000.0,
            step=5000.0,
        )
        currency = st.selectbox(
            "币种",
            options=["USD", "CAD", "EUR", "GBP", "AUD", "INR"],
            index=0,
        )

    income_replacement_years = st.selectbox(
        "收入替代年限",
        options=[5, 10, 15],
        index=1,
        help="希望寿险赔付可以替代多少年的收入。",
    )

    submitted = st.form_submit_button("生成保额建议和产品线索")


def build_client_profile() -> Dict[str, Any]:
    return {
        "age": age,
        "annual_income": annual_income,
        "dependents": dependents,
        "location": location,
        "total_debt": total_debt,
        "available_savings": savings,
        "existing_life_insurance": existing_cover,
        "income_replacement_years": income_replacement_years,
        "currency": currency,
        "request_timestamp": datetime.utcnow().isoformat(),
    }


def render_recommendations(result: Dict[str, Any], profile: Dict[str, Any]) -> None:
    coverage_currency = result.get("coverage_currency", currency)
    coverage_amount = safe_number(result.get("coverage_amount", 0))

    st.subheader("建议保额")
    st.metric(
        label="建议总保额",
        value=format_currency(coverage_amount, coverage_currency),
    )

    assumptions = result.get("assumptions", {})
    real_rate = parse_percentage(assumptions.get("real_discount_rate", "2%"))
    local_breakdown = compute_local_breakdown(profile, real_rate)

    st.subheader("计算输入")
    st.table(
        {
            "项目": [
                "年收入",
                "收入替代年限",
                "未偿债务",
                "可用流动资产",
                "已有寿险保额",
                "实际折现率",
            ],
            "数值": [
                format_currency(local_breakdown["income"], coverage_currency),
                f"{local_breakdown['years']} 年",
                format_currency(local_breakdown["debt"], coverage_currency),
                format_currency(safe_number(profile.get("available_savings")), coverage_currency),
                format_currency(safe_number(profile.get("existing_life_insurance")), coverage_currency),
                f"{real_rate * 100:.2f}%",
            ],
        }
    )

    st.subheader("保额计算过程")
    step_rows = [
        ("年金折现系数", f"{local_breakdown['annuity_factor']:.3f}"),
        ("折现后的收入替代需求", format_currency(local_breakdown["discounted_income"], coverage_currency)),
        ("+ 未偿债务", format_currency(local_breakdown["debt"], coverage_currency)),
        ("- 可用资产和已有保额", format_currency(local_breakdown["assets_offset"], coverage_currency)),
        ("= 本地公式估算", format_currency(local_breakdown["recommended"], coverage_currency)),
    ]
    step_rows.append(("= Agent 输出保额", format_currency(coverage_amount, coverage_currency)))

    st.table({"步骤": [s for s, _ in step_rows], "金额": [a for _, a in step_rows]})

    breakdown = result.get("breakdown", {})
    with st.expander("保额如何计算", expanded=True):
        st.markdown(
            f"- 收入替代需求：{format_currency(safe_number(breakdown.get('income_replacement')), coverage_currency)}"
        )
        st.markdown(
            f"- 债务覆盖需求：{format_currency(safe_number(breakdown.get('debt_obligations')), coverage_currency)}"
        )
        assets_offset = safe_number(breakdown.get("assets_offset"))
        st.markdown(
            f"- 可用资产和已有保额抵扣：{format_currency(assets_offset, coverage_currency)}"
        )
        methodology = breakdown.get("methodology")
        if methodology:
            st.caption(methodology)

    recommendations = result.get("recommendations", [])
    if recommendations:
        st.subheader("定期寿险产品或渠道线索")
        for idx, option in enumerate(recommendations, start=1):
            with st.container():
                name = option.get("name", "未命名产品或机构")
                summary = option.get("summary", "未提供摘要。")
                st.markdown(f"**{idx}. {name}** — {summary}")
                link = option.get("link")
                if link:
                    st.markdown(f"[查看详情]({link})")
                source = option.get("source")
                if source:
                    st.caption(f"来源：{source}")
                st.markdown("---")

    with st.expander("模型假设"):
        st.write(
            {
                "收入替代年限": assumptions.get(
                    "income_replacement_years", income_replacement_years
                ),
                "实际折现率": assumptions.get("real_discount_rate", "2%"),
                "补充说明": assumptions.get("additional_notes", ""),
            }
        )

    if result.get("research_notes"):
        st.caption(result["research_notes"])
    if result.get("timestamp"):
        st.caption(f"生成时间：{result['timestamp']}")

    with st.expander("Agent 返回 JSON"):
        st.json(result)


if submitted:
    if not deepseek_api_key:
        st.error("请先在侧边栏填写 DeepSeek API Key。")
        st.stop()

    advisor_agent = get_agent(deepseek_api_key)
    if not advisor_agent:
        st.error("无法初始化保额顾问，请检查 DeepSeek API Key。")
        st.stop()

    client_profile = build_client_profile()
    local_breakdown = compute_local_breakdown(client_profile, real_rate=0.02)
    local_result = {
        "coverage_amount": int(local_breakdown["recommended"]),
        "coverage_currency": client_profile["currency"],
        "breakdown": {
            "income_replacement": local_breakdown["discounted_income"],
            "debt_obligations": local_breakdown["debt"],
            "assets_offset": local_breakdown["assets_offset"],
            "methodology": "本地 Python 使用收入替代现值 + 未偿债务 - 可用资产 - 已有寿险保额进行估算，实际折现率默认 2%。",
        },
        "assumptions": {
            "income_replacement_years": client_profile["income_replacement_years"],
            "real_discount_rate": "2%",
            "additional_notes": "该估算未纳入税务、通胀路径、社保、雇主福利、配偶收入变化等复杂因素。",
        },
    }
    user_prompt = (
        "你会收到客户画像 JSON 和本地 Python 已计算出的保额结果 JSON。"
        "请使用 DuckDuckGo 搜索客户所在地的定期寿险产品、保险机构或购买注意事项，"
        "并严格按照系统指令返回中文 JSON。\n"
        f"客户画像 JSON：{json.dumps(client_profile, ensure_ascii=False)}\n"
        f"本地计算结果 JSON：{json.dumps(local_result, ensure_ascii=False)}"
    )

    with st.spinner("正在计算保额并研究产品线索..."):
        response = advisor_agent.run(user_prompt, stream=False)

    parsed = extract_json(response.content if response else "")
    if not parsed:
        st.error("Agent 返回了非预期格式。可展开查看原始输出。")
        with st.expander("原始 Agent 输出"):
            st.write(response.content if response else "<empty>")
    else:
        render_recommendations(parsed, client_profile)
        with st.expander("Agent 调试输出"):
            st.write(response.content)

st.divider()
st.caption(
    "本项目仅用于技术学习与原型验证，不构成投资、保险、税务或法律建议。"
    "请向持牌专业人士核验保额和产品信息，并以保险公司正式披露为准。"
)
