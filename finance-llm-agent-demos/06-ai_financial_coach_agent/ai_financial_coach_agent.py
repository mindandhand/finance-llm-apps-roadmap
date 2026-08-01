import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional, Any
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import json
import logging
from pydantic import BaseModel, Field
import csv
from io import StringIO

from agno.agent import Agent
from agno.models.deepseek import DeepSeek

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent
SHARED_WORKSPACE_DIR = REPO_DIR.parent

for env_path in (
    APP_DIR / ".env",
    REPO_DIR / ".env",
    SHARED_WORKSPACE_DIR / ".env",
):
    load_dotenv(env_path)

# Pydantic 输出结构模型
class SpendingCategory(BaseModel):
    category: str = Field(..., description="支出类别名称")
    amount: float = Field(..., description="该类别支出金额")
    percentage: Optional[float] = Field(None, description="占总支出的比例")

class SpendingRecommendation(BaseModel):
    category: str = Field(..., description="建议对应类别")
    recommendation: str = Field(..., description="建议内容")
    potential_savings: Optional[float] = Field(None, description="预计每月节省金额")

class BudgetAnalysis(BaseModel):
    total_expenses: float = Field(..., description="月度总支出")
    monthly_income: Optional[float] = Field(None, description="月收入")
    spending_categories: List[SpendingCategory] = Field(..., description="按类别拆分的支出")
    recommendations: List[SpendingRecommendation] = Field(..., description="支出优化建议")

class EmergencyFund(BaseModel):
    recommended_amount: float = Field(..., description="建议应急金规模")
    current_amount: Optional[float] = Field(None, description="当前应急金金额")
    current_status: str = Field(..., description="应急金状态评估")

class SavingsRecommendation(BaseModel):
    category: str = Field(..., description="储蓄类别")
    amount: float = Field(..., description="建议每月金额")
    rationale: Optional[str] = Field(None, description="建议理由")

class AutomationTechnique(BaseModel):
    name: str = Field(..., description="自动化方法名称")
    description: str = Field(..., description="实施说明")

class SavingsStrategy(BaseModel):
    emergency_fund: EmergencyFund = Field(..., description="应急金建议")
    recommendations: List[SavingsRecommendation] = Field(..., description="储蓄分配建议")
    automation_techniques: Optional[List[AutomationTechnique]] = Field(None, description="自动化储蓄方法")

class Debt(BaseModel):
    name: str = Field(..., description="债务名称")
    amount: float = Field(..., description="当前余额")
    interest_rate: float = Field(..., description="年利率百分比")
    min_payment: Optional[float] = Field(None, description="最低月还款")

class PayoffPlan(BaseModel):
    total_interest: float = Field(..., description="总利息支出")
    months_to_payoff: int = Field(..., description="预计还清月份")
    monthly_payment: Optional[float] = Field(None, description="建议月还款额")

class PayoffPlans(BaseModel):
    avalanche: PayoffPlan = Field(..., description="优先偿还最高利率的方法")
    snowball: PayoffPlan = Field(..., description="优先偿还最小余额的方法")

class DebtRecommendation(BaseModel):
    title: str = Field(..., description="建议标题")
    description: str = Field(..., description="建议内容")
    impact: Optional[str] = Field(None, description="预期影响")

class DebtReduction(BaseModel):
    total_debt: float = Field(..., description="债务总额")
    debts: List[Debt] = Field(..., description="债务列表")
    payoff_plans: PayoffPlans = Field(..., description="还债策略")
    recommendations: Optional[List[DebtRecommendation]] = Field(None, description="债务优化建议")

model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat"))
base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")

def parse_json_safely(data: str, default_value: Any = None) -> Any:
    """安全解析 JSON，失败时返回默认值。"""
    if not data:
        return default_value
    if isinstance(data, str):
        content = data.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            data = "\n".join(lines).strip()
    try:
        return json.loads(data) if isinstance(data, str) else data
    except json.JSONDecodeError:
        return default_value

