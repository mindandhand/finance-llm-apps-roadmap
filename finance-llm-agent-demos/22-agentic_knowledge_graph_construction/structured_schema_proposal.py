"""结构化金融数据的可执行 Schema 提议与 Critic 修订。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools import FileSample


@dataclass(frozen=True)
class CsvMappingRule:
    """把普通业务 CSV 的两列映射成一条有方向的图关系。"""

    file_name: str
    source_column: str
    source_type: str
    relation: str
    target_column: str
    target_type: str

    def __post_init__(self) -> None:
        values = (
            self.file_name,
            self.source_column,
            self.source_type,
            self.relation,
            self.target_column,
            self.target_type,
        )
        if not all(str(value).strip() for value in values):
            raise ValueError("CSV 构图规则的文件、列、类型和关系均不能为空。")
        object.__setattr__(self, "file_name", self.file_name.strip())
        object.__setattr__(self, "relation", self.relation.strip().upper())

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CsvMappingRule":
        return cls(
            str(value.get("file_name", "")),
            str(value.get("source_column", "")),
            str(value.get("source_type", "")),
            str(value.get("relation", "")),
            str(value.get("target_column", "")),
            str(value.get("target_type", "")),
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "file_name": self.file_name,
            "source_column": self.source_column,
            "source_type": self.source_type,
            "relation": self.relation,
            "target_column": self.target_column,
            "target_type": self.target_type,
        }


@dataclass(frozen=True)
class StructuredGraphPlan:
    rules: list[CsvMappingRule]
    rationale: str
    resolved_findings: list[str] = field(default_factory=list)
    approved_by: str | None = None

    def __post_init__(self) -> None:
        if not self.rules:
            raise ValueError("结构化构图计划至少需要一条 CSV 映射规则。")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StructuredGraphPlan":
        return cls(
            [CsvMappingRule.from_dict(item) for item in value.get("rules", [])],
            str(value.get("rationale", "")).strip(),
            [str(item).strip() for item in value.get("resolved_findings", []) if str(item).strip()],
            str(value.get("approved_by", "")).strip() or None,
        )

    def approve(self, reviewer: str) -> "StructuredGraphPlan":
        name = reviewer.strip()
        if not name:
            raise ValueError("结构化计划审批人不能为空。")
        return StructuredGraphPlan(self.rules, self.rationale, self.resolved_findings, name)

    def as_dict(self) -> dict[str, object]:
        return {
            "rules": [rule.as_dict() for rule in self.rules],
            "rationale": self.rationale,
            "resolved_findings": self.resolved_findings,
            "approved_by": self.approved_by,
        }


def build_structured_schema_prompt(goal: str, catalog: dict[str, FileSample]) -> str:
    csv_samples = [item.as_dict() for item in catalog.values() if item.kind == "csv"]
    return f"""你是金融结构化数据 Schema Proposal Agent。
研究目标：{goal}
CSV 文件样本：{csv_samples}
请为每项关系给出 file_name、source_column、source_type、relation、target_column、target_type。
规则必须引用真实存在的文件和列，并明确关系方向。只返回 JSON：
{{"rules": [{{"file_name": "...", "source_column": "...", "source_type": "Company",
"relation": "SUPPLIES", "target_column": "...", "target_type": "Company"}}], "rationale": "..."}}
"""


def build_structured_critic_prompt(goal: str, plan: StructuredGraphPlan) -> str:
    return f"""你是结构化 Schema Critic Agent。
研究目标：{goal}
待审核计划：{plan.as_dict()}
检查字段是否存在、主语宾语方向、关系命名、遗漏文件以及能否回答研究问题。
只返回 JSON：{{"approved": false, "findings": ["具体问题"]}}
"""


def revise_structured_plan(
    current: StructuredGraphPlan,
    proposal: dict[str, Any],
    findings: list[str],
) -> StructuredGraphPlan:
    """把 Critic 意见显式带入下一版，形成可审计的修订闭环。"""
    revised = StructuredGraphPlan.from_dict(proposal)
    return StructuredGraphPlan(revised.rules, revised.rationale, list(findings))
