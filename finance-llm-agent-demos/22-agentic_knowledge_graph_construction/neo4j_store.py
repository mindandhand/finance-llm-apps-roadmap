"""Neo4j 持久化与可溯源 GraphRAG 检索。"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from neo4j import GraphDatabase

from core import Evidence, ExtractedFact, RetrievalResult
from kg_construction import (
    DomainConstructionBatch,
    DomainEntity,
    DomainRelationship,
    EmbeddedChunk,
    LocalHashEmbedder,
)


class Neo4jGraphStore:
    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        *,
        driver: Any | None = None,
    ) -> None:
        if driver is None:
            if not all((uri, user, password)):
                raise ValueError("连接 Neo4j 需要 uri、user 和 password。")
            driver = GraphDatabase.driver(uri, auth=(user, password))
        self.driver = driver

    def close(self) -> None:
        self.driver.close()

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    @staticmethod
    def _hash(*parts: str) -> str:
        return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()

    def upsert_fact(self, fact: ExtractedFact) -> None:
        fact_id = self._hash(fact.source, fact.relation.upper(), fact.target)
        evidence_id = self._hash(
            fact_id,
            fact.evidence.source_name,
            fact.evidence.locator,
            fact.evidence.excerpt,
        )
        with self.driver.session() as session:
            session.run(
                """
                MERGE (source:Entity {name: $source})
                SET source.type = $source_type
                MERGE (target:Entity {name: $target})
                SET target.type = $target_type
                MERGE (f:Fact {id: $fact_id})
                SET f.relation = $relation
                MERGE (source)-[:FROM]->(f)
                MERGE (f)-[:TO]->(target)
                MERGE (e:Evidence {id: $evidence_id})
                SET e.source_name = $source_name,
                    e.locator = $locator,
                    e.excerpt = $excerpt,
                    e.confidence = $confidence
                MERGE (e)-[:SUPPORTS]->(f)
                """,
                source=fact.source,
                source_type=fact.source_type,
                target=fact.target,
                target_type=fact.target_type,
                relation=fact.relation.upper(),
                fact_id=fact_id,
                evidence_id=evidence_id,
                source_name=fact.evidence.source_name,
                locator=fact.evidence.locator,
                excerpt=fact.evidence.excerpt,
                confidence=fact.evidence.confidence,
            )

    def upsert_facts(self, facts: list[ExtractedFact]) -> int:
        for fact in facts:
            self.upsert_fact(fact)
        return len(facts)

    @staticmethod
    def _identifier(value: str) -> str:
        """标签和属性键不能作为普通参数，写入 Cypher 前仅允许安全标识符。"""
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError(f"不安全的 Neo4j 标识符：{value}")
        return value

    def create_uniqueness_constraint(self, label: str, unique_key: str) -> None:
        safe_label = self._identifier(label)
        safe_key = self._identifier(unique_key)
        constraint = self._identifier(f"{safe_label}_{safe_key}_constraint")
        with self.driver.session() as session:
            session.run(
                f"CREATE CONSTRAINT `{constraint}` IF NOT EXISTS "
                f"FOR (n:`{safe_label}`) REQUIRE n.`{safe_key}` IS UNIQUE"
            )

    def upsert_domain_entity(self, entity: DomainEntity) -> None:
        label = self._identifier(entity.label)
        key = self._identifier(entity.unique_key)
        with self.driver.session() as session:
            session.run(
                f"MERGE (n:`{label}` {{`{key}`: $unique_value}}) "
                "SET n += $properties, n._source_name = $source_name, n._source_row = $source_row",
                unique_value=entity.unique_value,
                properties=entity.properties,
                source_name=entity.source_name,
                source_row=entity.row_number,
            )

    def upsert_domain_relationship(self, relationship: DomainRelationship) -> None:
        source_label = self._identifier(relationship.source_label)
        source_property = self._identifier(relationship.source_property)
        target_label = self._identifier(relationship.target_label)
        target_property = self._identifier(relationship.target_property)
        relation = self._identifier(relationship.relationship_type)
        with self.driver.session() as session:
            session.run(
                f"MATCH (source:`{source_label}` {{`{source_property}`: $source_key}}), "
                f"(target:`{target_label}` {{`{target_property}`: $target_key}}) "
                f"MERGE (source)-[r:`{relation}`]->(target) "
                "SET r += $properties, r._source_name = $source_name, r._source_row = $source_row",
                source_key=relationship.source_key,
                target_key=relationship.target_key,
                properties=relationship.properties,
                source_name=relationship.source_name,
                source_row=relationship.row_number,
            )

    def upsert_domain_batch(self, batch: DomainConstructionBatch) -> int:
        constraints = {(entity.label, entity.unique_key) for entity in batch.entities}
        for label, key in sorted(constraints):
            self.create_uniqueness_constraint(label, key)
        for entity in batch.entities:
            self.upsert_domain_entity(entity)
        for relationship in batch.relationships:
            self.upsert_domain_relationship(relationship)
        return len(batch.entities) + len(batch.relationships)

    def upsert_chunks(self, chunks: list[EmbeddedChunk]) -> int:
        for chunk in chunks:
            chunk_id = self._hash(chunk.source_name, str(chunk.index), chunk.text)
            with self.driver.session() as session:
                session.run(
                    """
                    MERGE (chunk:DocumentChunk {id: $chunk_id})
                    SET chunk.source_name = $source_name, chunk.chunk_index = $chunk_index,
                        chunk.title = $title, chunk.text = $text, chunk.embedding = $embedding
                    """,
                    chunk_id=chunk_id,
                    source_name=chunk.source_name,
                    chunk_index=chunk.index,
                    title=chunk.title,
                    text=chunk.text,
                    embedding=chunk.embedding,
                )
        return len(chunks)

    def correlate_extracted_entities(
        self, label: str, entity_key: str, domain_key: str
    ) -> int:
        """连接抽取 Entity 与领域节点；标准化后的精确值匹配可重复执行。"""
        safe_label = self._identifier(label)
        safe_entity_key = self._identifier(entity_key)
        safe_domain_key = self._identifier(domain_key)
        with self.driver.session() as session:
            row = session.run(
                f"""
                MATCH (entity:Entity), (domain:`{safe_label}`)
                WHERE entity.type = $label
                  AND toLower(trim(toString(entity.`{safe_entity_key}`))) =
                      toLower(trim(toString(domain.`{safe_domain_key}`)))
                MERGE (entity)-[r:CORRESPONDS_TO]->(domain)
                RETURN count(r) AS relationship_count
                """,
                label=label,
            ).single()
        return int(row["relationship_count"]) if row else 0

    def retrieve_chunks(self, question: str, top_k: int = 5) -> list[Evidence]:
        """对已保存的 Chunk embedding 做余弦检索，补充图路径之外的原文证据。"""
        query_vector = LocalHashEmbedder().embed(question)
        with self.driver.session() as session:
            rows = [
                dict(row)
                for row in session.run(
                    """
                    MATCH (chunk:DocumentChunk)
                    RETURN chunk.source_name AS source_name, chunk.chunk_index AS chunk_index,
                           chunk.text AS text, chunk.embedding AS embedding
                    """
                )
            ]
        scored = []
        for row in rows:
            embedding = [float(value) for value in row.get("embedding") or []]
            if len(embedding) != len(query_vector):
                continue
            score = sum(left * right for left, right in zip(query_vector, embedding))
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            Evidence(
                str(row["source_name"]),
                f"块 {int(row['chunk_index']) + 1}",
                str(row["text"]),
                max(0.0, min(1.0, score)),
            )
            for score, row in scored[:top_k]
            if score > 0
        ]

    def retrieve(self, question: str, max_hops: int = 2) -> RetrievalResult:
        terms = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", question)
        terms = list(dict.fromkeys(term for term in terms if len(term.strip()) >= 2))
        max_depth = min(6, max(2, int(max_hops) * 2))
        with self.driver.session() as session:
            rows = session.run(
                """
                MATCH (seed:Entity)
                WHERE any(term IN $terms WHERE
                    toLower(seed.name) CONTAINS toLower(term)
                    OR toLower(term) CONTAINS toLower(seed.name))
                MATCH path = (seed)-[*1..6]-(f:Fact)
                WHERE length(path) <= $max_depth
                MATCH (source:Entity)-[:FROM]->(f)-[:TO]->(target:Entity)
                MATCH (e:Evidence)-[:SUPPORTS]->(f)
                RETURN DISTINCT source.name AS source,
                       f.relation AS relation,
                       target.name AS target,
                       e.source_name AS source_name,
                       e.locator AS locator,
                       e.excerpt AS excerpt,
                       e.confidence AS confidence
                LIMIT 30
                """,
                terms=terms or [question.strip()],
                max_depth=max_depth,
            )
            records = [dict(row) for row in rows]

        paths = [f"{row['source']} -[{row['relation']}]-> {row['target']}" for row in records]
        citations = [
            Evidence(
                source_name=row["source_name"],
                locator=row["locator"],
                excerpt=row["excerpt"],
                confidence=float(row["confidence"]),
            )
            for row in records
        ]
        context = "\n".join(
            f"[{index}] {path}；证据：{citation.excerpt}（{citation.source_name}，{citation.locator}）"
            for index, (path, citation) in enumerate(zip(paths, citations), start=1)
        )
        return RetrievalResult(paths, citations, context)

    def stats(self) -> dict[str, int]:
        with self.driver.session() as session:
            row = session.run(
                """
                MATCH (n)
                RETURN count(CASE WHEN n:Entity THEN 1 END) AS entities,
                       count(CASE WHEN n:Fact THEN 1 END) AS facts,
                       count(CASE WHEN n:Evidence THEN 1 END) AS evidence
                """
            ).single()
        return dict(row) if row else {"entities": 0, "facts": 0, "evidence": 0}

    def clear_graph(self, confirmation: str) -> None:
        if confirmation != "确认清空图谱":
            raise ValueError("清空图谱需要输入：确认清空图谱")
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
