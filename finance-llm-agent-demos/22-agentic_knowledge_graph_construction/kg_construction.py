"""严格按人工批准计划构建结构化与非结构化金融知识图谱。"""

from __future__ import annotations

import csv
from io import StringIO
from typing import Protocol

from core import Evidence, ExtractedFact
from structured_schema_proposal import CsvMappingRule, StructuredGraphPlan
from unstructured_schema_proposal import UnstructuredGraphPlan


class UnstructuredExtractor(Protocol):
    def extract_unstructured_facts(
        self,
        text: str,
        source_name: str,
        existing_entities: list[str] | None = None,
        plan: UnstructuredGraphPlan | None = None,
    ) -> list[ExtractedFact]: ...


def _facts_from_csv(name: str, content: bytes, rule: CsvMappingRule) -> list[ExtractedFact]:
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
            facts.extend(
                extractor.extract_unstructured_facts(
                    content.decode("utf-8-sig"), name, canonical_names, unstructured_plan
                )
            )
    return facts
