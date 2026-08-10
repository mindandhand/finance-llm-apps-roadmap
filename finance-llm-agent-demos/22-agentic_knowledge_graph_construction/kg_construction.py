"""严格按人工批准计划构建结构化与非结构化金融知识图谱。"""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from io import StringIO
from typing import Protocol

from core import Evidence, ExtractedFact
from structured_schema_proposal import (
    ConstructionPlan,
    CsvMappingRule,
    StructuredGraphPlan,
)
from unstructured_schema_proposal import UnstructuredGraphPlan


class UnstructuredExtractor(Protocol):
    def extract_unstructured_facts(
        self,
        text: str,
        source_name: str,
        existing_entities: list[str] | None = None,
        plan: UnstructuredGraphPlan | None = None,
    ) -> list[ExtractedFact]: ...


@dataclass(frozen=True)
class DomainEntity:
    label: str
    unique_key: str
    unique_value: str
    properties: dict[str, str]
    source_name: str
    row_number: int


@dataclass(frozen=True)
class DomainRelationship:
    relationship_type: str
    source_label: str
    source_key: str
    source_property: str
    target_label: str
    target_key: str
    target_property: str
    properties: dict[str, str]
    source_name: str
    row_number: int


@dataclass(frozen=True)
class MarkdownChunk:
    text: str
    index: int
    title: str


@dataclass(frozen=True)
class EmbeddedChunk:
    source_name: str
    index: int
    title: str
    text: str
    embedding: list[float]


class LocalHashEmbedder:
    """无需额外服务的可重复向量器，用于教学环境保留 Chunk/Embedding 链路。"""

    def __init__(self, dimensions: int = 64) -> None:
        if dimensions < 8:
            raise ValueError("Embedding 维度至少为 8。")
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dimensions] += 1.0
        magnitude = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / magnitude for value in vector]


@dataclass
class DomainConstructionBatch:
    entities: list[DomainEntity] = field(default_factory=list)
    relationships: list[DomainRelationship] = field(default_factory=list)


def build_domain_records(
    payloads: dict[str, bytes], plan: ConstructionPlan
) -> DomainConstructionBatch:
    """先生成领域节点、再生成关系；完整保留唯一键及节点/关系属性。"""
    if not plan.approved_by:
        raise ValueError("领域图施工前必须批准 construction plan。")
    batch = DomainConstructionBatch()
    # 先物化所有节点记录，确保关系写入时两端节点已经存在。
    for rule in plan.nodes.values():
        if rule.source_file not in payloads:
            raise ValueError(f"施工计划引用了未批准文件：{rule.source_file}")
        reader = csv.DictReader(StringIO(payloads[rule.source_file].decode("utf-8-sig")))
        required = {rule.unique_column_name, *rule.properties}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{rule.source_file} 缺少字段：{', '.join(sorted(missing))}")
        for row_number, row in enumerate(reader, start=2):
            value = (row.get(rule.unique_column_name) or "").strip()
            if not value:
                raise ValueError(f"{rule.source_file} 第 {row_number} 行唯一键为空。")
            batch.entities.append(
                DomainEntity(
                    rule.label,
                    rule.unique_column_name,
                    value,
                    {key: (row.get(key) or "").strip() for key in rule.properties},
                    rule.source_file,
                    row_number,
                )
            )
    # 关系文件可与节点文件分离，通过计划中批准的外键/唯一键完成连接。
    for rule in plan.relationships.values():
        if rule.source_file not in payloads:
            raise ValueError(f"施工计划引用了未批准文件：{rule.source_file}")
        reader = csv.DictReader(StringIO(payloads[rule.source_file].decode("utf-8-sig")))
        required = {rule.from_node_column, rule.to_node_column, *rule.properties}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{rule.source_file} 缺少字段：{', '.join(sorted(missing))}")
        from_key = rule.from_node_key or plan.nodes[rule.from_node_label].unique_column_name
        to_key = rule.to_node_key or plan.nodes[rule.to_node_label].unique_column_name
        for row_number, row in enumerate(reader, start=2):
            source = (row.get(rule.from_node_column) or "").strip()
            target = (row.get(rule.to_node_column) or "").strip()
            if not source or not target:
                raise ValueError(f"{rule.source_file} 第 {row_number} 行关系连接键为空。")
            batch.relationships.append(
                DomainRelationship(
                    rule.relationship_type,
                    rule.from_node_label,
                    source,
                    from_key,
                    rule.to_node_label,
                    target,
                    to_key,
                    {key: (row.get(key) or "").strip() for key in rule.properties},
                    rule.source_file,
                    row_number,
                )
            )
    return batch


def split_markdown(text: str, delimiter_pattern: str = r"(?m)^---\s*$") -> list[MarkdownChunk]:
    """保留原自定义 Markdown Loader/TextSplitter 的文档标题和块序号。"""
    title_match = re.search(r"(?m)^#\s+(.+)$", text)
    title = title_match.group(1).strip() if title_match else "Untitled"
    parts = [part.strip() for part in re.split(delimiter_pattern, text) if part.strip()]
    return [MarkdownChunk(part, index, title) for index, part in enumerate(parts)]


