"""非结构化金融文档的实体与事实抽取计划。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core import GraphPlan
from tools import FileSample


@dataclass
class EntityTypeSession:
    """NER Schema Agent 的 proposed/approved 独立状态。"""

    proposed: list[str] = field(default_factory=list)
    approved: list[str] = field(default_factory=list)
    feedback: list[str] = field(default_factory=list)
    approved_by: str | None = None

    def set_proposed(self, entity_types: list[str]) -> list[str]:
        values = list(dict.fromkeys(item.strip() for item in entity_types if item.strip()))
        if not values:
            raise ValueError("至少需要提议一种实体类型。")
        self.proposed = values
        self.approved = []
        self.approved_by = None
        return self.proposed

    def reject(self, feedback: str) -> None:
        text = feedback.strip()
        if not text:
            raise ValueError("拒绝实体类型时必须提供反馈。")
        self.feedback.append(text)

    def approve(self, reviewer: str) -> list[str]:
        if not self.proposed:
            raise ValueError("请先提议实体类型。")
        name = reviewer.strip()
        if not name:
            raise ValueError("实体类型审批人不能为空。")
        self.approved = list(self.proposed)
        self.approved_by = name
        return self.approved

    def as_dict(self) -> dict[str, object]:
        return {
            "proposed": self.proposed,
            "approved": self.approved,
            "feedback": self.feedback,
            "approved_by": self.approved_by,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EntityTypeSession":
        return cls(
            proposed=[str(item) for item in value.get("proposed", [])],
            approved=[str(item) for item in value.get("approved", [])],
            feedback=[str(item) for item in value.get("feedback", [])],
            approved_by=str(value.get("approved_by", "")).strip() or None,
        )


@dataclass(frozen=True)
class FactTypeDefinition:
    subject_label: str
    predicate_label: str
    object_label: str
    description: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (self.subject_label, self.predicate_label, self.object_label, self.description)
        ):
            raise ValueError("事实类型必须包含主语、谓语、宾语和业务说明。")
        object.__setattr__(self, "predicate_label", self.predicate_label.strip().upper())

    def as_dict(self) -> dict[str, str]:
        return {
            "subject_label": self.subject_label,
            "predicate_label": self.predicate_label,
            "object_label": self.object_label,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FactTypeDefinition":
        return cls(
            str(value.get("subject_label", "")),
            str(value.get("predicate_label", "")),
            str(value.get("object_label", "")),
            str(value.get("description", "")),
        )


@dataclass
class FactTypeSession:
    """Fact Agent 状态；只能引用已经批准的实体类型。"""

    approved_entities: list[str]
    proposed: dict[str, FactTypeDefinition] = field(default_factory=dict)
    approved: list[FactTypeDefinition] = field(default_factory=list)
    feedback: list[str] = field(default_factory=list)
    approved_by: str | None = None

    def add_proposed(self, fact: FactTypeDefinition) -> FactTypeDefinition:
        allowed = set(self.approved_entities)
        if fact.subject_label not in allowed or fact.object_label not in allowed:
            raise ValueError("事实类型只能引用已批准的实体类型。")
        self.proposed[fact.predicate_label] = fact
        self.approved = []
        self.approved_by = None
        return fact

    def remove_proposed(self, predicate_label: str) -> FactTypeDefinition:
        key = predicate_label.strip().upper()
        if key not in self.proposed:
            raise ValueError(f"不存在事实类型：{key}")
        return self.proposed.pop(key)

    def reject(self, feedback: str) -> None:
        text = feedback.strip()
        if not text:
            raise ValueError("拒绝事实类型时必须提供反馈。")
        self.feedback.append(text)

    def approve(self, reviewer: str) -> list[FactTypeDefinition]:
        if not self.proposed:
            raise ValueError("请先提议事实类型。")
        name = reviewer.strip()
        if not name:
            raise ValueError("事实类型审批人不能为空。")
        self.approved = list(self.proposed.values())
        self.approved_by = name
        return self.approved

    def as_dict(self) -> dict[str, object]:
        return {
            "approved_entities": self.approved_entities,
            "proposed": {key: fact.as_dict() for key, fact in self.proposed.items()},
            "approved": [fact.as_dict() for fact in self.approved],
            "feedback": self.feedback,
            "approved_by": self.approved_by,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FactTypeSession":
        return cls(
            approved_entities=[str(item) for item in value.get("approved_entities", [])],
            proposed={
                key: FactTypeDefinition.from_dict(item) for key, item in value.get("proposed", {}).items()
            },
            approved=[FactTypeDefinition.from_dict(item) for item in value.get("approved", [])],
            feedback=[str(item) for item in value.get("feedback", [])],
            approved_by=str(value.get("approved_by", "")).strip() or None,
        )


@dataclass(frozen=True)
class UnstructuredGraphPlan:
    entity_types: list[str]
    fact_types: list[str]
    chunk_strategy: str
    rationale: str
    approved_by: str | None = None

    def __post_init__(self) -> None:
        if not self.entity_types or not self.fact_types:
            raise ValueError("非结构化计划必须包含实体类型和事实类型。")
        if not self.chunk_strategy.strip():
            raise ValueError("非结构化计划必须指定分块策略。")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "UnstructuredGraphPlan":
        return cls(
            [str(item).strip() for item in value.get("entity_types", []) if str(item).strip()],
            [str(item).strip().upper() for item in value.get("fact_types", []) if str(item).strip()],
            str(value.get("chunk_strategy", "markdown_paragraph")).strip(),
            str(value.get("rationale", "")).strip(),
            str(value.get("approved_by", "")).strip() or None,
        )

    @classmethod
    def from_graph_plan(cls, plan: GraphPlan) -> "UnstructuredGraphPlan":
        return cls(
            list(plan.unstructured_entity_types),
            list(plan.unstructured_fact_types),
            "markdown_paragraph",
            plan.rationale,
        )

    def approve(self, reviewer: str) -> "UnstructuredGraphPlan":
        name = reviewer.strip()
        if not name:
            raise ValueError("非结构化计划审批人不能为空。")
        return UnstructuredGraphPlan(
            self.entity_types, self.fact_types, self.chunk_strategy, self.rationale, name
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "entity_types": self.entity_types,
            "fact_types": self.fact_types,
            "chunk_strategy": self.chunk_strategy,
            "rationale": self.rationale,
            "approved_by": self.approved_by,
        }


def build_unstructured_schema_prompt(goal: str, catalog: dict[str, FileSample]) -> str:
    markdown_samples = [item.as_dict() for item in catalog.values() if item.kind == "md"]
    return f"""你是金融非结构化知识抽取计划 Agent。
研究目标：{goal}
Markdown 文件样本：{markdown_samples}
请独立提出实体类型、事实类型和分块策略，并说明如何连接结构化领域实体。
只返回 JSON：
{{"entity_types": ["Company", "RiskEvent"], "fact_types": ["EXPOSED_TO"],
"chunk_strategy": "markdown_paragraph", "rationale": "..."}}
"""
