"""Agentic 金融知识图谱示例的可测试核心逻辑。"""

from __future__ import annotations

import csv
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ApprovalRequiredError(RuntimeError):
    """尚未完成人工审批时阻止写图。"""


@dataclass(frozen=True)
class Evidence:
    source_name: str
    locator: str
    excerpt: str
    confidence: float


@dataclass(frozen=True)
class ExtractedFact:
    source: str
    source_type: str
    relation: str
    target: str
    target_type: str
    evidence: Evidence


@dataclass(frozen=True)
class GraphPlan:
    node_types: list[str]
    relationship_types: list[str]
    rationale: str
    unstructured_entity_types: list[str] = field(default_factory=list)
    unstructured_fact_types: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GraphPlan":
        node_types = [str(item).strip() for item in value.get("node_types", []) if str(item).strip()]
        relationship_types = [
            str(item).strip().upper()
            for item in value.get("relationship_types", [])
            if str(item).strip()
        ]
        if not node_types or not relationship_types:
            raise ValueError("图谱方案必须同时包含节点类型和关系类型。")
        return cls(
            node_types,
            relationship_types,
            str(value.get("rationale", "")).strip(),
            [str(item).strip() for item in value.get("unstructured_entity_types", []) if str(item).strip()],
            [str(item).strip() for item in value.get("unstructured_fact_types", []) if str(item).strip()],
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_types": self.node_types,
            "relationship_types": self.relationship_types,
            "rationale": self.rationale,
            "unstructured_entity_types": self.unstructured_entity_types,
            "unstructured_fact_types": self.unstructured_fact_types,
        }


@dataclass
class WorkflowSession:
    goal: str
    phase: str = "intent"
    plan: GraphPlan | None = None
    review_findings: list[str] = field(default_factory=list)
    approved_by: str | None = None

    def propose(self, plan: GraphPlan) -> None:
        self.plan = plan
        self.phase = "schema_proposed"
        self.approved_by = None

    def review(self, findings: list[str]) -> None:
        if self.plan is None:
            raise ValueError("请先生成图谱方案。")
        self.review_findings = [item.strip() for item in findings if item.strip()]
        self.phase = "reviewed"

    def approve(self, reviewer: str) -> None:
        if self.phase not in {"schema_proposed", "reviewed"}:
            raise ValueError("当前阶段没有可审批的图谱方案。")
        if not reviewer.strip():
            raise ValueError("审批人不能为空。")
        self.approved_by = reviewer.strip()
        self.phase = "approved"

    def begin_construction(self) -> None:
        if self.phase != "approved" or not self.approved_by:
            raise ApprovalRequiredError("写入 Neo4j 前必须由研究员审批图谱方案。")
        self.phase = "constructing"


def build_financial_schema_prompt(goal: str, file_names: list[str]) -> str:
    """生成金融场景 Schema Agent 的中文提示词。"""
    return f"""你是金融知识图谱 Schema 设计 Agent。
研究目标：{goal}
候选文件：{', '.join(file_names) or '暂无'}

请提出节点类型、关系类型及其业务理由，并满足以下技术契约：
1. 每一条关系都必须保留来源、原文定位和置信度；
2. 同时支持 CSV 结构化数据与 Markdown 非结构化文本；
3. 输出将交给独立的批判 Agent 检查歧义、缺失关系和不可验证结论；
4. 不得在人工批准之前写入数据库。

只返回 JSON：
{{"node_types": ["Company"], "relationship_types": ["SUPPLIES"],
  "unstructured_entity_types": ["RiskEvent"],
  "unstructured_fact_types": ["EXPOSED_TO"], "rationale": "..."}}
"""


def build_critic_prompt(goal: str, plan: GraphPlan) -> str:
    return f"""你是知识图谱批判 Agent。研究目标：{goal}
待审核方案：{plan.as_dict()}
检查节点与关系是否能回答研究问题、是否存在方向歧义，以及是否包含来源、定位、置信度和实体消歧要求。
只返回 JSON：{{"findings": ["具体修改意见"]}}
"""


def load_structured_facts(path: str | Path) -> list[ExtractedFact]:
    """读取标准关系 CSV，并给每条事实附加行级证据。"""
    csv_path = Path(path)
    required = {"source", "source_type", "relation", "target", "target_type"}
    facts: list[ExtractedFact] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV 缺少字段：{', '.join(sorted(missing))}")
        for row_number, row in enumerate(reader, start=2):
            values = {key: (row.get(key) or "").strip() for key in required}
            if not all(values.values()):
                raise ValueError(f"第 {row_number} 行存在空字段。")
            excerpt = f"{values['source']} -[{values['relation']}]-> {values['target']}"
            facts.append(
                ExtractedFact(
                    source=values["source"],
                    source_type=values["source_type"],
                    relation=values["relation"].upper(),
                    target=values["target"],
                    target_type=values["target_type"],
                    evidence=Evidence(csv_path.name, f"第 {row_number} 行", excerpt, 1.0),
                )
            )
    return facts


@dataclass(frozen=True)
class RetrievalResult:
    paths: list[str]
    citations: list[Evidence]
    context: str


class InMemoryGraphStore:
    """用于测试和界面预览；正式构图使用 Neo4jGraphStore。"""

    def __init__(self) -> None:
        self.nodes: dict[str, str] = {}
        self.relationships: list[ExtractedFact] = []

    @staticmethod
    def _canonical(name: str, aliases: dict[str, str] | None = None) -> str:
        cleaned = name.strip()
        return (aliases or {}).get(cleaned, cleaned)

    def upsert_fact(self, fact: ExtractedFact, aliases: dict[str, str] | None = None) -> None:
        source = self._canonical(fact.source, aliases)
        target = self._canonical(fact.target, aliases)
        canonical_fact = ExtractedFact(
            source,
            fact.source_type,
            fact.relation.upper(),
            target,
            fact.target_type,
            fact.evidence,
        )
        self.nodes[source] = fact.source_type
        self.nodes[target] = fact.target_type
        identity = (source, canonical_fact.relation, target, fact.evidence.source_name, fact.evidence.locator)
        existing = {
            (item.source, item.relation, item.target, item.evidence.source_name, item.evidence.locator)
            for item in self.relationships
        }
        if identity not in existing:
            self.relationships.append(canonical_fact)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def relationship_count(self) -> int:
        return len(self.relationships)

    @property
    def evidence(self) -> list[Evidence]:
        return [item.evidence for item in self.relationships]


class GraphRetriever:
    """从问题中识别起点，并对关系执行无向多跳遍历。"""

    def __init__(self, store: InMemoryGraphStore) -> None:
        self.store = store

    def retrieve(self, question: str, max_hops: int = 2) -> RetrievalResult:
        seeds = [name for name in self.store.nodes if name in question]
        if not seeds:
            seeds = list(self.store.nodes)[:1]

        visited = set(seeds)
        queue = deque((seed, 0) for seed in seeds)
        selected: list[ExtractedFact] = []
        while queue:
            current, depth = queue.popleft()
            if depth >= max_hops:
                continue
            for fact in self.store.relationships:
                if fact.source == current:
                    neighbor = fact.target
                elif fact.target == current:
                    neighbor = fact.source
                else:
                    continue
                if fact not in selected:
                    selected.append(fact)
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))

        paths = [f"{fact.source} -[{fact.relation}]-> {fact.target}" for fact in selected]
        citations = [fact.evidence for fact in selected]
        context = "\n".join(
            f"[{index}] {path}；证据：{fact.evidence.excerpt}"
            for index, (path, fact) in enumerate(zip(paths, selected), start=1)
        )
        return RetrievalResult(paths, citations, context)
