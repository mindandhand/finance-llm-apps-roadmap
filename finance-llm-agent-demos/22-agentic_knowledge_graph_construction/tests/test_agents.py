import unittest

from agents import AgentService, parse_json_response
from tools import FileSample


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        return next(self.responses)


class AgentServiceTests(unittest.TestCase):
    def test_parse_json_response_accepts_markdown_fence(self):
        value = parse_json_response('```json\n{"findings": ["保留来源"]}\n```')
        self.assertEqual(["保留来源"], value["findings"])

    def test_unstructured_extraction_keeps_paragraph_and_confidence(self):
        client = FakeClient(
            [
                '{"facts": [{"source": "华星科技", "source_type": "Company", '
                '"relation": "EXPOSED_TO", "target": "芯片短缺", '
                '"target_type": "RiskEvent", "paragraph": 2, '
                '"excerpt": "芯片短缺可能影响交付", "confidence": 0.88}]}'
            ]
        )

        facts = AgentService(client).extract_unstructured_facts(
            "# 风险公告\n\n业务正常。\n\n芯片短缺可能影响交付。", "风险公告.md"
        )

        self.assertEqual(1, len(facts))
        self.assertEqual("第 2 段", facts[0].evidence.locator)
        self.assertEqual(0.88, facts[0].evidence.confidence)
        self.assertIn("不得补写", client.prompts[0])

    def test_answer_prompt_requires_inline_citation_and_refusal(self):
        client = FakeClient(["远航汽车可能受到芯片短缺影响 [1]。"])
        service = AgentService(client)

        answer = service.answer("有什么风险？", "[1] 华星科技 -[EXPOSED_TO]-> 芯片短缺")

        self.assertIn("[1]", answer)
        self.assertIn("证据不足", client.prompts[0])

    def test_file_suggestion_agent_returns_only_catalog_files(self):
        client = FakeClient(
            ['{"selected_files": ["relationships.csv", "unknown.csv"], "reasoning": "覆盖关系和风险"}']
        )

        suggestion = AgentService(client).suggest_files(
            "追踪风险", ["relationships.csv", "risk_report.md"]
        )

        self.assertEqual(["relationships.csv"], suggestion["selected_files"])
        self.assertEqual("覆盖关系和风险", suggestion["reasoning"])
        self.assertIn("候选文件目录", client.prompts[0])

    def test_conversational_agents_preserve_all_original_stages(self):
        client = FakeClient(
            [
                '{"needs_clarification": false, "question": "", "kind_of_graph": "A股风险图谱", "graph_description": "追踪风险"}',
                '{"sample_files": ["companies.csv"]}',
                '{"selected_files": ["companies.csv"], "reasoning": "公司主数据"}',
                '{"nodes": {"Company": {"source_file": "companies.csv", "label": "Company", '
                '"unique_column_name": "company_code", "properties": ["company_name"]}}, "relationships": {}}',
                '{"findings": []}',
                '{"entity_types": ["Company", "RiskEvent"]}',
                '{"fact_types": [{"subject_label": "Company", "predicate_label": "EXPOSED_TO", '
                '"object_label": "RiskEvent", "description": "风险暴露"}]}',
                '{"strategy": "multi_hop"}',
            ]
        )
        service = AgentService(client)
        catalog = {
            "companies.csv": FileSample(
                "companies.csv", "csv", ["company_code", "company_name"], "600001,远航汽车", 40
            )
        }

        goal = service.perceive_goal_conversation(
            [{"role": "user", "content": "分析公司风险"}], []
        )
        suggestion = service.suggest_files_conversation(goal, catalog, [])
        plan = service.propose_construction_plan(goal, catalog, [])
        findings = service.review_construction_plan(goal, plan)
        entities = service.propose_entity_types_conversation(goal, catalog, ["Company"], [])
        facts = service.propose_fact_types_conversation(goal, entities, [])
        strategy = service.select_retrieval_strategy("风险如何向下游传导？")

        self.assertEqual(["companies.csv"], suggestion["selected_files"])
        self.assertEqual("company_code", plan.nodes["Company"].unique_column_name)
        self.assertEqual([], findings)
        self.assertEqual(["Company", "RiskEvent"], entities)
        self.assertEqual("EXPOSED_TO", facts[0].predicate_label)
        self.assertEqual("multi_hop", strategy)
        self.assertIn("按需采样结果", client.prompts[2])


if __name__ == "__main__":
    unittest.main()