class FinanceAdvisorSystem:
    def __init__(self, api_key: str):
        model = DeepSeek(id=model_id, api_key=api_key, base_url=base_url)
        
        self.budget_analysis_agent = Agent(
            name="预算分析 Agent",
            model=model,
            instructions=[
                "你是预算分析 Agent，负责审查用户的交易、收入和支出。",
                "所有输出字段内容必须使用中文。",
                "只返回 JSON，不要返回 markdown 或解释性前后缀。",
                "JSON 字段必须包含 total_expenses, monthly_income, spending_categories, recommendations。",
                "spending_categories 是对象数组，每项包含 category, amount, percentage。",
                "recommendations 是对象数组，每项包含 category, recommendation, potential_savings。",
                "建议至少 3 条，并尽量量化潜在节省金额。",
            ],
            markdown=False,
        )
        
        self.savings_strategy_agent = Agent(
            name="储蓄策略 Agent",
            model=model,
            instructions=[
                "你是储蓄策略 Agent，负责制定个性化储蓄计划。",
                "必须基于用户数据和预算分析结果生成建议。",
                "所有输出字段内容必须使用中文。",
                "只返回 JSON，不要返回 markdown 或解释性前后缀。",
                "JSON 字段必须包含 emergency_fund, recommendations, automation_techniques。",
                "emergency_fund 包含 recommended_amount, current_amount, current_status。",
                "recommendations 是对象数组，每项包含 category, amount, rationale。",
                "automation_techniques 是对象数组，每项包含 name, description。",
            ],
            markdown=False,
        )
        
        self.debt_reduction_agent = Agent(
            name="债务优化 Agent",
            model=model,
            instructions=[
                "你是债务优化 Agent，负责制定债务偿还策略。",
                "必须基于用户债务、预算分析和储蓄策略生成建议。",
                "所有输出字段内容必须使用中文。",
                "只返回 JSON，不要返回 markdown 或解释性前后缀。",
                "JSON 字段必须包含 total_debt, debts, payoff_plans, recommendations。",
                "payoff_plans 必须包含 avalanche 和 snowball。",
                "每个 payoff plan 包含 total_interest, months_to_payoff, monthly_payment。",
                "recommendations 是对象数组，每项包含 title, description, impact。",
            ],
            markdown=False,
        )

    async def analyze_finances(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            default_results = self._create_default_results(financial_data)
            financial_json = json.dumps(financial_data, ensure_ascii=False)

            budget_response = self.budget_analysis_agent.run(
                f"请分析以下财务数据并返回预算分析 JSON：\n{financial_json}",
                stream=False,
            )
            budget_analysis = parse_json_safely(
                budget_response.content if budget_response else "",
                default_results["budget_analysis"],
            )

            savings_response = self.savings_strategy_agent.run(
                "请基于以下财务数据和预算分析返回储蓄策略 JSON：\n"
                f"财务数据：{financial_json}\n"
                f"预算分析：{json.dumps(budget_analysis, ensure_ascii=False)}",
                stream=False,
            )
            savings_strategy = parse_json_safely(
                savings_response.content if savings_response else "",
                default_results["savings_strategy"],
            )

            debt_response = self.debt_reduction_agent.run(
                "请基于以下财务数据、预算分析和储蓄策略返回债务优化 JSON：\n"
                f"财务数据：{financial_json}\n"
                f"预算分析：{json.dumps(budget_analysis, ensure_ascii=False)}\n"
                f"储蓄策略：{json.dumps(savings_strategy, ensure_ascii=False)}",
                stream=False,
            )
            debt_reduction = parse_json_safely(
                debt_response.content if debt_response else "",
                default_results["debt_reduction"],
            )

            return {
                "budget_analysis": budget_analysis,
                "savings_strategy": savings_strategy,
                "debt_reduction": debt_reduction,
            }
        except Exception as e:
            logger.exception(f"财务分析过程中发生错误：{str(e)}")
            raise

    def _create_default_results(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        monthly_income = financial_data.get("monthly_income", 0)
        expenses = financial_data.get("manual_expenses", {})
        
        # 手动支出可能为空。
        if expenses is None:
            expenses = {}
        
        if not expenses and financial_data.get("transactions"):
            expenses = {}
            for transaction in financial_data["transactions"]:
                category = transaction.get("Category", "未分类")
                amount = transaction.get("Amount", 0)
                expenses[category] = expenses.get(category, 0) + amount
        
        total_expenses = sum(expenses.values())
        
        return {
            "budget_analysis": {
                "total_expenses": total_expenses,
                "monthly_income": monthly_income,
                "spending_categories": [
                    {"category": cat, "amount": amt, "percentage": (amt / total_expenses * 100) if total_expenses > 0 else 0}
                    for cat, amt in expenses.items()
                ],
                "recommendations": [
                    {"category": "综合", "recommendation": "建议优先复盘高频支出，并为可压缩类别设置月度上限。", "potential_savings": total_expenses * 0.1}
                ]
            },
            "savings_strategy": {
                "emergency_fund": {
                    "recommended_amount": total_expenses * 6,
                    "current_amount": 0,
                    "current_status": "尚未建立"
                },
                "recommendations": [
                    {"category": "应急金", "amount": total_expenses * 0.1, "rationale": "先建立 3 到 6 个月支出的现金缓冲。"},
                    {"category": "长期储蓄", "amount": monthly_income * 0.15, "rationale": "为养老、教育或长期目标持续积累。"}
                ],
                "automation_techniques": [
                    {"name": "发薪日自动转账", "description": "工资到账后自动转入储蓄账户，减少手动决策。"}
                ]
            },
            "debt_reduction": {
                "total_debt": sum(debt.get("amount", 0) for debt in financial_data.get("debts", [])),
                "debts": financial_data.get("debts", []),
                "payoff_plans": {
                    "avalanche": {
                        "total_interest": sum(debt.get("amount", 0) for debt in financial_data.get("debts", [])) * 0.2,
                        "months_to_payoff": 24,
                        "monthly_payment": sum(debt.get("amount", 0) for debt in financial_data.get("debts", [])) / 24
                    },
                    "snowball": {
                        "total_interest": sum(debt.get("amount", 0) for debt in financial_data.get("debts", [])) * 0.25,
                        "months_to_payoff": 24,
                        "monthly_payment": sum(debt.get("amount", 0) for debt in financial_data.get("debts", [])) / 24
                    }
                },
                "recommendations": [
                    {"title": "提高月还款额", "description": "在保留必要现金流后，将可用结余优先用于高利率债务。", "impact": "可减少总利息支出并缩短还清周期。"}
                ]
            }
        }

def display_budget_analysis(analysis: Dict[str, Any]):
    if isinstance(analysis, str):
        try:
            analysis = json.loads(analysis)
        except json.JSONDecodeError:
            st.error("无法解析预算分析结果")
            return
    
    if not isinstance(analysis, dict):
        st.error("预算分析格式无效")
        return
    
    if "spending_categories" in analysis:
        st.subheader("按类别支出")
        fig = px.pie(
            values=[cat["amount"] for cat in analysis["spending_categories"]],
            names=[cat["category"] for cat in analysis["spending_categories"]],
            title="支出结构"
        )
        st.plotly_chart(fig)
    
    if "total_expenses" in analysis:
        st.subheader("收入与支出")
        income = analysis.get("monthly_income", 0)
        expenses = analysis["total_expenses"]
        surplus_deficit = income - expenses
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=["收入", "支出"], 
                            y=[income, expenses],
                            marker_color=["green", "red"]))
        fig.update_layout(title="月收入与月支出")
        st.plotly_chart(fig)
        
        st.metric("月度结余/缺口", 
                  f"${surplus_deficit:.2f}", 
                  delta=f"{surplus_deficit:.2f}")
    
    if "recommendations" in analysis:
        st.subheader("支出优化建议")
        for rec in analysis["recommendations"]:
            st.markdown(f"**{rec['category']}**: {rec['recommendation']}")
            if "potential_savings" in rec:
                st.metric("预计每月可节省", f"${rec['potential_savings']:.2f}")

