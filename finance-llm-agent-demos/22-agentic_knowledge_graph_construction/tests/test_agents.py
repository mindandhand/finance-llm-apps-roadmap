import unittest

from agents import AgentService, parse_json_response


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


if __name__ == "__main__":
    unittest.main()
