"""非结构化金融文档的实体与事实抽取计划。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core import GraphPlan
from tools import FileSample


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