def display_savings_strategy(strategy: Dict[str, Any]):
    if isinstance(strategy, str):
        try:
            strategy = json.loads(strategy)
        except json.JSONDecodeError:
            st.error("无法解析储蓄策略结果")
            return
    
    if not isinstance(strategy, dict):
        st.error("储蓄策略格式无效")
        return
    
    st.subheader("储蓄建议")
    
    if "emergency_fund" in strategy:
        ef = strategy["emergency_fund"]
        st.markdown("### 应急金")
        st.markdown(f"**建议规模**：${ef['recommended_amount']:.2f}")
        st.markdown(f"**当前状态**：{ef['current_status']}")
        
        if "current_amount" in ef and "recommended_amount" in ef:
            progress = ef["current_amount"] / ef["recommended_amount"]
            st.progress(min(progress, 1.0))
            st.markdown(f"${ef['current_amount']:.2f} / ${ef['recommended_amount']:.2f}")
    
    if "recommendations" in strategy:
        st.markdown("### 建议储蓄分配")
        for rec in strategy["recommendations"]:
            st.markdown(f"**{rec['category']}**：每月 ${rec['amount']:.2f}")
            st.markdown(f"_{rec['rationale']}_")
    
    if "automation_techniques" in strategy:
        st.markdown("### 自动化储蓄方法")
        for technique in strategy["automation_techniques"]:
            st.markdown(f"**{technique['name']}**: {technique['description']}")

