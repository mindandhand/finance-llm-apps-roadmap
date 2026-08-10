import unittest

from core import Evidence, ExtractedFact
from neo4j_store import Neo4jGraphStore
from kg_construction import (
    DomainConstructionBatch,
    DomainEntity,
    DomainRelationship,
    EmbeddedChunk,
)


class FakeResult:
    def __init__(self, rows=None, single_value=None):
        self.rows = rows or []
        self.single_value = single_value

    def __iter__(self):
        return iter(self.rows)

    def single(self):
        return self.single_value


class FakeSession:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def run(self, query, **parameters):
        self.calls.append((query, parameters))
        return next(self.results, FakeResult())


class FakeDriver:
    def __init__(self, session):
        self._session = session

    def session(self):
        return self._session

    def close(self):
        pass


class Neo4jGraphStoreTests(unittest.TestCase):
    def test_upsert_uses_fact_and_evidence_nodes_without_dynamic_cypher(self):
        session = FakeSession([FakeResult()])
        store = Neo4jGraphStore(driver=FakeDriver(session))
        fact = ExtractedFact(
            "华星科技",
            "Company",
            "SUPPLIES",
            "远航汽车",
            "Company",
            Evidence("relationships.csv", "第 2 行", "华星科技向远航汽车供货", 1.0),
        )

        store.upsert_fact(fact)

        query, parameters = session.calls[0]
        self.assertIn("MERGE (f:Fact", query)
        self.assertIn("MERGE (e:Evidence", query)
        self.assertNotIn("SUPPLIES", query)
        self.assertEqual("SUPPLIES", parameters["relation"])
        self.assertEqual(64, len(parameters["fact_id"]))

    def test_retrieve_returns_paths_and_evidence(self):
        rows = [
            {
                "source": "华星科技",
                "relation": "EXPOSED_TO",
                "target": "芯片短缺",
                "source_name": "风险公告.md",
                "locator": "第 2 段",
                "excerpt": "芯片短缺可能影响交付",
                "confidence": 0.88,
            }
        ]
        session = FakeSession([FakeResult(rows)])
        store = Neo4jGraphStore(driver=FakeDriver(session))

        result = store.retrieve("华星科技面临什么风险？", max_hops=2)

        self.assertEqual(["华星科技 -[EXPOSED_TO]-> 芯片短缺"], result.paths)
        self.assertEqual("风险公告.md", result.citations[0].source_name)
        self.assertIn("[1]", result.context)
        self.assertEqual(4, session.calls[0][1]["max_depth"])

    def test_domain_batch_creates_constraint_nodes_and_relationship_properties(self):
        session = FakeSession([FakeResult(), FakeResult(), FakeResult()])
        store = Neo4jGraphStore(driver=FakeDriver(session))
        batch = DomainConstructionBatch(
            entities=[DomainEntity("Company", "company_code", "600001", {"company_name": "远航汽车"}, "companies.csv", 2)],
            relationships=[
                DomainRelationship(
                    "SUPPLIES", "Company", "600002", "company_code", "Company", "600001",
                    "company_code", {"ratio": "0.38"}, "relationships.csv", 2
                )
            ],
        )

        written = store.upsert_domain_batch(batch)

        self.assertEqual(2, written)
        self.assertIn("CREATE CONSTRAINT", session.calls[0][0])
        self.assertEqual({"company_name": "远航汽车"}, session.calls[1][1]["properties"])
        self.assertEqual({"ratio": "0.38"}, session.calls[2][1]["properties"])

    def test_chunks_are_persisted_with_embeddings(self):
        session = FakeSession([FakeResult()])
        store = Neo4jGraphStore(driver=FakeDriver(session))

        count = store.upsert_chunks([EmbeddedChunk("risk.md", 0, "风险公告", "芯片短缺", [0.1, 0.2])])

        self.assertEqual(1, count)
        self.assertIn("DocumentChunk", session.calls[0][0])
        self.assertEqual([0.1, 0.2], session.calls[0][1]["embedding"])

    def test_unsafe_dynamic_identifier_is_rejected(self):
        store = Neo4jGraphStore(driver=FakeDriver(FakeSession([])))

        with self.assertRaises(ValueError):
            store.create_uniqueness_constraint("Company`) MATCH (n)", "company_code")


if __name__ == "__main__":
    unittest.main()
