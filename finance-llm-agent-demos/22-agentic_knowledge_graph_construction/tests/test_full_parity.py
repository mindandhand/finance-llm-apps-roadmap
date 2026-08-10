import tempfile
import unittest
from pathlib import Path

from file_suggestion import FileSuggestionSession
from helper import ConversationSession
from kg_construction import (
    build_domain_records,
    build_markdown_records,
    correlate_entity_and_domain_keys,
    normalize_key,
    split_markdown,
)
from structured_schema_proposal import (
    ConstructionPlan,
    NodeConstructionRule,
    RelationshipConstructionRule,
    validate_construction_plan,
    validate_construction_payloads,
)
from unstructured_schema_proposal import (
    EntityTypeSession,
    FactTypeDefinition,
    FactTypeSession,
)
from user_intent import IntentConversation
from workflow import build_parity_workflow

from langgraph.types import Command


class FullParityTests(unittest.TestCase):
    """保护原课程文件中的对话、工具和构图行为，而非只比较文件名。"""

    def test_intent_conversation_can_clarify_revise_reject_and_approve(self):
        conversation = IntentConversation()
        conversation.add_user_message("我想做公司图谱")
        conversation.ask_clarification("需要分析哪类公司关系？")
        conversation.add_user_message("上市公司的供应链风险传导")
        conversation.set_perceived_goal("上市公司风险图谱", "追踪供应商风险到上市公司的传导路径")

        conversation.reject_goal("还需要限定中国上市公司")
        self.assertEqual("clarifying", conversation.phase)
        self.assertIn("中国上市公司", conversation.feedback[-1])

        conversation.set_perceived_goal("A股供应链风险图谱", "追踪供应商风险到 A 股公司的传导路径")
        approved = conversation.approve_goal("研究员")

        self.assertEqual("A股供应链风险图谱", approved.kind_of_graph)
        self.assertEqual(4, len(conversation.messages))
        self.assertEqual("approved", conversation.phase)

    def test_file_suggestion_supports_on_demand_sampling_and_feedback_loop(self):
        session = FileSuggestionSession(
            {
                "companies.csv": "company_code,company_name\n600001,远航汽车\n".encode(),
                "risk.md": "# 风险公告\n\n芯片短缺。".encode(),
            }
        )

        sample = session.sample_file("companies.csv")
        session.set_suggested_files(["companies.csv"])
        session.reject("还需要公告证据")
        session.set_suggested_files(["companies.csv", "risk.md"])
        approved = session.approve("研究员")

        self.assertIn("远航汽车", sample.sample)
        self.assertEqual(["companies.csv", "risk.md"], approved)
        self.assertEqual(["还需要公告证据"], session.feedback)

    def test_structured_plan_keeps_nodes_properties_relationships_and_remove_tools(self):
        plan = ConstructionPlan()
        plan.propose_node(
            NodeConstructionRule(
                "companies.csv", "Company", "company_code", ["company_name", "industry"]
            )
        )
        plan.propose_relationship(
            RelationshipConstructionRule(
                "relationships.csv",
                "SUPPLIES",
                "Company",
                "supplier_code",
                "Company",
                "customer_code",
                ["annual_purchase_ratio"],
            )
        )
        removed = plan.remove_relationship("SUPPLIES")
        plan.propose_relationship(removed)

        self.assertEqual("company_code", plan.nodes["Company"].unique_column_name)
        self.assertEqual(["annual_purchase_ratio"], plan.relationships["SUPPLIES"].properties)

    def test_structured_plan_validates_columns_and_unique_identifier(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "companies.csv").write_text(
                "company_code,company_name\n600001,远航汽车\n600002,华星科技\n", encoding="utf-8"
            )
            plan = ConstructionPlan()
            plan.propose_node(NodeConstructionRule("companies.csv", "Company", "company_code", ["company_name"]))

            findings = validate_construction_plan(root, plan)

        self.assertEqual([], findings)

    def test_entity_and_fact_type_agents_have_separate_approval_states(self):
        entities = EntityTypeSession()
        entities.set_proposed(["Company", "RiskEvent"])
        approved_entities = entities.approve("研究员")
        facts = FactTypeSession(approved_entities)
        facts.add_proposed(FactTypeDefinition("Company", "EXPOSED_TO", "RiskEvent", "风险暴露"))

        self.assertIsNone(facts.approved_by)
        approved_facts = facts.approve("研究员")
        self.assertEqual("EXPOSED_TO", approved_facts[0].predicate_label)
        self.assertEqual("研究员", entities.approved_by)

    def test_domain_graph_imports_node_and_relationship_properties_from_business_csv(self):
        payloads = {
            "companies.csv": b"company_code,company_name,industry\n600001,FarSail Auto,Auto\n600002,Star Tech,Parts\n",
            "relationships.csv": b"supplier_code,customer_code,annual_purchase_ratio\n600002,600001,0.38\n",
        }
        plan = ConstructionPlan(
            nodes={
                "Company": NodeConstructionRule(
                    "companies.csv", "Company", "company_code", ["company_name", "industry"]
                )
            },
            relationships={
                "SUPPLIES": RelationshipConstructionRule(
                    "relationships.csv",
                    "SUPPLIES",
                    "Company",
                    "supplier_code",
                    "Company",
                    "customer_code",
                    ["annual_purchase_ratio"],
                    from_node_key="company_code",
                    to_node_key="company_code",
                )
            },
            approved_by="研究员",
        )

        batch = build_domain_records(payloads, plan)

        self.assertEqual(2, len(batch.entities))
        self.assertEqual("Auto", batch.entities[0].properties["industry"])
        self.assertEqual("0.38", batch.relationships[0].properties["annual_purchase_ratio"])
        self.assertEqual("600002", batch.relationships[0].source_key)

    def test_markdown_chunking_and_entity_key_correlation_are_preserved(self):
        chunks = split_markdown("# 公告\n\n第一段。\n\n---\n\n第二段。")
        correlated = correlate_entity_and_domain_keys(
            "Company", ["name", "companyName"], ["company_name", "company_code"], similarity=0.75
        )

        self.assertEqual(2, len(chunks))
        self.assertEqual("name", normalize_key("Company", "company name"))
        self.assertEqual(("name", "company_name"), correlated[0][:2])

    def test_markdown_embeddings_and_plan_checkpoint_round_trips(self):
        records = build_markdown_records(
            {"risk.md": "# 风险公告\n\n芯片短缺。\n\n---\n\n交付延期。".encode()}
        )
        plan = ConstructionPlan(
            nodes={
                "Company": NodeConstructionRule(
                    "companies.csv", "Company", "company_code", ["company_name"]
                )
            },
            approved_by="研究员",
        )
        restored = ConstructionPlan.from_dict(plan.as_dict())
        findings = validate_construction_payloads(
            {"companies.csv": b"company_code,company_name\n600001,FarSail Auto\n"}, restored
        )

        self.assertEqual(2, len(records))
        self.assertEqual(64, len(records[0].embedding))
        self.assertAlmostEqual(1.0, sum(value * value for value in records[0].embedding), places=6)
        self.assertEqual("研究员", restored.approved_by)
        self.assertEqual([], findings)

    def test_conversation_session_preserves_messages_and_shared_state(self):
        session = ConversationSession()
        session.add("user", "分析供应链风险")
        session.add("assistant", "请确认研究范围")
        session.state["perceived_user_goal"] = {"kind_of_graph": "风险图谱"}

        self.assertEqual("请确认研究范围", session.messages[-1].content)
        self.assertIn("perceived_user_goal", session.snapshot()["state"])

    def test_parity_workflow_keeps_five_independent_approval_gates(self):
        constructed = []
        plan = ConstructionPlan(
            nodes={
                "Company": NodeConstructionRule(
                    "companies.csv", "Company", "company_code", ["company_name"]
                )
            }
        )
        graph = build_parity_workflow(
            perceive_goal=lambda messages, feedback: {
                "needs_clarification": False,
                "kind_of_graph": "A股风险图谱",
                "graph_description": "追踪供应链风险",
            },
            suggest_files=lambda goal, files, feedback: {
                "selected_files": ["companies.csv", "risk.md"],
                "reasoning": "结构化公司与公告证据",
            },
            propose_construction_plan=lambda goal, files, feedback: plan,
            review_construction_plan=lambda goal, files, proposed: [],
            propose_entity_types=lambda goal, files, well_known_types, feedback: ["Company", "RiskEvent"],
            propose_fact_types=lambda goal, entities, feedback: [
                FactTypeDefinition("Company", "EXPOSED_TO", "RiskEvent", "风险暴露")
            ],
            construct_graph=lambda state: constructed.append(state) or 3,
        )
        config = {"configurable": {"thread_id": "parity-five-gates"}}
        pending = graph.invoke(
            {"messages": [{"role": "user", "content": "分析公司风险"}], "available_files": ["companies.csv", "risk.md"]},
            config=config,
        )

        expected = [
            "awaiting_goal_approval",
            "awaiting_file_approval",
            "awaiting_structured_approval",
            "awaiting_entity_approval",
            "awaiting_fact_approval",
        ]
        for index, status in enumerate(expected):
            self.assertEqual(status, pending["status"])
            if index < len(expected) - 1:
                pending = graph.invoke(
                    Command(resume={"approved": True, "reviewer": "研究员"}), config=config
                )

        completed = graph.invoke(
            Command(resume={"approved": True, "reviewer": "研究员"}), config=config
        )
        self.assertEqual("completed", completed["status"])
        self.assertEqual("研究员", constructed[0]["construction_plan"].approved_by)
        self.assertEqual("研究员", constructed[0]["entity_session"].approved_by)
        self.assertEqual("研究员", constructed[0]["fact_session"].approved_by)

    def test_parity_workflow_resumes_after_clarification_answer(self):
        calls = []

        def perceive(messages, feedback):
            calls.append(messages)
            if len(messages) == 1:
                return {
                    "needs_clarification": True,
                    "question": "需要分析哪类公司关系？",
                }
            return {
                "needs_clarification": False,
                "kind_of_graph": "供应链图谱",
                "graph_description": "分析上市公司的供应链风险传导关系",
            }

        graph = build_parity_workflow(
            perceive_goal=perceive,
            suggest_files=lambda *_: {"selected_files": ["companies.csv"], "reasoning": "实体数据"},
            propose_construction_plan=lambda *_: ConstructionPlan().propose_node(
                NodeConstructionRule("companies.csv", "Company", "company_code", ["company_name"])
            ),
            review_construction_plan=lambda *_: [],
            propose_entity_types=lambda *_: ["Company"],
            propose_fact_types=lambda *_: [
                FactTypeDefinition("Company", "SUPPLIES", "Company", "供应关系")
            ],
            construct_graph=lambda _: 0,
        )
        config = {"configurable": {"thread_id": "clarification-resume"}}
        pending = graph.invoke(
            {
                "messages": [{"role": "user", "content": "构建一个金融图谱"}],
                "available_files": ["companies.csv"],
                "status": "new",
            },
            config=config,
        )

        self.assertEqual("awaiting_clarification", pending["status"])
        resumed = graph.invoke(
            Command(resume={"message": "分析上市公司供应链"}), config=config
        )

        self.assertEqual("awaiting_goal_approval", resumed["status"])
        self.assertEqual("分析上市公司供应链", calls[-1][-1]["content"])


if __name__ == "__main__":
    unittest.main()
