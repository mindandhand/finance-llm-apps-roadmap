"""使用 LangGraph 编排 Schema 提议、批判、人工审批与构图。"""

from __future__ import annotations

from typing import Any, Callable, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from core import GraphPlan
from structured_schema_proposal import StructuredGraphPlan
from unstructured_schema_proposal import UnstructuredGraphPlan


class ConstructionState(TypedDict):
    goal: str
    selected_files: list[str]
    plan: dict[str, Any]
    review_findings: list[str]
    approved: bool
    approved_by: str
    status: str
    written_facts: int


PlanProposer = Callable[[str, list[str]], GraphPlan]
PlanReviewer = Callable[[str, GraphPlan], list[str]]
GraphConstructor = Callable[[ConstructionState], int]


def build_construction_workflow(
    propose_plan: PlanProposer,
    review_plan: PlanReviewer,
    construct_graph: GraphConstructor,
):
    """构建可暂停、可恢复的知识图谱构建工作流。"""

    def propose_node(state: ConstructionState) -> dict[str, Any]:
        plan = propose_plan(state["goal"], state["selected_files"])
        return {"plan": plan.as_dict(), "status": "schema_proposed"}

    def review_node(state: ConstructionState) -> dict[str, Any]:
        plan = GraphPlan.from_dict(state["plan"])
        findings = review_plan(state["goal"], plan)
        return {"review_findings": findings, "status": "awaiting_approval"}

    def approval_node(
        state: ConstructionState,
    ) -> Command[Literal["construct", "reject"]]:
        decision = interrupt(
            {
                "question": "是否批准该 Schema 并写入 Neo4j？",
                "plan": state["plan"],
                "review_findings": state["review_findings"],
            }
        )
        approved = bool(decision.get("approved")) if isinstance(decision, dict) else bool(decision)
        reviewer = str(decision.get("reviewer", "")) if isinstance(decision, dict) else ""
        return Command(
            update={
                "approved": approved,
                "approved_by": reviewer.strip(),
                "status": "approved" if approved else "rejected",
            },
            goto="construct" if approved else "reject",
        )

    def construct_node(state: ConstructionState) -> dict[str, Any]:
        if not state["approved"] or not state["approved_by"]:
            raise RuntimeError("缺少有效的人工审批信息，已阻止写图。")
        count = construct_graph(state)
        return {"written_facts": count, "status": "completed"}

    def reject_node(state: ConstructionState) -> dict[str, Any]:
        return {"status": "rejected", "written_facts": 0}

    builder = StateGraph(ConstructionState)
    builder.add_node("propose", propose_node)
    builder.add_node("review", review_node)
    builder.add_node("approval", approval_node)
    builder.add_node("construct", construct_node)
    builder.add_node("reject", reject_node)
    builder.add_edge(START, "propose")
    builder.add_edge("propose", "review")
    builder.add_edge("review", "approval")
    builder.add_edge("construct", END)
    builder.add_edge("reject", END)
    return builder.compile(checkpointer=InMemorySaver())


class FullConstructionState(TypedDict, total=False):
    """完整课程工作流的共享状态；每个批准结果都显式留痕。"""

    intent_message: str
    perceived_goal: dict[str, str]
    goal_approved_by: str
    available_files: list[str]
    suggested_files: list[str]
    file_reasoning: str
    selected_files: list[str]
    files_approved_by: str
    structured_plan: dict[str, Any]
    structured_findings: list[str]
    unstructured_plan: dict[str, Any]
    status: str
    written_facts: int


