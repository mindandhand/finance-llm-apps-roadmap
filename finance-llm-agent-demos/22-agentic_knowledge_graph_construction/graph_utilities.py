"""面向 Agent 的图数据库工具；底层持久化继续由 Neo4jGraphStore 提供。"""

from __future__ import annotations

from core import ExtractedFact, RetrievalResult
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

    def retrieve(self, question: str, strategy: str = "multi_hop", max_hops: int = 2) -> RetrievalResult:
        if strategy not in {"multi_hop", "direct"}:
            raise ValueError(f"不支持的 GraphRAG 检索策略：{strategy}")
        return self.store.retrieve(question, 1 if strategy == "direct" else max_hops)

    def stats(self) -> dict[str, int]:
        return self.store.stats()

    def clear(self, confirmation: str) -> None:
        self.store.clear_graph(confirmation)
