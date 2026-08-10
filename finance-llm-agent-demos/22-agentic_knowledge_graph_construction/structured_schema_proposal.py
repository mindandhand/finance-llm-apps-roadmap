"""结构化金融数据的可执行 Schema 提议与 Critic 修订。"""

from __future__ import annotations

import csv
from io import StringIO
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools import FileSample


@dataclass(frozen=True)
class NodeConstructionRule:
    """从业务 CSV 创建领域节点，保留唯一键和批准属性。"""

    source_file: str
    label: str
    unique_column_name: str
    properties: list[str]

    def __post_init__(self) -> None:
        if not self.source_file.strip() or not self.label.strip() or not self.unique_column_name.strip():
            raise ValueError("节点施工规则的文件、标签和唯一列不能为空。")
        if self.unique_column_name in self.properties:
            raise ValueError("唯一列无需在普通属性中重复声明。")

    def as_dict(self) -> dict[str, object]:
        return {
            "construction_type": "node",
            "source_file": self.source_file,
            "label": self.label,
            "unique_column_name": self.unique_column_name,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "NodeConstructionRule":
        return cls(
            str(value.get("source_file", "")),
            str(value.get("label", "")),
            str(value.get("unique_column_name", "")),
            [str(item) for item in value.get("properties", [])],
        )


@dataclass(frozen=True)
class RelationshipConstructionRule:
    """从业务 CSV 的外键列连接既有领域节点，并导入关系属性。"""

    source_file: str
    relationship_type: str
    from_node_label: str
    from_node_column: str
    to_node_label: str
    to_node_column: str
    properties: list[str]
    from_node_key: str | None = None
    to_node_key: str | None = None

    def __post_init__(self) -> None:
        required = (
            self.source_file,
            self.relationship_type,
            self.from_node_label,
            self.from_node_column,
            self.to_node_label,
            self.to_node_column,
        )
        if not all(str(value).strip() for value in required):
            raise ValueError("关系施工规则的文件、类型、节点和连接列不能为空。")
        object.__setattr__(self, "relationship_type", self.relationship_type.strip().upper())

    def as_dict(self) -> dict[str, object]:
        return {
            "construction_type": "relationship",
            "source_file": self.source_file,
            "relationship_type": self.relationship_type,
            "from_node_label": self.from_node_label,
            "from_node_column": self.from_node_column,
            "to_node_label": self.to_node_label,
            "to_node_column": self.to_node_column,
            "properties": self.properties,
            "from_node_key": self.from_node_key,
            "to_node_key": self.to_node_key,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RelationshipConstructionRule":
        return cls(
            str(value.get("source_file", "")),
            str(value.get("relationship_type", "")),
            str(value.get("from_node_label", "")),
            str(value.get("from_node_column", "")),
            str(value.get("to_node_label", "")),
            str(value.get("to_node_column", "")),
            [str(item) for item in value.get("properties", [])],
            str(value.get("from_node_key", "")).strip() or None,
            str(value.get("to_node_key", "")).strip() or None,
        )


@dataclass
class ConstructionPlan:
    """原版 proposed/approved construction plan 的框架无关实现。

    nodes 与 relationships 是仍可修改的候选方案；只有 approved_by 被设置后，
    工作流才允许真正写入 Neo4j。该对象因此同时承担编辑会话和审批快照职责。
    """

    nodes: dict[str, NodeConstructionRule] = field(default_factory=dict)
    relationships: dict[str, RelationshipConstructionRule] = field(default_factory=dict)
    feedback: list[str] = field(default_factory=list)
    approved_by: str | None = None

    def propose_node(self, rule: NodeConstructionRule) -> NodeConstructionRule:
        # 标签是规则身份键：同标签再次提议表示修订 Critic 指出的旧规则。
        self.nodes[rule.label] = rule
        self.approved_by = None
        return rule

    def propose_relationship(self, rule: RelationshipConstructionRule) -> RelationshipConstructionRule:
        self.relationships[rule.relationship_type] = rule
        self.approved_by = None
        return rule

    def remove_node(self, label: str) -> NodeConstructionRule:
        # 保留原项目细粒度 remove 工具，而不是强迫 Agent 重建整个方案。
        if label not in self.nodes:
            raise ValueError(f"不存在节点施工规则：{label}")
        self.approved_by = None
        return self.nodes.pop(label)

    def remove_relationship(self, relationship_type: str) -> RelationshipConstructionRule:
        key = relationship_type.strip().upper()
        if key not in self.relationships:
            raise ValueError(f"不存在关系施工规则：{key}")
        self.approved_by = None
        return self.relationships.pop(key)

    def reject(self, feedback: str) -> None:
        # 驳回会撤销旧批准；反馈留给下一轮提议提示词使用。
        text = feedback.strip()
        if not text:
            raise ValueError("拒绝施工计划时必须提供反馈。")
        self.feedback.append(text)
        self.approved_by = None

    def approve(self, reviewer: str) -> "ConstructionPlan":
        name = reviewer.strip()
        if not name:
            raise ValueError("施工计划审批人不能为空。")
        if not self.nodes:
            raise ValueError("施工计划必须至少包含一类领域节点。")
        self.approved_by = name
        return self

    def as_dict(self) -> dict[str, object]:
        return {
            "nodes": {key: rule.as_dict() for key, rule in self.nodes.items()},
            "relationships": {key: rule.as_dict() for key, rule in self.relationships.items()},
            "feedback": self.feedback,
            "approved_by": self.approved_by,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ConstructionPlan":
        return cls(
            nodes={key: NodeConstructionRule.from_dict(item) for key, item in value.get("nodes", {}).items()},
            relationships={
                key: RelationshipConstructionRule.from_dict(item)
                for key, item in value.get("relationships", {}).items()
            },
            feedback=[str(item) for item in value.get("feedback", [])],
            approved_by=str(value.get("approved_by", "")).strip() or None,
        )


def _csv_columns_and_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader.fieldnames or []), list(reader)


def validate_construction_plan(root: str | Path, plan: ConstructionPlan) -> list[str]:
    """使用真实文件验证字段、唯一键和节点引用，等价于原 search_file/Critic 工具。"""
    directory = Path(root)
    findings: list[str] = []
    # 节点先校验真实列及唯一值；关系规则随后才能安全引用这些节点。
    for rule in plan.nodes.values():
        path = directory / rule.source_file
        if not path.is_file():
            findings.append(f"节点文件不存在：{rule.source_file}")
            continue
        columns, rows = _csv_columns_and_rows(path)
        missing = {rule.unique_column_name, *rule.properties} - set(columns)
        if missing:
            findings.append(f"{rule.source_file} 缺少字段：{', '.join(sorted(missing))}")
        values = [(row.get(rule.unique_column_name) or "").strip() for row in rows]
        if not values or any(not value for value in values) or len(values) != len(set(values)):
            findings.append(f"{rule.source_file}.{rule.unique_column_name} 不是非空唯一键")
    for rule in plan.relationships.values():
        path = directory / rule.source_file
        if not path.is_file():
            findings.append(f"关系文件不存在：{rule.source_file}")
            continue
        columns, _ = _csv_columns_and_rows(path)
        missing = {rule.from_node_column, rule.to_node_column, *rule.properties} - set(columns)
        if missing:
            findings.append(f"{rule.source_file} 缺少字段：{', '.join(sorted(missing))}")
        if rule.from_node_label not in plan.nodes or rule.to_node_label not in plan.nodes:
            findings.append(f"{rule.relationship_type} 引用了未定义的节点标签")
    return findings


def validate_construction_payloads(
    payloads: dict[str, bytes], plan: ConstructionPlan
) -> list[str]:
    """校验上传文件中的方案，语义与本地目录版本一致。"""
    """上传文件版本的确定性校验，避免只依赖 Critic 的自然语言判断。"""
    findings: list[str] = []
    node_labels: set[str] = set()
    for rule in plan.nodes.values():
        if rule.source_file not in payloads:
            findings.append(f"节点文件未获批准：{rule.source_file}")
            continue
        reader = csv.DictReader(StringIO(payloads[rule.source_file].decode("utf-8-sig")))
        columns = set(reader.fieldnames or [])
        rows = list(reader)
        node_labels.add(rule.label)
        missing = {rule.unique_column_name, *rule.properties} - columns
        if missing:
            findings.append(f"{rule.source_file} 缺少字段：{', '.join(sorted(missing))}")
        values = [(row.get(rule.unique_column_name) or "").strip() for row in rows]
        if not values or any(not value for value in values) or len(values) != len(set(values)):
            findings.append(f"{rule.source_file}.{rule.unique_column_name} 不是非空唯一键")
    for rule in plan.relationships.values():
        if rule.source_file not in payloads:
            findings.append(f"关系文件未获批准：{rule.source_file}")
            continue
        reader = csv.DictReader(StringIO(payloads[rule.source_file].decode("utf-8-sig")))
        columns = set(reader.fieldnames or [])
        missing = {rule.from_node_column, rule.to_node_column, *rule.properties} - columns
        if missing:
            findings.append(f"{rule.source_file} 缺少字段：{', '.join(sorted(missing))}")
        if rule.from_node_label not in node_labels or rule.to_node_label not in node_labels:
            findings.append(f"{rule.relationship_type} 引用了未定义的节点标签")
    return findings


@dataclass(frozen=True)
class CsvMappingRule:
    """旧课程接口：把 CSV 行映射成带证据定位的事实三元组。"""
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
    """兼容旧版一次性结构化方案，避免业务改写导致原调用失效。"""
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
    """生成 Schema Critic 提示词，要求输出可执行的字段级修订意见。"""
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