def display_debt_reduction(plan: Dict[str, Any]):
    if isinstance(plan, str):
        try:
            plan = json.loads(plan)
        except json.JSONDecodeError:
            st.error("无法解析债务优化结果")
            return
    
    if not isinstance(plan, dict):
        st.error("债务优化格式无效")
        return
    
    if "total_debt" in plan:
        st.metric("债务总额", f"${plan['total_debt']:.2f}")
    
    if "debts" in plan:
        st.subheader("债务明细")
        debt_df = pd.DataFrame(plan["debts"])
        st.dataframe(debt_df)
        
        fig = px.bar(debt_df, x="name", y="amount", color="interest_rate",
                    labels={"name": "债务", "amount": "金额", "interest_rate": "利率（%）"},
                    title="债务结构")
        st.plotly_chart(fig)
    
    if "payoff_plans" in plan:
        st.subheader("还债计划")
        tabs = st.tabs(["雪崩法", "雪球法", "对比"])
        
        with tabs[0]:
            st.markdown("### 雪崩法（优先偿还最高利率）")
            if "avalanche" in plan["payoff_plans"]:
                avalanche = plan["payoff_plans"]["avalanche"]
                st.markdown(f"**总利息**：${avalanche['total_interest']:.2f}")
                st.markdown(f"**还清时间**：{avalanche['months_to_payoff']} 个月")
                
                if "monthly_payment" in avalanche:
                    st.markdown(f"**建议月还款**：${avalanche['monthly_payment']:.2f}")
        
        with tabs[1]:
            st.markdown("### 雪球法（优先偿还最小余额）")
            if "snowball" in plan["payoff_plans"]:
                snowball = plan["payoff_plans"]["snowball"]
                st.markdown(f"**总利息**：${snowball['total_interest']:.2f}")
                st.markdown(f"**还清时间**：{snowball['months_to_payoff']} 个月")
                
                if "monthly_payment" in snowball:
                    st.markdown(f"**建议月还款**：${snowball['monthly_payment']:.2f}")
        
        with tabs[2]:
            st.markdown("### 方法对比")
            if "avalanche" in plan["payoff_plans"] and "snowball" in plan["payoff_plans"]:
                avalanche = plan["payoff_plans"]["avalanche"]
                snowball = plan["payoff_plans"]["snowball"]
                
                comparison_data = {
                    "方法": ["雪崩法", "雪球法"],
                    "总利息": [avalanche["total_interest"], snowball["total_interest"]],
                    "还清月份": [avalanche["months_to_payoff"], snowball["months_to_payoff"]]
                }
                comparison_df = pd.DataFrame(comparison_data)
                
                st.dataframe(comparison_df)
                
                fig = go.Figure(data=[
                    go.Bar(name="总利息", x=comparison_df["方法"], y=comparison_df["总利息"]),
                    go.Bar(name="还清月份", x=comparison_df["方法"], y=comparison_df["还清月份"])
                ])
                fig.update_layout(barmode='group', title="还债方法对比")
                st.plotly_chart(fig)
    
    if "recommendations" in plan:
        st.subheader("债务优化建议")
        for rec in plan["recommendations"]:
            st.markdown(f"**{rec['title']}**: {rec['description']}")
            if "impact" in rec:
                st.markdown(f"_影响：{rec['impact']}_")

