import unittest

from langgraph.types import Command

from core import GraphPlan
from workflow import build_construction_workflow


class AgenticWorkflowTests(unittest.TestCase):
    def test_workflow_interrupts_before_write_and_resumes_after_approval(self):
        writes = []

        graph = build_construction_workflow(
            propose_plan=lambda goal, files: GraphPlan(
                ["Company", "RiskEvent"], ["AFFECTED_BY"], f"{goal}:{len(files)}"
            ),
            review_plan=lambda goal, plan: ["已检查来源和关系方向"],
            construct_graph=lambda state: writes.append(state["approved_by"]) or 3,
        )
        config = {"configurable": {"thread_id": "workflow-test"}}

        pending = graph.invoke(
            {
                "goal": "追踪供应链风险",
                "selected_files": ["relationships.csv", "risk_report.md"],
                "plan": {},
                "review_findings": [],
                "approved": False,
                "approved_by": "",
                "status": "new",
                "written_facts": 0,
            },
            config=config,
        )

        self.assertEqual([], writes)
        self.assertEqual("awaiting_approval", pending["status"])
        self.assertIn("__interrupt__", pending)
        self.assertEqual("Company", pending["plan"]["node_types"][0])

        completed = graph.invoke(
            Command(resume={"approved": True, "reviewer": "研究员"}),
            config=config,
        )

        self.assertEqual(["研究员"], writes)
        self.assertEqual("completed", completed["status"])
        self.assertEqual(3, completed["written_facts"])

    def test_rejection_finishes_without_graph_write(self):
        writes = []
        graph = build_construction_workflow(
            propose_plan=lambda goal, files: GraphPlan(["Company"], ["OWNS"], "股权关系"),
            review_plan=lambda goal, plan: [],
            construct_graph=lambda state: writes.append(True) or 1,
        )
        config = {"configurable": {"thread_id": "rejection-test"}}
        initial = {
            "goal": "分析股权",
            "selected_files": ["relationships.csv"],
            "plan": {},
            "review_findings": [],
            "approved": False,
            "approved_by": "",
            "status": "new",
            "written_facts": 0,
        }
        graph.invoke(initial, config=config)

        rejected = graph.invoke(
            Command(resume={"approved": False, "reviewer": "研究员"}),
            config=config,
        )

        self.assertEqual([], writes)
        self.assertEqual("rejected", rejected["status"])


if __name__ == "__main__":
    unittest.main()
