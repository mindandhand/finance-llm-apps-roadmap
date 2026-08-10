"""使用 LangGraph 编排 Schema 提议、批判、人工审批与构图。"""

from __future__ import annotations

from typing import Any, Callable, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from core import GraphPlan
from structured_schema_proposal import StructuredGraphPlan
from unstructured_schema_proposal import UnstructuredGraphPlan
from structured_schema_proposal import ConstructionPlan
from unstructured_schema_proposal import EntityTypeSession, FactTypeDefinition, FactTypeSession


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
    clarification_question: str
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


class ParityState(TypedDict, total=False):
    """与原对话式 Agent 阶段一一对应的可检查点共享状态。

    这里只保存普通 dict/list，而不保存 dataclass 实例，保证 LangGraph 的
    checkpointer 能稳定序列化；各节点使用时再恢复为领域对象。
    """

    messages: list[dict[str, str]]
    available_files: list[str]
    goal_feedback: list[str]
    file_feedback: list[str]
    structured_feedback: list[str]
    entity_feedback: list[str]
    fact_feedback: list[str]
    perceived_goal: dict[str, str]
    # 必须声明为图状态字段，否则 LangGraph 会在进入 clarification 节点前过滤它。
    clarification_question: str
    goal_approved_by: str
    selected_files: list[str]
    file_reasoning: str
    files_approved_by: str
    construction_plan: dict[str, Any]
    structured_findings: list[str]
    entity_session: dict[str, Any]
    fact_session: dict[str, Any]
    status: str
    written_facts: int


