import csv
import tempfile
import unittest
from pathlib import Path

from core import (
    ApprovalRequiredError,
    Evidence,
    ExtractedFact,
    GraphPlan,
    GraphRetriever,
    InMemoryGraphStore,
    WorkflowSession,
    build_financial_schema_prompt,
    load_structured_facts,
)


class AgenticKnowledgeGraphTests(unittest.TestCase):
    def test_financial_prompt_keeps_schema_critic_and_provenance_contracts(self):
        prompt = build_financial_schema_prompt("追踪上市公司的供应链风险", ["companies.csv"])

        self.assertIn("节点类型", prompt)
        self.assertIn("关系类型", prompt)
        self.assertIn("批判", prompt)
        self.assertIn("来源", prompt)
        self.assertIn("置信度", prompt)

    def test_graph_write_is_blocked_until_human_approval(self):
        session = WorkflowSession("分析股权和风险事件")
        plan = GraphPlan.from_dict(
            {
                "node_types": ["Company", "RiskEvent"],
                "relationship_types": ["AFFECTED_BY"],
                "rationale": "连接公司与风险事件",
            }
        )
        session.propose(plan)

        with self.assertRaises(ApprovalRequiredError):
            session.begin_construction()

        session.review(["为 RiskEvent 增加 source_url 来源字段"])
        session.approve("研究员")
        session.begin_construction()
        self.assertEqual("constructing", session.phase)
        self.assertEqual("研究员", session.approved_by)

    def test_structured_csv_becomes_traceable_graph_facts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "relationships.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["source", "source_type", "relation", "target", "target_type"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "source": "华星科技",
                        "source_type": "Company",
                        "relation": "SUPPLIES",
                        "target": "远航汽车",
                        "target_type": "Company",
                    }
                )

            facts = load_structured_facts(csv_path)

        self.assertEqual(1, len(facts))
        self.assertEqual("SUPPLIES", facts[0].relation)
        self.assertEqual("relationships.csv", facts[0].evidence.source_name)
        self.assertIn("第 2 行", facts[0].evidence.locator)

    def test_structured_and_unstructured_facts_merge_with_evidence(self):
        store = InMemoryGraphStore()
        csv_fact = ExtractedFact(
            source="华星科技",
            source_type="Company",
            relation="SUPPLIES",
            target="远航汽车",
            target_type="Company",
            evidence=Evidence("供应链关系.csv", "第 2 行", "华星科技向远航汽车供货", 1.0),
        )
        report_fact = ExtractedFact(
            source="华星科技股份有限公司",
            source_type="Company",
            relation="EXPOSED_TO",
            target="芯片短缺",
            target_type="RiskEvent",
            evidence=Evidence("风险公告.md", "第 1 段", "公司可能受到芯片短缺影响", 0.91),
        )

        store.upsert_fact(csv_fact)
        store.upsert_fact(report_fact, aliases={"华星科技股份有限公司": "华星科技"})

        self.assertEqual(3, store.node_count)
        self.assertEqual(2, store.relationship_count)
        self.assertEqual(2, len(store.evidence))

    def test_graphrag_returns_reasoning_path_and_citations(self):
        store = InMemoryGraphStore()
        store.upsert_fact(
            ExtractedFact(
                "华星科技",
                "Company",
                "SUPPLIES",
                "远航汽车",
                "Company",
                Evidence("供应链关系.csv", "第 2 行", "华星科技向远航汽车供货", 1.0),
            )
        )
        store.upsert_fact(
            ExtractedFact(
                "华星科技",
                "Company",
                "EXPOSED_TO",
                "芯片短缺",
                "RiskEvent",
                Evidence("风险公告.md", "第 1 段", "华星科技面临芯片短缺风险", 0.91),
            )
        )

        result = GraphRetriever(store).retrieve("远航汽车会受到什么供应链风险？", max_hops=2)

        self.assertEqual(2, len(result.paths))
        self.assertEqual(["供应链关系.csv", "风险公告.md"], [item.source_name for item in result.citations])
        self.assertIn("远航汽车", result.context)
        self.assertIn("芯片短缺", result.context)


if __name__ == "__main__":
    unittest.main()
