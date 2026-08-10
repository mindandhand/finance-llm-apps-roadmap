import tempfile
import unittest
from pathlib import Path

from core import GraphPlan
from file_suggestion import build_file_catalog
from kg_construction import collect_facts_from_files
from structured_schema_proposal import CsvMappingRule, StructuredGraphPlan, revise_structured_plan
from unstructured_schema_proposal import UnstructuredGraphPlan
from user_intent import UserIntentSession


class PreservedWorkflowTests(unittest.TestCase):
    """保护原课程版的阶段边界，防止金融化改写缩减功能。"""

    def test_user_intent_requires_perception_before_explicit_approval(self):
        session = UserIntentSession()

        with self.assertRaises(ValueError):
            session.approve("研究员")

        session.set_perceived_goal("上市公司风险图谱", "追踪供应链风险的传导路径")
        approved = session.approve("研究员")

        self.assertEqual("上市公司风险图谱", approved.kind_of_graph)
        self.assertEqual("研究员", session.approved_by)
        self.assertEqual("approved", session.phase)

    def test_file_catalog_samples_csv_columns_and_markdown_content(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "companies.csv").write_text(
                "company_code,company_name\n600001,远航汽车\n", encoding="utf-8"
            )
            (root / "risk.md").write_text(
                "# 风险公告\n\n芯片短缺可能影响交付。", encoding="utf-8"
            )

            catalog = build_file_catalog(root)

        self.assertEqual(["company_code", "company_name"], catalog["companies.csv"].columns)
        self.assertIn("远航汽车", catalog["companies.csv"].sample)
        self.assertIn("芯片短缺", catalog["risk.md"].sample)

    def test_critic_findings_are_applied_before_structured_plan_approval(self):
        initial = StructuredGraphPlan(
            rules=[
                CsvMappingRule(
                    file_name="holdings.csv",
                    source_column="shareholder",
                    source_type="Shareholder",
                    relation="OWNS",
                    target_column="company",
                    target_type="Company",
                )
            ],
            rationale="构建股权关系",
        )

        revised = revise_structured_plan(
            initial,
            {
                "rules": [
                    {
                        **initial.rules[0].as_dict(),
                        "relation": "HOLDS_SHARES_IN",
                    }
                ],
                "rationale": "消除 OWNS 的方向歧义",
            },
            ["OWNS 方向不清晰"],
        )

        self.assertEqual("HOLDS_SHARES_IN", revised.rules[0].relation)
        self.assertEqual(["OWNS 方向不清晰"], revised.resolved_findings)

    def test_structured_and_unstructured_plans_remain_independent(self):
        structured = StructuredGraphPlan(
            rules=[
                CsvMappingRule(
                    "relationships.csv", "supplier", "Company", "SUPPLIES", "customer", "Company"
                )
            ],
            rationale="供应链关系",
        )
        unstructured = UnstructuredGraphPlan(
            entity_types=["Company", "RiskEvent"],
            fact_types=["EXPOSED_TO"],
            chunk_strategy="markdown_paragraph",
            rationale="从公告抽取风险事实",
        )

        self.assertNotEqual(structured.as_dict(), unstructured.as_dict())
        self.assertEqual("markdown_paragraph", unstructured.chunk_strategy)

    def test_approved_mapping_plan_drives_non_standard_csv_construction(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "relationships.csv"
            csv_path.write_text(
                "supplier,customer,relation_note\n华星科技,远航汽车,核心供货\n",
                encoding="utf-8",
            )
            plan = StructuredGraphPlan(
                rules=[
                    CsvMappingRule(
                        csv_path.name,
                        "supplier",
                        "Company",
                        "SUPPLIES",
                        "customer",
                        "Company",
                    )
                ],
                rationale="批准后的字段映射",
                approved_by="研究员",
            )

            facts = collect_facts_from_files(
                {csv_path.name: csv_path.read_bytes()},
                structured_plan=plan,
                unstructured_plan=None,
                extractor=None,
            )

        self.assertEqual(1, len(facts))
        self.assertEqual("华星科技", facts[0].source)
        self.assertEqual("SUPPLIES", facts[0].relation)
        self.assertEqual("远航汽车", facts[0].target)

    def test_legacy_graph_plan_can_be_split_without_losing_types(self):
        legacy = GraphPlan(
            ["Company"],
            ["SUPPLIES"],
            "金融图谱",
            ["RiskEvent"],
            ["EXPOSED_TO"],
        )

        unstructured = UnstructuredGraphPlan.from_graph_plan(legacy)

        self.assertEqual(["RiskEvent"], unstructured.entity_types)
        self.assertEqual(["EXPOSED_TO"], unstructured.fact_types)


if __name__ == "__main__":
    unittest.main()