def parse_csv_transactions(file_content) -> List[Dict[str, Any]]:
    """将 CSV 文件内容解析为交易列表。"""
    try:
        # 读取 CSV 内容。
        df = pd.read_csv(StringIO(file_content.decode('utf-8')))
        
        # 校验必要列。
        required_columns = ['Date', 'Category', 'Amount']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"CSV 缺少必要列：{', '.join(missing_columns)}")
        
        # 将日期统一为 YYYY-MM-DD 字符串。
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
        
        # 将金额转为数字，并兼容货币符号和逗号。
        df['Amount'] = df['Amount'].replace(r'[$,]', '', regex=True).astype(float)
        
        # 按类别汇总。
        category_totals = df.groupby('Category')['Amount'].sum().reset_index()
        
        # 转为字典列表。
        transactions = df.to_dict('records')
        
        return {
            'transactions': transactions,
            'category_totals': category_totals.to_dict('records')
        }
    except Exception as e:
        raise ValueError(f"解析 CSV 文件失败：{str(e)}")

def validate_csv_format(file) -> bool:
    """校验 CSV 文件格式和内容。"""
    try:
        content = file.read().decode('utf-8')
        dialect = csv.Sniffer().sniff(content)
        has_header = csv.Sniffer().has_header(content)
        file.seek(0)
        
        if not has_header:
            return False, "CSV 文件必须包含表头"
            
        df = pd.read_csv(StringIO(content))
        required_columns = ['Date', 'Category', 'Amount']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return False, f"CSV 缺少必要列：{', '.join(missing_columns)}"
            
        # 校验日期格式。
        try:
            pd.to_datetime(df['Date'])
        except:
            return False, "Date 列的日期格式无效"
            
        # 校验金额格式。
        try:
            df['Amount'].replace(r'[$,]', '', regex=True).astype(float)
        except:
            return False, "Amount 列的金额格式无效"
            
        return True, "CSV 格式有效"
    except Exception as e:
        return False, f"CSV 格式无效：{str(e)}"