def build_full_construction_workflow(
    *,
    perceive_goal: Callable[[str], dict[str, str]],
    suggest_files: Callable[[str, list[str]], dict[str, Any]],
    propose_structured: Callable[[str, list[str]], StructuredGraphPlan],
    review_structured: Callable[[str, StructuredGraphPlan], list[str]],
    revise_structured: Callable[
        [str, StructuredGraphPlan, list[str]], StructuredGraphPlan
    ],
    propose_unstructured: Callable[[str, list[str]], UnstructuredGraphPlan],
    construct_graph: Callable[[FullConstructionState], int],
):
    """构建不缩减的 Agentic 构图流程。

    技术栈由 Google ADK 换成 LangGraph，但仍保留意图、文件、结构化
    Schema、非结构化计划四个独立人工确认点。Critic 有意见时必须先
    生成修订版，审批节点看到并批准的始终是修订后的可执行计划。
    """

    def goal_node(state: FullConstructionState) -> dict[str, Any]:
        perceived = perceive_goal(state["intent_message"])
        if not perceived.get("kind_of_graph") or not perceived.get("graph_description"):
            raise ValueError("意图 Agent 必须返回图谱类型和研究目标说明。")
        return {"perceived_goal": perceived, "status": "awaiting_goal_approval"}

    def goal_approval_node(
        state: FullConstructionState,
    ) -> Command[Literal["suggest_files", "reject"]]:
        decision = interrupt(
            {"stage": "goal", "question": "是否批准 Agent 理解的研究目标？", "goal": state["perceived_goal"]}
        )
        approved, reviewer = _approval_decision(decision)
        return Command(
            update={"goal_approved_by": reviewer, "status": "goal_approved" if approved else "rejected"},
            goto="suggest_files" if approved else "reject",
        )

    def suggest_files_node(state: FullConstructionState) -> dict[str, Any]:
        suggestion = suggest_files(
            state["perceived_goal"]["graph_description"], state["available_files"]
        )
        allowed = set(state["available_files"])
        selected = [name for name in suggestion.get("selected_files", []) if name in allowed]
        if not selected:
            raise ValueError("文件推荐 Agent 没有返回可用文件。")
        return {
            "suggested_files": selected,
            "selected_files": selected,
            "file_reasoning": str(suggestion.get("reasoning", "")),
            "status": "awaiting_file_approval",
        }

    def file_approval_node(
        state: FullConstructionState,
    ) -> Command[Literal["propose_structured", "propose_unstructured", "reject"]]:
        decision = interrupt(
            {
                "stage": "files",
                "question": "是否批准推荐的数据文件？",
                "selected_files": state["selected_files"],
                "reasoning": state["file_reasoning"],
            }
        )
        approved, reviewer = _approval_decision(decision)
        selected = state["selected_files"]
        if isinstance(decision, dict) and decision.get("selected_files"):
            allowed = set(state["available_files"])
            selected = [name for name in decision["selected_files"] if name in allowed]
        if approved and not selected:
            raise ValueError("批准的数据文件范围不能为空。")
        has_csv = any(name.lower().endswith(".csv") for name in selected)
        return Command(
            update={
                "selected_files": selected,
                "files_approved_by": reviewer,
                "status": "files_approved" if approved else "rejected",
            },
            goto=("propose_structured" if has_csv else "propose_unstructured") if approved else "reject",
        )

    def structured_node(state: FullConstructionState) -> dict[str, Any]:
        plan = propose_structured(
            state["perceived_goal"]["graph_description"], state["selected_files"]
        )
        return {"structured_plan": plan.as_dict(), "status": "structured_proposed"}

    def structured_review_node(state: FullConstructionState) -> dict[str, Any]:
        plan = StructuredGraphPlan.from_dict(state["structured_plan"])
        goal = state["perceived_goal"]["graph_description"]
        resolved_findings: list[str] = []
        # 原版 Critic Pattern 是闭环：每次修订都要再次交给 Critic，而不是修一次就批准。
        for _ in range(3):
            findings = review_structured(goal, plan)
            if not findings:
                break
            resolved_findings.extend(findings)
            plan = revise_structured(goal, plan, findings)
        else:
            raise ValueError("结构化 Schema 连续三轮未通过 Critic，请人工缩小目标或调整文件。")
        return {
            "structured_plan": plan.as_dict(),
            "structured_findings": resolved_findings,
            "status": "awaiting_structured_approval",
        }

    def structured_approval_node(
        state: FullConstructionState,
    ) -> Command[Literal["propose_unstructured", "construct", "reject"]]:
        decision = interrupt(
            {
                "stage": "structured_schema",
                "question": "是否批准修订后的结构化构图计划？",
                "plan": state["structured_plan"],
                "findings": state.get("structured_findings", []),
            }
        )
        approved, reviewer = _approval_decision(decision)
        plan = StructuredGraphPlan.from_dict(state["structured_plan"])
        plan = plan.approve(reviewer) if approved else plan
        has_markdown = any(name.lower().endswith(".md") for name in state["selected_files"])
        return Command(
            update={
                "structured_plan": plan.as_dict(),
                "status": "structured_approved" if approved else "rejected",
            },
            goto=("propose_unstructured" if has_markdown else "construct") if approved else "reject",
        )

    def unstructured_node(state: FullConstructionState) -> dict[str, Any]:
        markdown_files = [name for name in state["selected_files"] if name.lower().endswith(".md")]
        plan = propose_unstructured(state["perceived_goal"]["graph_description"], markdown_files)
        return {"unstructured_plan": plan.as_dict(), "status": "awaiting_unstructured_approval"}

    def unstructured_approval_node(
        state: FullConstructionState,
    ) -> Command[Literal["construct", "reject"]]:
        decision = interrupt(
            {
                "stage": "unstructured_schema",
                "question": "是否批准非结构化实体与事实抽取计划？",
                "plan": state["unstructured_plan"],
            }
        )
        approved, reviewer = _approval_decision(decision)
        plan = UnstructuredGraphPlan.from_dict(state["unstructured_plan"])
        plan = plan.approve(reviewer) if approved else plan
        return Command(
            update={
                "unstructured_plan": plan.as_dict(),
                "status": "unstructured_approved" if approved else "rejected",
            },
            goto="construct" if approved else "reject",
        )

    def construct_node(state: FullConstructionState) -> dict[str, Any]:
        if any(name.lower().endswith(".csv") for name in state["selected_files"]):
            structured = StructuredGraphPlan.from_dict(state["structured_plan"])
            if not structured.approved_by:
                raise RuntimeError("未批准结构化计划，禁止构图。")
        if any(name.lower().endswith(".md") for name in state["selected_files"]):
            unstructured = UnstructuredGraphPlan.from_dict(state["unstructured_plan"])
            if not unstructured.approved_by:
                raise RuntimeError("未批准非结构化计划，禁止抽取 Markdown。")
        return {"written_facts": construct_graph(state), "status": "completed"}

    def reject_node(state: FullConstructionState) -> dict[str, Any]:
        return {"written_facts": 0, "status": "rejected"}

    builder = StateGraph(FullConstructionState)
    builder.add_node("perceive_goal", goal_node)
    builder.add_node("goal_approval", goal_approval_node)
    builder.add_node("suggest_files", suggest_files_node)
    builder.add_node("file_approval", file_approval_node)
    builder.add_node("propose_structured", structured_node)
    builder.add_node("review_structured", structured_review_node)
    builder.add_node("structured_approval", structured_approval_node)
    builder.add_node("propose_unstructured", unstructured_node)
    builder.add_node("unstructured_approval", unstructured_approval_node)
    builder.add_node("construct", construct_node)
    builder.add_node("reject", reject_node)
    builder.add_edge(START, "perceive_goal")
    builder.add_edge("perceive_goal", "goal_approval")
    builder.add_edge("suggest_files", "file_approval")
    builder.add_edge("propose_structured", "review_structured")
    builder.add_edge("review_structured", "structured_approval")
    builder.add_edge("propose_unstructured", "unstructured_approval")
    builder.add_edge("construct", END)
    builder.add_edge("reject", END)
    return builder.compile(checkpointer=InMemorySaver())


def _approval_decision(decision: object) -> tuple[bool, str]:
    """所有人工门禁使用同一严格规则：批准必须同时有审批人。"""
    if not isinstance(decision, dict):
        return False, ""
    reviewer = str(decision.get("reviewer", "")).strip()
    return bool(decision.get("approved")) and bool(reviewer), reviewer