def build_parity_workflow(
    *,
    perceive_goal: Callable[[list[dict[str, str]], list[str]], dict[str, Any]],
    suggest_files: Callable[[dict[str, str], list[str], list[str]], dict[str, Any]],
    propose_construction_plan: Callable[[dict[str, str], list[str], list[str]], ConstructionPlan],
    review_construction_plan: Callable[[dict[str, str], list[str], ConstructionPlan], list[str]],
    propose_entity_types: Callable[[dict[str, str], list[str], list[str], list[str]], list[str]],
    propose_fact_types: Callable[
        [dict[str, str], list[str], list[str]], list[FactTypeDefinition]
    ],
    construct_graph: Callable[[ParityState], int],
):
    """恢复原版对话/工具行为，同时用 LangGraph 实现可恢复人工门禁。"""

    def perceive_node(state: ParityState) -> dict[str, Any]:
        # 意图 Agent 可以返回澄清问题，也可以形成 perceived goal；两者不能同时推进。
        result = perceive_goal(state["messages"], state.get("goal_feedback", []))
        if result.get("needs_clarification"):
            question = str(result.get("question", "")).strip()
            if not question:
                raise ValueError("意图 Agent 要求澄清时必须返回问题。")
            return {"status": "awaiting_clarification", "clarification_question": question}
        goal = {
            "kind_of_graph": str(result.get("kind_of_graph", "")).strip(),
            "graph_description": str(result.get("graph_description", "")).strip(),
        }
        if not all(goal.values()):
            raise ValueError("意图 Agent 未形成完整 perceived goal。")
        return {"perceived_goal": goal, "status": "awaiting_goal_approval"}

    def goal_gate(state: ParityState) -> Command[Literal["suggest", "perceive"]]:
        # 第一门：拒绝后携带反馈回到意图 Agent，而不是直接终止整个会话。
        decision = interrupt({"stage": "goal", "goal": state["perceived_goal"]})
        approved, reviewer = _approval_decision(decision)
        if approved:
            return Command(update={"goal_approved_by": reviewer, "status": "goal_approved"}, goto="suggest")
        feedback = _feedback(decision, "拒绝研究目标时必须提供修改意见。")
        return Command(
            update={"goal_feedback": [*state.get("goal_feedback", []), feedback], "status": "clarifying"},
            goto="perceive",
        )

    def clarification_node(state: ParityState) -> Command[Literal["perceive"]]:
        # interrupt 暂停图执行；恢复时把问答双方都追加到对话历史。
        answer = interrupt(
            {"stage": "clarification", "question": state["clarification_question"]}
        )
        content = (
            str(answer.get("message", "")).strip() if isinstance(answer, dict) else str(answer).strip()
        )
        if not content:
            raise ValueError("请回答意图 Agent 的澄清问题。")
        messages = [
            *state["messages"],
            {"role": "assistant", "content": state["clarification_question"]},
            {"role": "user", "content": content},
        ]
        return Command(update={"messages": messages, "status": "clarifying"}, goto="perceive")

    def suggest_node(state: ParityState) -> dict[str, Any]:
        # 推荐结果必须取自候选目录，模型虚构的路径会在此被过滤。
        result = suggest_files(
            state["perceived_goal"], state["available_files"], state.get("file_feedback", [])
        )
        allowed = set(state["available_files"])
        selected = [str(item) for item in result.get("selected_files", []) if str(item) in allowed]
        if not selected:
            raise ValueError("文件 Agent 未推荐任何候选目录内文件。")
        return {
            "selected_files": selected,
            "file_reasoning": str(result.get("reasoning", "")).strip(),
            "status": "awaiting_file_approval",
        }

    def file_gate(state: ParityState) -> Command[Literal["structured", "suggest"]]:
        # 第二门：批准的是最终数据范围，不等同于 UI 中允许查看的候选范围。
        decision = interrupt({"stage": "files", "files": state["selected_files"]})
        approved, reviewer = _approval_decision(decision)
        if approved:
            return Command(update={"files_approved_by": reviewer, "status": "files_approved"}, goto="structured")
        feedback = _feedback(decision, "拒绝文件建议时必须提供修改意见。")
        return Command(
            update={"file_feedback": [*state.get("file_feedback", []), feedback]}, goto="suggest"
        )

    def structured_node(state: ParityState) -> dict[str, Any]:
        # Schema Proposal 与独立 Critic 最多往返三轮，防止模型无限自我修订。
        plan = propose_construction_plan(
            state["perceived_goal"], state["selected_files"], state.get("structured_feedback", [])
        )
        findings: list[str] = []
        for _ in range(3):
            current = review_construction_plan(state["perceived_goal"], state["selected_files"], plan)
            if not current:
                break
            findings.extend(current)
            plan.feedback.extend(current)
            plan = propose_construction_plan(state["perceived_goal"], state["selected_files"], plan.feedback)
        else:
            raise ValueError("结构化施工计划连续三轮未通过 Critic。")
        return {
            "construction_plan": plan.as_dict(),
            "structured_findings": findings,
            "status": "awaiting_structured_approval",
        }

    def structured_gate(state: ParityState) -> Command[Literal["entities", "structured"]]:
        # 第三门：只有人工批准后的施工计划才会带 approved_by 进入构建节点。
        plan = ConstructionPlan.from_dict(state["construction_plan"])
        decision = interrupt({"stage": "structured", "plan": plan.as_dict()})
        approved, reviewer = _approval_decision(decision)
        if approved:
            plan.approve(reviewer)
            return Command(update={"construction_plan": plan.as_dict()}, goto="entities")
        feedback = _feedback(decision, "拒绝施工计划时必须提供修改意见。")
        return Command(
            update={"structured_feedback": [*state.get("structured_feedback", []), feedback]},
            goto="structured",
        )

    def entity_node(state: ParityState) -> dict[str, Any]:
        # 结构化标签作为 well-known types，NER Agent 优先复用以便后续实体对齐。
        plan = ConstructionPlan.from_dict(state["construction_plan"])
        proposed = propose_entity_types(
            state["perceived_goal"],
            state["selected_files"],
            sorted(plan.nodes),
            state.get("entity_feedback", []),
        )
        session = EntityTypeSession()
        session.set_proposed(proposed)
        return {"entity_session": session.as_dict(), "status": "awaiting_entity_approval"}

    def entity_gate(state: ParityState) -> Command[Literal["facts", "entities"]]:
        # 第四门只批准实体类型；事实类型仍需下一阶段独立讨论。
        session = EntityTypeSession.from_dict(state["entity_session"])
        decision = interrupt({"stage": "entities", "entity_types": session.proposed})
        approved, reviewer = _approval_decision(decision)
        if approved:
            session.approve(reviewer)
            return Command(update={"entity_session": session.as_dict()}, goto="facts")
        feedback = _feedback(decision, "拒绝实体类型时必须提供修改意见。")
        return Command(
            update={"entity_feedback": [*state.get("entity_feedback", []), feedback]}, goto="entities"
        )

    def fact_node(state: ParityState) -> dict[str, Any]:
        # Fact Agent 只能使用上一门已经批准的实体类型作为主语和宾语。
        entities = EntityTypeSession.from_dict(state["entity_session"])
        proposed = propose_fact_types(
            state["perceived_goal"], entities.approved, state.get("fact_feedback", [])
        )
        session = FactTypeSession(entities.approved)
        for fact in proposed:
            session.add_proposed(fact)
        return {"fact_session": session.as_dict(), "status": "awaiting_fact_approval"}

    def fact_gate(state: ParityState) -> Command[Literal["construct", "facts"]]:
        # 第五门通过后才具备全部写库前置条件。
        session = FactTypeSession.from_dict(state["fact_session"])
        decision = interrupt({"stage": "facts", "fact_types": [fact.as_dict() for fact in session.proposed.values()]})
        approved, reviewer = _approval_decision(decision)
        if approved:
            session.approve(reviewer)
            return Command(update={"fact_session": session.as_dict()}, goto="construct")
        feedback = _feedback(decision, "拒绝事实类型时必须提供修改意见。")
        return Command(update={"fact_feedback": [*state.get("fact_feedback", []), feedback]}, goto="facts")

    def construct_node(state: ParityState) -> dict[str, Any]:
        # 写库前再次做防御性检查；即使外部错误跳转，也不能绕过任何审批。
        plan = ConstructionPlan.from_dict(state["construction_plan"])
        entities = EntityTypeSession.from_dict(state["entity_session"])
        facts = FactTypeSession.from_dict(state["fact_session"])
        if not plan.approved_by:
            raise RuntimeError("结构化施工计划未批准。")
        if not entities.approved_by or not facts.approved_by:
            raise RuntimeError("实体类型或事实类型未批准。")
        callback_state = dict(state)
        callback_state.update(
            {"construction_plan": plan, "entity_session": entities, "fact_session": facts}
        )
        return {"written_facts": construct_graph(callback_state), "status": "completed"}

    # 节点负责业务状态变化，边只描述固定的阶段顺序；驳回回路由 Command 控制。
    builder = StateGraph(ParityState)
    for name, node in (
        ("perceive", perceive_node), ("clarification", clarification_node),
        ("goal_gate", goal_gate), ("suggest", suggest_node),
        ("file_gate", file_gate), ("structured", structured_node), ("structured_gate", structured_gate),
        ("entities", entity_node), ("entity_gate", entity_gate), ("facts", fact_node),
        ("fact_gate", fact_gate), ("construct", construct_node),
    ):
        builder.add_node(name, node)
    builder.add_edge(START, "perceive")
    builder.add_conditional_edges(
        "perceive",
        lambda state: "clarification" if state["status"] == "awaiting_clarification" else "goal_gate",
        {"clarification": "clarification", "goal_gate": "goal_gate"},
    )
    builder.add_edge("suggest", "file_gate")
    builder.add_edge("structured", "structured_gate")
    builder.add_edge("entities", "entity_gate")
    builder.add_edge("facts", "fact_gate")
    builder.add_edge("construct", END)
    return builder.compile(checkpointer=InMemorySaver())


def _feedback(decision: object, message: str) -> str:
    """拒绝动作必须携带反馈，否则 Agent 没有可执行的修订依据。"""
    if not isinstance(decision, dict) or not str(decision.get("feedback", "")).strip():
        raise ValueError(message)
    return str(decision["feedback"]).strip()
