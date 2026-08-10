"""Neo4j 持久化与可溯源 GraphRAG 检索。"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from neo4j import GraphDatabase

from core import Evidence, ExtractedFact, RetrievalResult


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
