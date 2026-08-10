"""Agent 驱动的金融知识图谱构建学习应用。"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

from agents import AgentService, DeepSeekClient
from file_suggestion import build_catalog_from_payloads
from graph_utilities import GraphUtilities
from kg_construction import collect_facts_from_files
from neo4j_store import Neo4jGraphStore
from structured_schema_proposal import StructuredGraphPlan
from unstructured_schema_proposal import UnstructuredGraphPlan
from workflow import build_full_construction_workflow


APP_DIR = Path(__file__).resolve().parent
for env_path in (APP_DIR / ".env", APP_DIR.parent / ".env", APP_DIR.parent.parent / ".env"):
    load_dotenv(env_path)

SAMPLE_FILES = {
    path.name: path.read_bytes()
    for path in sorted((APP_DIR / "data").iterdir())
    if path.suffix.lower() in {".csv", ".md"}
}


def make_agent_service() -> AgentService:
    return AgentService(
        DeepSeekClient(
            st.session_state.api_key,
            st.session_state.base_url,
            st.session_state.model,
        )
    )


def make_store() -> Neo4jGraphStore:
    return Neo4jGraphStore(
        st.session_state.neo4j_uri,
        st.session_state.neo4j_user,
        st.session_state.neo4j_password,
    )


st.set_page_config(page_title="金融图谱构建实验室", page_icon="◈", layout="wide")
st.markdown(
    """
    <style>
    :root { --ink:#14231f; --paper:#f4f0e6; --jade:#087f5b; --amber:#d97706; }
    .stApp { background: linear-gradient(135deg,#f7f4ec 0%,#edf4ef 58%,#e4eee8 100%); color:var(--ink); }
    [data-testid="stSidebar"] { background:#14231f; }
    [data-testid="stSidebar"] * { color:#f4f0e6 !important; }
    .hero { border-left:7px solid var(--jade); padding:1.2rem 1.5rem; margin:.5rem 0 1.4rem;
      background:rgba(255,255,255,.72); box-shadow:0 16px 45px rgba(20,35,31,.08); }
    .eyebrow { color:var(--jade); font-weight:800; letter-spacing:.16em; font-size:.75rem; }
    .hero h1 { font-family:Georgia,'Songti SC',serif; font-size:2.5rem; margin:.35rem 0; color:var(--ink); }
    .pipeline { display:flex; gap:.4rem; flex-wrap:wrap; margin:0 0 1.25rem; }
    .pipeline span { border:1px solid #b7c8bf; background:rgba(255,255,255,.62); padding:.35rem .65rem;
      border-radius:2px; font-size:.78rem; font-weight:700; }
    .pipeline b { color:var(--amber); padding:.3rem .05rem; }
    div[data-testid="stMetric"] { background:rgba(255,255,255,.74); border-top:3px solid var(--jade); padding:1rem; }
    .stButton button { border-radius:2px; font-weight:750; }
    </style>
    <div class="hero"><div class="eyebrow">DEMO 22 · AGENTIC GRAPHRAG</div>
    <h1>金融关系与风险图谱构建实验室</h1>
    <p>让 Agent 规划图谱，但把数据选择、写库审批和证据核验留给研究员。</p></div>
    <div class="pipeline"><span>01 研究意图</span><b>→</b><span>02 文件推荐</span><b>→</b>
    <span>03 Schema 提议</span><b>→</b><span>04 批判审核</span><b>→</b>
    <span>05 人工批准</span><b>→</b><span>06 Neo4j 构图</span><b>→</b><span>07 GraphRAG</span></div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("运行配置")
    st.text_input("DeepSeek API Key", value=os.getenv("DEEPSEEK_API_KEY", ""), type="password", key="api_key")
    st.text_input("模型", value=os.getenv("DEEPSEEK_MODEL_ID", "deepseek-chat"), key="model")
    st.text_input("API 地址", value=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"), key="base_url")
    st.divider()
    st.text_input("Neo4j URI", value=os.getenv("NEO4J_URI", "bolt://localhost:7688"), key="neo4j_uri")
    st.text_input("Neo4j 用户", value=os.getenv("NEO4J_USER", "neo4j"), key="neo4j_user")
    st.text_input("Neo4j 密码", value=os.getenv("NEO4J_PASSWORD", "password"), type="password", key="neo4j_password")
    if st.button("检查 Neo4j 连接", use_container_width=True):
        try:
            store = make_store()
            store.verify_connectivity()
            store.close()
            st.success("连接正常")
        except Exception as exc:
            st.error(str(exc))

build_tab, query_tab, graph_tab, learn_tab = st.tabs(["构建工作流", "GraphRAG 问答", "图谱状态", "技术解读"])

with build_tab:
    st.subheader("研究意图与数据范围")
    goal = st.text_area(
        "研究目标",
        value="分析远航汽车的供应链依赖，并追踪上游风险事件可能形成的影响路径。",
        height=90,
    )
    uploads = st.file_uploader("补充 CSV 或 Markdown 文件", type=["csv", "md"], accept_multiple_files=True)
    catalog = dict(SAMPLE_FILES)
    catalog.update({item.name: item.getvalue() for item in uploads})
    catalog_samples = build_catalog_from_payloads(catalog)

    left, right = st.columns([1, 2])
    with left:
        if st.button("让 Agent 推荐文件", use_container_width=True):
            try:
                st.session_state.suggestion = make_agent_service().suggest_files(goal, catalog_samples)
            except Exception as exc:
                st.error(str(exc))
    with right:
        suggestion = st.session_state.get("suggestion", {})
        if suggestion:
            st.info(f"推荐理由：{suggestion['reasoning']}")

    default_files = st.session_state.get("suggestion", {}).get("selected_files", list(SAMPLE_FILES))
    selected_files = st.multiselect(
        "研究员确认使用的文件",
        options=list(catalog),
        default=[name for name in default_files if name in catalog],
    )

    if st.button("启动完整构图工作流", type="primary", use_container_width=True):
        if not selected_files:
            st.error("请至少选择一个数据文件。")
        else:
            try:
                service = make_agent_service()
                # 回调只读取工作流最终批准的文件和计划，界面上的临时选择不能绕过审批。
                def selected_catalog(names):
                    return {name: catalog_samples[name] for name in names if name in catalog_samples}

                def construct(state):
                    approved_files = state["selected_files"]
                    payloads = {name: catalog[name] for name in approved_files}
                    structured_value = state.get("structured_plan")
                    structured_plan = (
                        StructuredGraphPlan.from_dict(structured_value)
                        if structured_value
                        else None
                    )
                    unstructured_value = state.get("unstructured_plan")
                    unstructured_plan = (
                        UnstructuredGraphPlan.from_dict(unstructured_value)
                        if unstructured_value
                        else None
                    )
                    facts = collect_facts_from_files(
                        payloads, structured_plan, unstructured_plan, service
                    )
                    store = make_store()
                    try:
                        return store.upsert_facts(facts)
                    finally:
                        store.close()

                graph = build_full_construction_workflow(
                    perceive_goal=service.perceive_goal,
                    suggest_files=lambda approved_goal, names: service.suggest_files(
                        approved_goal, selected_catalog(names)
                    ),
                    propose_structured=lambda approved_goal, names: service.propose_structured_plan(
                        approved_goal, selected_catalog(names)
                    ),
                    review_structured=service.review_structured_plan,
                    revise_structured=service.revise_structured_plan,
                    propose_unstructured=lambda approved_goal, names: service.propose_unstructured_plan(
                        approved_goal, selected_catalog(names)
                    ),
                    construct_graph=construct,
                )
                config = {"configurable": {"thread_id": str(uuid.uuid4())}}
                result = graph.invoke(
                    {
                        "intent_message": goal,
                        "available_files": selected_files,
                        "status": "new",
                    },
                    config=config,
                )
                st.session_state.workflow_graph = graph
                st.session_state.workflow_config = config
                st.session_state.workflow_result = result
            except Exception as exc:
                st.error(str(exc))

    result = st.session_state.get("workflow_result")
    if result:
        status = result.get("status", "unknown")
        st.caption(f"当前状态：{status}")
        if result.get("perceived_goal"):
            st.markdown("**Agent 理解的研究目标**")
            st.json(result["perceived_goal"])
        if result.get("file_reasoning"):
            st.info(f"文件推荐理由：{result['file_reasoning']}")
            st.write("推荐文件：", result.get("selected_files", []))
        if result.get("structured_plan"):
            st.markdown("**结构化可执行构图计划**")
            st.json(result["structured_plan"])
        if result.get("structured_findings"):
            st.markdown("**批判 Agent 的审核意见**")
            for finding in result["structured_findings"]:
                st.warning(finding)
        if result.get("unstructured_plan"):
            st.markdown("**非结构化实体与事实抽取计划**")
            st.json(result["unstructured_plan"])

        approval_statuses = {
            "awaiting_goal_approval": "批准研究目标并继续",
            "awaiting_file_approval": "批准文件范围并继续",
            "awaiting_structured_approval": "批准结构化计划并继续",
            "awaiting_unstructured_approval": "批准非结构化计划并构图",
        }
        if status in approval_statuses:
            reviewer = st.text_input("审批人", value="研究员")
            approve_col, reject_col = st.columns(2)
            if approve_col.button(approval_statuses[status], type="primary", use_container_width=True):
                try:
                    decision = {"approved": True, "reviewer": reviewer}
                    if status == "awaiting_file_approval":
                        decision["selected_files"] = selected_files
                    st.session_state.workflow_result = st.session_state.workflow_graph.invoke(
                        Command(resume=decision),
                        config=st.session_state.workflow_config,
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if reject_col.button("拒绝当前阶段", use_container_width=True):
                st.session_state.workflow_result = st.session_state.workflow_graph.invoke(
                    Command(resume={"approved": False, "reviewer": reviewer}),
                    config=st.session_state.workflow_config,
                )
                st.rerun()
        elif status == "completed":
            st.success(f"构图完成，共写入 {result.get('written_facts', 0)} 条带证据事实。")
        elif status == "rejected":
            st.error("方案已拒绝，Neo4j 未发生写入。")

with query_tab:
    st.subheader("沿图路径回答，而不是凭模型记忆回答")
    question = st.text_input("问题", value="远航汽车可能受到哪些上游风险影响？")
    hops = st.slider("最大关系跳数", 1, 3, 2)
    if st.button("检索并回答", type="primary", use_container_width=True):
        try:
            store = make_store()
            service = make_agent_service()
            strategy = service.select_retrieval_strategy(question)
            retrieval = GraphUtilities(store).retrieve(question, strategy, hops)
            store.close()
            answer = service.answer(question, retrieval.context)
            st.caption(f"GraphRAG Agent 选择的检索策略：{strategy}")
            st.markdown(answer)
            st.markdown("**推理路径**")
            for path in retrieval.paths:
                st.code(path, language=None)
            st.markdown("**证据账本**")
            for index, citation in enumerate(retrieval.citations, start=1):
                with st.expander(f"[{index}] {citation.source_name} · {citation.locator}"):
                    st.write(citation.excerpt)
                    st.caption(f"抽取置信度：{citation.confidence:.0%}")
        except Exception as exc:
            st.error(str(exc))

with graph_tab:
    st.subheader("Neo4j 图谱状态")
    if st.button("刷新统计"):
        try:
            store = make_store()
            stats = store.stats()
            store.close()
            columns = st.columns(3)
            columns[0].metric("实体", stats["entities"])
            columns[1].metric("事实", stats["facts"])
            columns[2].metric("证据", stats["evidence"])
        except Exception as exc:
            st.error(str(exc))
    with st.expander("危险操作：清空本示例图谱"):
        confirmation = st.text_input("输入“确认清空图谱”")
        if st.button("清空图谱"):
            try:
                store = make_store()
                store.clear_graph(confirmation)
                store.close()
                st.success("图谱已清空。")
            except Exception as exc:
                st.error(str(exc))

with learn_tab:
    st.subheader("这个示例保留了什么")
    st.markdown(
        """
        - **文件推荐 Agent**：根据研究意图建议 CSV 与 Markdown 数据，最终选择仍由研究员确认。
        - **Schema Agent + 批判 Agent**：分别提出并审查节点、关系、事实类型和溯源约束。
        - **LangGraph 人工审批**：使用 `interrupt()` 真正暂停；使用同一 `thread_id` 和 `Command(resume=...)` 恢复。
        - **双通道构图**：CSV 确定性转换；Markdown 由 DeepSeek 抽取，并优先链接结构化实体标准名。
        - **Neo4j 证据模型**：`Entity → Fact → Entity` 与 `Evidence → Fact`，同一事实可保留多份来源。
        - **GraphRAG**：从问题中的实体出发做多跳遍历，答案必须使用 `[n]` 行内引用，证据不足时拒答。
        """
    )
