"""金融知识图谱研究意图的感知、确认与批准。

原课程把“用户说了一句话”和“已批准的研究目标”视为两个不同状态。
这里保留该边界，避免未经确认的模型理解直接驱动文件选择和构图。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserGoal:
    """用户确认后的知识图谱用途。"""

    kind_of_graph: str
    graph_description: str

    @classmethod
    def create(cls, kind_of_graph: str, graph_description: str) -> "UserGoal":
        kind = kind_of_graph.strip()
        description = graph_description.strip()
        if not kind or not description:
            raise ValueError("图谱类型和研究目标说明均不能为空。")
        return cls(kind, description)

    def as_dict(self) -> dict[str, str]:
        return {
            "kind_of_graph": self.kind_of_graph,
            "graph_description": self.graph_description,
        }


@dataclass
class UserIntentSession:
    """记录意图协商状态；批准前只保存 Agent 的暂时理解。"""

    perceived_goal: UserGoal | None = None
    approved_goal: UserGoal | None = None
    approved_by: str | None = None
    phase: str = "clarifying"

    def set_perceived_goal(self, kind_of_graph: str, graph_description: str) -> UserGoal:
        self.perceived_goal = UserGoal.create(kind_of_graph, graph_description)
        self.approved_goal = None
        self.approved_by = None
        self.phase = "awaiting_goal_approval"
        return self.perceived_goal

    def approve(self, reviewer: str) -> UserGoal:
        if self.perceived_goal is None:
            raise ValueError("请先记录 Agent 对研究目标的理解。")
        approved_by = reviewer.strip()
        if not approved_by:
            raise ValueError("意图审批人不能为空。")
        self.approved_goal = self.perceived_goal
        self.approved_by = approved_by
        self.phase = "approved"
        return self.approved_goal


def build_user_intent_prompt(message: str, perceived_goal: UserGoal | None = None) -> str:
    """生成意图 Agent 提示词，要求澄清而不是擅自批准目标。"""
    return f"""你是金融知识图谱研究意图 Agent。
用户输入：{message.strip()}
当前理解：{perceived_goal.as_dict() if perceived_goal else '尚未形成'}

请判断是否还需要澄清研究对象、关系范围、时间范围或预期问题。
如果信息充分，给出不超过 3 个词的 kind_of_graph 和明确的 graph_description；
你只能记录 perceived goal，不能替用户批准。
只返回 JSON：
{{"needs_clarification": false, "question": "", "kind_of_graph": "上市公司风险图谱", "graph_description": "..."}}
"""