def display_csv_preview(df: pd.DataFrame):
    """展示 CSV 数据预览和基础统计。"""
    st.subheader("CSV 数据预览")
    
    # 展示基础统计。
    total_transactions = len(df)
    total_amount = df['Amount'].sum()
    
    # 日期范围展示。
    df_dates = pd.to_datetime(df['Date'])
    date_range = f"{df_dates.min().strftime('%Y-%m-%d')} 至 {df_dates.max().strftime('%Y-%m-%d')}"
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("交易笔数", total_transactions)
    with col2:
        st.metric("总金额", f"${total_amount:,.2f}")
    with col3:
        st.metric("日期范围", date_range)
    
    # 展示类别汇总。
    st.subheader("按类别支出")
    category_totals = df.groupby('Category')['Amount'].agg(['sum', 'count']).reset_index()
    category_totals.columns = ['类别', '总金额', '交易笔数']
    st.dataframe(category_totals)
    
    # 展示交易样例。
    st.subheader("交易样例")
    st.dataframe(df.head())

def main():
    st.set_page_config(
        page_title="AI 财务教练",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 侧边栏展示 API Key 配置说明和 CSV 模板。
    with st.sidebar:
        st.title("配置与模板")
        st.info("请确认 `.env` 中已经配置 DeepSeek API Key：\n```\nDEEPSEEK_API_KEY=你的API Key\n```")
        st.caption("本应用使用 Agno 和 DeepSeek 的三 Agent 顺序流程生成个人财务分析。")
        
        st.divider()
        
        # CSV 模板下载。
        st.subheader("CSV 模板")
        st.markdown("""
        下载交易流水模板，字段要求：
- Date：日期，格式 YYYY-MM-DD
- Category：支出类别
- Amount：金额，数字
        """)
        
        # 示例 CSV 内容。
        sample_csv = """Date,Category,Amount
2024-01-01,Housing,1200.00
2024-01-02,Food,150.50
2024-01-03,Transportation,45.00"""
        
        st.download_button(
            label="下载 CSV 模板",
            data=sample_csv,
            file_name="expense_template.csv",
            mime="text/csv"
        )
    
    if not deepseek_api_key:
        st.error("未找到 DEEPSEEK_API_KEY。请在 `.env` 文件中添加该变量。")
        return
    
    # Main content
    st.title("AI 财务教练")
    st.caption("基于 Agno 和 DeepSeek 的多 Agent 财务分析应用")
    st.info("这个工具会分析你的收入、支出和债务，并生成预算、储蓄和还债建议。")
    st.divider()
    
    # Create tabs for different sections
    input_tab, about_tab = st.tabs(["财务信息", "关于"])
    
    with input_tab:
        st.header("填写财务信息")
        st.caption("输入数据仅用于当前本地会话分析。")
        
        # Income and Dependants section in a container
        with st.container():
            st.subheader("收入与家庭")
            income_col, dependants_col = st.columns([2, 1])
            with income_col:
                monthly_income = st.number_input(
                    "月收入",
                    min_value=0.0,
                    step=100.0,
                    value=25000.0,
                    key="income",
                    help="填写税后月收入"
                )
            with dependants_col:
                dependants = st.number_input(
                    "供养人数",
                    min_value=0,
                    step=1,
                    value=2,
                    key="dependants",
                    help="包括家庭中需要你供养的人"
                )
        
        st.divider()
        
        # Expenses section
        with st.container():
            st.subheader("支出")
            expense_option = st.radio(
                "你想如何录入支出？",
                ("上传 CSV 流水", "手动录入"),
                key="expense_option",
                horizontal=True
            )
            
            transaction_file = None
            manual_expenses = {}
            use_manual_expenses = False
            transactions_df = None

            if expense_option == "上传 CSV 流水":
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown("""
                    #### 上传交易流水
                    CSV 文件需要包含以下列：
                    - Date：日期，格式 YYYY-MM-DD
                    - Category：支出类别
                    - Amount：金额
                    """)
                    
                    transaction_file = st.file_uploader(
                        "选择 CSV 文件",
                        type=["csv"],
                        key="transaction_file",
                        help="上传包含交易记录的 CSV 文件"
                    )
                
                if transaction_file is not None:
                    # 校验 CSV 格式。
                    is_valid, message = validate_csv_format(transaction_file)
                    
                    if is_valid:
                        try:
                            # 解析 CSV 内容。
                            transaction_file.seek(0)
                            file_content = transaction_file.read()
                            parsed_data = parse_csv_transactions(file_content)
                            
                            # 构造 DataFrame。
                            transactions_df = pd.DataFrame(parsed_data['transactions'])
                            
                            # 展示预览。
                            display_csv_preview(transactions_df)
                            
                            st.success("交易文件已上传并通过校验。")
                        except Exception as e:
                            st.error(f"处理 CSV 文件失败：{str(e)}")
                            transactions_df = None
                    else:
                        st.error(message)
                        transactions_df = None
            else:
                use_manual_expenses = True
                st.markdown("#### 按类别填写月度支出")
                
                # 定义支出类别。
                categories = [
                    ("住房", "住房"),
                    ("水电燃气", "水电燃气"),
                    ("餐饮", "餐饮"),
                    ("交通", "交通"),
                    ("医疗", "医疗"),
                    ("娱乐", "娱乐"),
                    ("个人消费", "个人消费"),
                    ("储蓄", "储蓄"),
                    ("其他", "其他")
                ]
                default_expenses = {
                    "住房": 6000.0,
                    "水电燃气": 800.0,
                    "餐饮": 4500.0,
                    "交通": 1200.0,
                    "医疗": 600.0,
                    "娱乐": 1000.0,
                    "个人消费": 1800.0,
                    "储蓄": 4000.0,
                    "其他": 900.0,
                }
                
                # 使用三列提高录入效率。
                col1, col2, col3 = st.columns(3)
                cols = [col1, col2, col3]
                
                # 将类别分布到三列。
                for i, (emoji_cat, cat) in enumerate(categories):
                    with cols[i % 3]:
                        manual_expenses[cat] = st.number_input(
                            emoji_cat,
                            min_value=0.0,
                            step=50.0,
                            value=default_expenses.get(cat, 0.0),
                            key=f"manual_{cat}",
                            help=f"填写{cat}月度支出"
                        )
                
                if manual_expenses and any(manual_expenses.values()):
                    st.markdown("#### 已录入支出汇总")
                    manual_df_disp = pd.DataFrame({
                        'Category': list(manual_expenses.keys()),
                        'Amount': list(manual_expenses.values())
                    })
                    manual_df_disp = manual_df_disp[manual_df_disp['Amount'] > 0]
                    if not manual_df_disp.empty:
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.dataframe(
                                manual_df_disp,
                                column_config={
                                    "Category": "类别",
                                    "Amount": st.column_config.NumberColumn(
                                        "金额",
                                        format="$%.2f"
                                    )
                                },
                                hide_index=True
                            )
                        with col2:
                            st.metric(
                                "月度支出合计",
                                f"${manual_df_disp['Amount'].sum():,.2f}"
                            )
        
        st.divider()
        
        # 债务信息。
        with st.container():
            st.subheader("债务信息")
            st.info("填写债务后，系统会比较雪崩法和雪球法两种还款策略。")
            
            num_debts = st.number_input(
                "你有几笔债务？",
                min_value=0,
                max_value=10,
                step=1,
                value=2,
                key="num_debts"
            )
            
            debts = []
            if num_debts > 0:
                # 每行最多展示三笔债务。
                cols = st.columns(min(num_debts, 3))
                for i in range(num_debts):
                    col_idx = i % 3
                    with cols[col_idx]:
                        st.markdown(f"##### 债务 #{i+1}")
                        debt_name = st.text_input(
                            "名称",
                            value="信用卡" if i == 0 else f"贷款 {i+1}",
                            key=f"debt_name_{i}",
                            help="例如：信用卡、车贷、消费贷、学生贷款"
                        )
                        debt_amount = st.number_input(
                            "余额",
                            min_value=0.01,
                            step=100.0,
                            value=50000.0 if i == 0 else 120000.0,
                            key=f"debt_amount_{i}",
                            help="当前未还本金"
                        )
                        interest_rate = st.number_input(
                            "年利率（%）",
                            min_value=0.0,
                            max_value=100.0,
                            step=0.1,
                            value=18.0 if i == 0 else 6.0,
                            key=f"debt_rate_{i}",
                            help="填写年化利率"
                        )
                        min_payment = st.number_input(
                            "最低月还款",
                            min_value=0.0,
                            step=10.0,
                            value=3000.0 if i == 0 else 2500.0,
                            key=f"debt_min_payment_{i}",
                            help="每月最低还款额"
                        )
                        
                        debts.append({
                            "name": debt_name,
                            "amount": debt_amount,
                            "interest_rate": interest_rate,
                            "min_payment": min_payment
                        })
                        
                        if col_idx == 2 or i == num_debts - 1:
                            st.markdown("---")
        
        st.divider()
        
        # 分析按钮。
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            analyze_button = st.button(
                "生成财务分析",
                key="analyze_button",
                use_container_width=True,
                help="点击生成预算、储蓄和债务分析"
            )
        
        if analyze_button:
            if expense_option == "上传 CSV 流水" and transactions_df is None:
                st.error("请上传有效的交易 CSV 文件，或选择手动录入。")
                return
            if use_manual_expenses and (not manual_expenses or not any(manual_expenses.values())):
                st.warning("尚未填写手动支出，分析结果可能不完整。")

            st.header("财务分析结果")
            with st.spinner("AI Agent 正在分析你的财务数据..."): 
                financial_data = {
                    "monthly_income": monthly_income,
                    "dependants": dependants,
                    "transactions": transactions_df.to_dict('records') if transactions_df is not None else None,
                    "manual_expenses": manual_expenses if use_manual_expenses else None,
                    "debts": debts
                }
                
                finance_system = FinanceAdvisorSystem(deepseek_api_key)
                
                try:
                    results = asyncio.run(finance_system.analyze_finances(financial_data))
                    
                    tabs = st.tabs(["预算分析", "储蓄策略", "债务优化"])
                    
                    with tabs[0]:
                        st.subheader("预算分析")
                        if "budget_analysis" in results and results["budget_analysis"]:
                            display_budget_analysis(results["budget_analysis"])
                        else:
                            st.write("暂无预算分析结果。")
                    
                    with tabs[1]:
                        st.subheader("储蓄策略")
                        if "savings_strategy" in results and results["savings_strategy"]:
                            display_savings_strategy(results["savings_strategy"])
                        else:
                            st.write("暂无储蓄策略结果。")
                    
                    with tabs[2]:
                        st.subheader("债务优化方案")
                        if "debt_reduction" in results and results["debt_reduction"]:
                            display_debt_reduction(results["debt_reduction"])
                        else:
                            st.write("暂无债务优化结果。")
                except Exception as e:
                    st.error(f"分析过程中发生错误：{str(e)}")
    
    with about_tab:
        st.markdown("""
        ### 关于 AI 财务教练
        
        这个应用使用 Agno 和 DeepSeek，通过三个专职 Agent 生成个人财务分析和建议：
        
        1. **预算分析 Agent**
           - 分析支出模式
           - 找出可优化支出的类别
           - 给出可执行的预算建议
        
        2. **储蓄策略 Agent**
           - 制定个性化储蓄计划
           - 计算应急金需求
           - 推荐自动化储蓄方法
        
        3. **债务优化 Agent**
           - 制定债务偿还策略
           - 比较雪崩法和雪球法
           - 给出可执行的还债建议
        
        ### 隐私与安全
        
        - 输入数据仅用于当前本地会话
        - 不写入本地数据库
        - 模型调用会通过 DeepSeek API 发送必要上下文
        
        ### 风险提示
        
        本项目仅用于技术学习与原型验证，不构成投资、税务、保险或法律建议。
        """)

if __name__ == "__main__":
    main()
