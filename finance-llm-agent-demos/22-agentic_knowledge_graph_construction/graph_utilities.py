"""面向 Agent 的图数据库工具；底层持久化继续由 Neo4jGraphStore 提供。"""

from __future__ import annotations

from typing import Any

from core import ExtractedFact, RetrievalResult
from kg_construction import DomainConstructionBatch, EmbeddedChunk
from neo4j_store import Neo4jGraphStore


class GraphUtilities:
    """把连接检查、构图、检索和管理操作暴露为稳定工具边界。"""

    def __init__(self, store: Neo4jGraphStore) -> None:
        self.store = store

    def health(self) -> dict[str, str]:
        self.store.verify_connectivity()
        return {"status": "success", "message": "Neo4j is ready"}

    def construct(self, facts: list[ExtractedFact]) -> int:
        return self.store.upsert_facts(facts)

    def construct_domain_graph(self, batch: DomainConstructionBatch) -> int:
        return self.store.upsert_domain_batch(batch)

    def store_chunks(self, chunks: list[EmbeddedChunk]) -> int:
        return self.store.upsert_chunks(chunks)

    def correlate_entities(
        self, label: str, entity_key: str, domain_key: str, similarity: float = 0.9
    ) -> int:
        return self.store.correlate_extracted_entities(
            label, entity_key, domain_key, similarity
        )

    def extracted_entity_labels(self) -> list[str]:
        return self.store.find_extracted_entity_labels()

    def extracted_entity_keys(self, label: str) -> list[str]:
        return self.store.find_extracted_entity_keys(label)

    def domain_keys(self, label: str) -> list[str]:
        return self.store.find_domain_keys(label)

    def retrieve(self, question: str, strategy: str = "multi_hop", max_hops: int = 2) -> RetrievalResult:
        if strategy not in {"multi_hop", "direct"}:
            raise ValueError(f"不支持的 GraphRAG 检索策略：{strategy}")
        graph_result = self.store.retrieve(question, 1 if strategy == "direct" else max_hops)
        chunks = self.store.retrieve_chunks(question)
        if not chunks:
            return graph_result
        paths = [*graph_result.paths, *[f"文档证据：{item.source_name} · {item.locator}" for item in chunks]]
        citations = [*graph_result.citations, *chunks]
        context = "\n".join(
            f"[{index}] {path}；证据：{evidence.excerpt}"
            for index, (path, evidence) in enumerate(zip(paths, citations), start=1)
        )
        return RetrievalResult(paths, citations, context)

    def stats(self) -> dict[str, int]:
        return self.store.stats()

    def clear(self, confirmation: str) -> None:
        self.store.clear_graph(confirmation)

    def send_query(self, query: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        """通用只读/管理工具边界，返回 Agent 可消费的普通 Python 数据。"""
        try:
            with self.store.driver.session() as session:
                rows = [dict(row) for row in session.run(query, **(parameters or {}))]
            return {"status": "success", "query_result": rows}
        except Exception as exc:
            return {"status": "error", "error_message": str(exc)}

    def neo4j_version(self) -> dict[str, Any]:
        return self.send_query(
            "CALL dbms.components() YIELD name, versions RETURN name, versions"
        )

    def apoc_version(self) -> dict[str, Any]:
        return self.send_query("RETURN apoc.version() AS version")

    def drop_indexes_and_constraints(self, confirmation: str) -> None:
        if confirmation != "确认删除索引和约束":
            raise ValueError("删除索引和约束需要输入：确认删除索引和约束")
        with self.store.driver.session() as session:
            constraints = [row["name"] for row in session.run("SHOW CONSTRAINTS YIELD name RETURN name")]
            indexes = [row["name"] for row in session.run("SHOW INDEXES YIELD name RETURN name")]
            for name in constraints:
                safe = self.store._identifier(name)
                session.run(f"DROP CONSTRAINT `{safe}` IF EXISTS")
            for name in indexes:
                safe = self.store._identifier(name)
                session.run(f"DROP INDEX `{safe}` IF EXISTS")