def build_markdown_records(
    payloads: dict[str, bytes], embedder: LocalHashEmbedder | None = None
) -> list[EmbeddedChunk]:
    """加载 Markdown、保留标题和块序号，并为每个块生成可检索向量。"""
    # 默认本地哈希向量无需外部模型，演示环境也能稳定复现检索结果。
    encoder = embedder or LocalHashEmbedder()
    records = []
    for name, content in payloads.items():
        if not name.lower().endswith(".md"):
            continue
        for chunk in split_markdown(content.decode("utf-8-sig")):
            records.append(
                EmbeddedChunk(name, chunk.index, chunk.title, chunk.text, encoder.embed(chunk.text))
            )
    return records


def normalize_key(label: str, key: str) -> str:
    """标准化属性名，用于匹配抽取实体与领域节点的候选连接键。"""
    normalized = key.strip().lower()
    normalized = re.sub(rf"^{re.escape(label.lower())}[_\s]*", "", normalized)
    return re.sub(r"\s+", "_", normalized)


def correlate_entity_and_domain_keys(
    label: str,
    entity_keys: list[str],
    domain_keys: list[str],
    similarity: float = 0.9,
) -> list[tuple[str, str, float]]:
    """为抽取实体属性和领域属性生成候选映射，按名称相似度降序返回。"""
    correlated = []
    for entity_key in entity_keys:
        for domain_key in domain_keys:
            score = SequenceMatcher(
                None, normalize_key(label, entity_key), normalize_key(label, domain_key)
            ).ratio()
            if score >= similarity:
                correlated.append((entity_key, domain_key, score))
    return sorted(correlated, key=lambda item: item[2], reverse=True)


def _facts_from_csv(name: str, content: bytes, rule: CsvMappingRule) -> list[ExtractedFact]:
    """执行兼容版 CSV 映射，并把原始行号写入 Evidence。"""
    reader = csv.DictReader(StringIO(content.decode("utf-8-sig")))
    columns = set(reader.fieldnames or [])
    missing = {rule.source_column, rule.target_column} - columns
    if missing:
        raise ValueError(f"{name} 缺少批准计划引用的字段：{', '.join(sorted(missing))}")
    facts = []
    for row_number, row in enumerate(reader, start=2):
        source = (row.get(rule.source_column) or "").strip()
        target = (row.get(rule.target_column) or "").strip()
        if not source or not target:
            raise ValueError(f"{name} 第 {row_number} 行的构图字段为空。")
        excerpt = f"{rule.source_column}={source}; {rule.target_column}={target}"
        facts.append(
            ExtractedFact(
                source,
                rule.source_type,
                rule.relation,
                target,
                rule.target_type,
                Evidence(name, f"第 {row_number} 行", excerpt, 1.0),
            )
        )
    return facts


def collect_facts_from_files(
    payloads: dict[str, bytes],
    structured_plan: StructuredGraphPlan | None,
    unstructured_plan: UnstructuredGraphPlan | None,
    extractor: UnstructuredExtractor | None,
) -> list[ExtractedFact]:
    """执行批准计划；存在相应文件时，未经批准的计划会被硬性拒绝。"""
    csv_files = {name: content for name, content in payloads.items() if name.lower().endswith(".csv")}
    markdown_files = {name: content for name, content in payloads.items() if name.lower().endswith(".md")}
    if csv_files and (structured_plan is None or not structured_plan.approved_by):
        raise ValueError("结构化数据构图前必须批准结构化 Schema。")
    if markdown_files and (unstructured_plan is None or not unstructured_plan.approved_by):
        raise ValueError("非结构化数据抽取前必须批准非结构化计划。")

    facts: list[ExtractedFact] = []
    if structured_plan:
        for rule in structured_plan.rules:
            if rule.file_name not in csv_files:
                raise ValueError(f"批准计划引用了未选择的文件：{rule.file_name}")
            facts.extend(_facts_from_csv(rule.file_name, csv_files[rule.file_name], rule))

    canonical_names = sorted({fact.source for fact in facts} | {fact.target for fact in facts})
    if markdown_files:
        if extractor is None:
            raise ValueError("处理 Markdown 需要非结构化事实抽取 Agent。")
        for name, content in markdown_files.items():
            text = content.decode("utf-8-sig")
            chunks = (
                split_markdown(text)
                if unstructured_plan and unstructured_plan.chunk_strategy in {"markdown_delimiter", "markdown_paragraph"}
                else [MarkdownChunk(text, 0, "Untitled")]
            )
            context = "\n".join(text.splitlines()[:5])
            for chunk in chunks:
                extracted = extractor.extract_unstructured_facts(
                    f"文件上下文：\n{context}\n\n当前块：\n{chunk.text}",
                    name,
                    canonical_names,
                    unstructured_plan,
                )
                # 块序号与模型返回的段落定位共同构成可复核证据位置。
                for fact in extracted:
                    facts.append(
                        ExtractedFact(
                            fact.source,
                            fact.source_type,
                            fact.relation,
                            fact.target,
                            fact.target_type,
                            Evidence(
                                fact.evidence.source_name,
                                f"块 {chunk.index + 1} · {fact.evidence.locator}",
                                fact.evidence.excerpt,
                                fact.evidence.confidence,
                            ),
                        )
                    )
    return facts
