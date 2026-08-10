"""DeepSeek 驱动的 Schema、批判、事实抽取与回答 Agent。"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

import requests

from core import (
    Evidence,
    ExtractedFact,
    GraphPlan,
    build_critic_prompt,
    build_financial_schema_prompt,
)
from file_suggestion import build_file_suggestion_prompt, validate_suggestion
from structured_schema_proposal import (
    ConstructionPlan,
    StructuredGraphPlan,
    build_structured_critic_prompt,
    build_structured_schema_prompt,
    revise_structured_plan,
)
from tools import FileSample
from unstructured_schema_proposal import (
    FactTypeDefinition,
    UnstructuredGraphPlan,
    build_unstructured_schema_prompt,
)
from user_intent import build_user_intent_prompt


def parse_json_response(content: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I | re.S)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("模型没有返回有效 JSON。")
    value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("模型 JSON 顶层必须是对象。")
    return value


class CompletionClient(Protocol):
    def complete(self, prompt: str) -> str: ...


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ) -> None:
        if not api_key.strip():
            raise ValueError("未配置 DEEPSEEK_API_KEY。")
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(self, prompt: str) -> str:
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
            timeout=120,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"DeepSeek 请求失败（HTTP {response.status_code}）：{response.text[:300]}")
        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("DeepSeek 返回格式不符合 chat completions 规范。") from exc


class AgentService:
    def __init__(self, client: CompletionClient) -> None:
        self.client = client

    def propose_plan(self, goal: str, files: list[str]) -> GraphPlan:
        value = parse_json_response(self.client.complete(build_financial_schema_prompt(goal, files)))
        return GraphPlan.from_dict(value)

    def perceive_goal(self, message: str) -> dict[str, str]:
        """理解研究意图，但不替用户执行批准动作。"""
        value = parse_json_response(self.client.complete(build_user_intent_prompt(message)))
        if value.get("needs_clarification"):
            question = str(value.get("question", "")).strip()
            raise ValueError(f"研究目标仍需澄清：{question or '请补充研究范围。'}")
        kind = str(value.get("kind_of_graph", "")).strip()
        description = str(value.get("graph_description", "")).strip()
        if not kind or not description:
            raise ValueError("意图 Agent 未返回完整的研究目标。")
        return {"kind_of_graph": kind, "graph_description": description}

    def perceive_goal_conversation(
        self, messages: list[dict[str, str]], feedback: list[str]
    ) -> dict[str, Any]:
        """完整意图对话：模型可以继续追问，不能自行执行批准。"""
        prompt = f"""你是金融知识图谱用例专家，负责与研究员共同明确图谱用途。
可建议的金融场景包括：上市公司供应链、股权穿透、关联交易、风险传导、欺诈账户网络和投资组合暴露。

用户目标必须包含：
- kind_of_graph：不超过 3 个词的图谱类型；
- graph_description：研究对象、关系范围和希望回答的问题。

对话历史：{messages}
用户对上一版理解的修改意见：{feedback or '暂无'}

如果研究对象、关系范围或预期问题仍不清楚，请提出一个具体澄清问题；
信息充分时只形成 perceived goal，必须等待用户另行批准。
只返回 JSON：
{{"needs_clarification": true, "question": "具体问题", "kind_of_graph": "", "graph_description": ""}}
或
{{"needs_clarification": false, "question": "", "kind_of_graph": "A股风险图谱", "graph_description": "..."}}
"""
        return parse_json_response(self.client.complete(prompt))

    def suggest_files_conversation(
        self,
        goal: dict[str, str],
        catalog: dict[str, FileSample],
        feedback: list[str],
    ) -> dict[str, Any]:
        """让文件 Agent 先决定采样对象，再根据工具结果形成建议。"""
        discovery = parse_json_response(
            self.client.complete(
                f"""你是金融知识图谱文件推荐 Agent。
批准目标：{goal}；候选文件：{list(catalog)}；用户反馈：{feedback or '暂无'}。
先判断哪些文件需要查看内容，不得猜测目录外文件。
只返回 JSON：{{"sample_files": ["需要采样的文件"]}}"""
            )
        )
        requested = [str(item) for item in discovery.get("sample_files", []) if str(item) in catalog]
        samples = [catalog[name].as_dict() for name in requested]
        result = parse_json_response(
            self.client.complete(
                f"""你是金融知识图谱文件推荐 Agent。
批准目标：{goal}
全部候选文件：{list(catalog)}
按需采样结果：{samples}
用户反馈：{feedback or '暂无'}
请设置 suggested files 并说明逐个文件的用途，等待用户批准，不得自行批准。
只返回 JSON：{{"selected_files": ["文件名"], "reasoning": "..."}}"""
            )
        )
        return validate_suggestion(result, catalog)

    def propose_construction_plan(
        self,
        goal: dict[str, str],
        catalog: dict[str, FileSample],
        feedback: list[str],
    ) -> ConstructionPlan:
        prompt = f"""你是金融 property graph 结构化 Schema Proposal Agent。
批准目标：{goal}
批准文件样本：{[sample.as_dict() for sample in catalog.values() if sample.kind == 'csv']}
Critic 或用户反馈：{feedback or '暂无'}

必须为实体文件生成节点施工规则：source_file、label、unique_column_name、properties；
必须为关系或外键生成关系施工规则：source_file、relationship_type、from/to 节点标签、
from/to 文件列、from/to 节点唯一键和关系 properties。所有批准 CSV 都要有用途，图必须连通。
只返回 JSON：
{{"nodes": {{"Company": {{"source_file": "companies.csv", "label": "Company",
"unique_column_name": "company_code", "properties": ["company_name"]}}}},
"relationships": {{"SUPPLIES": {{"source_file": "relationships.csv", "relationship_type": "SUPPLIES",
"from_node_label": "Company", "from_node_column": "supplier_code", "from_node_key": "company_code",
"to_node_label": "Company", "to_node_column": "customer_code", "to_node_key": "company_code",
"properties": ["annual_purchase_ratio"]}}}}}}
"""
        return ConstructionPlan.from_dict(parse_json_response(self.client.complete(prompt)))

    def review_construction_plan(
        self, goal: dict[str, str], plan: ConstructionPlan
    ) -> list[str]:
        value = parse_json_response(
            self.client.complete(
                f"""你是独立的金融 Schema Critic Agent。
批准目标：{goal}；施工计划：{plan.as_dict()}。
检查唯一键、字段、节点/关系方向、属性、文件覆盖、孤立节点和研究问题相关性。
只返回 JSON：{{"findings": []}}；没有问题时必须返回空数组。"""
            )
        )
        findings = value.get("findings", [])
        if not isinstance(findings, list):
            raise ValueError("Schema Critic findings 必须是数组。")
        return [str(item).strip() for item in findings if str(item).strip()]

    def propose_entity_types_conversation(
        self,
        goal: dict[str, str],
        catalog: dict[str, FileSample],
        well_known_types: list[str],
        feedback: list[str],
    ) -> list[str]:
        value = parse_json_response(
            self.client.complete(
                f"""你是金融命名实体 Schema Agent。批准目标：{goal}。
Markdown 样本：{[item.as_dict() for item in catalog.values() if item.kind == 'md']}。
领域图已有标签：{well_known_types}；用户反馈：{feedback or '暂无'}。
优先复用已有标签，再提议文本中确有必要的新实体类型，等待单独批准。
只返回 JSON：{{"entity_types": ["Company", "RiskEvent"]}}"""
            )
        )
        return [str(item).strip() for item in value.get("entity_types", []) if str(item).strip()]

    def propose_fact_types_conversation(
        self, goal: dict[str, str], approved_entities: list[str], feedback: list[str]
    ) -> list[FactTypeDefinition]:
        value = parse_json_response(
            self.client.complete(
                f"""你是金融事实类型 Agent。批准目标：{goal}；已批准实体：{approved_entities}；
用户反馈：{feedback or '暂无'}。每项事实必须明确 subject_label、predicate_label、object_label 和 description，
且主宾语只能引用已批准实体。等待用户独立批准事实类型。
只返回 JSON：{{"fact_types": [{{"subject_label": "Company", "predicate_label": "EXPOSED_TO",
"object_label": "RiskEvent", "description": "公司暴露于风险事件"}}]}}"""
            )
        )
        return [FactTypeDefinition.from_dict(item) for item in value.get("fact_types", [])]

    def suggest_files(
        self, goal: str, catalog: list[str] | dict[str, FileSample]
    ) -> dict[str, Any]:
        # 兼容旧调用；完整工作流会传入带表头和内容摘要的 FileSample。
        if isinstance(catalog, dict):
            value = parse_json_response(
                self.client.complete(build_file_suggestion_prompt(goal, catalog))
            )
            return validate_suggestion(value, catalog)
        prompt = f"""你是数据文件推荐 Agent。根据研究目标从候选文件目录中选择必要文件。
不得返回目录之外的文件；结构化关系与非结构化证据应在需要时同时覆盖。
研究目标：{goal}
候选文件目录：{', '.join(catalog)}
只返回 JSON：{{"selected_files": ["文件名"], "reasoning": "选择理由"}}
"""
        value = parse_json_response(self.client.complete(prompt))
        allowed = set(catalog)
        selected = [str(item) for item in value.get("selected_files", []) if str(item) in allowed]
        return {"selected_files": selected, "reasoning": str(value.get("reasoning", "")).strip()}

    def propose_structured_plan(
        self, goal: str, catalog: dict[str, FileSample]
    ) -> StructuredGraphPlan:
        value = parse_json_response(
            self.client.complete(build_structured_schema_prompt(goal, catalog))
        )
        return StructuredGraphPlan.from_dict(value)

    def review_structured_plan(self, goal: str, plan: StructuredGraphPlan) -> list[str]:
        value = parse_json_response(
            self.client.complete(build_structured_critic_prompt(goal, plan))
        )
        findings = value.get("findings", [])
        if not isinstance(findings, list):
            raise ValueError("结构化 Critic 的 findings 必须是数组。")
        return [str(item).strip() for item in findings if str(item).strip()]

    def revise_structured_plan(
        self, goal: str, plan: StructuredGraphPlan, findings: list[str]
    ) -> StructuredGraphPlan:
        prompt = f"""你是金融结构化 Schema Proposal Agent。
研究目标：{goal}
上一版计划：{plan.as_dict()}
Critic 意见：{findings}
请逐项解决意见并返回完整的替代计划。只返回与上一版相同结构的 JSON。
"""
        proposal = parse_json_response(self.client.complete(prompt))
        return revise_structured_plan(plan, proposal, findings)

    def propose_unstructured_plan(
        self, goal: str, catalog: dict[str, FileSample]
    ) -> UnstructuredGraphPlan:
        value = parse_json_response(
            self.client.complete(build_unstructured_schema_prompt(goal, catalog))
        )
        return UnstructuredGraphPlan.from_dict(value)

    def review_plan(self, goal: str, plan: GraphPlan) -> list[str]:
        value = parse_json_response(self.client.complete(build_critic_prompt(goal, plan)))
        findings = value.get("findings", [])
        if not isinstance(findings, list):
            raise ValueError("批判 Agent 的 findings 必须是数组。")
        return [str(item).strip() for item in findings if str(item).strip()]

    def extract_unstructured_facts(
        self,
        text: str,
        source_name: str,
        existing_entities: list[str] | None = None,
        plan: UnstructuredGraphPlan | None = None,
    ) -> list[ExtractedFact]:
        prompt = f"""你是金融事实抽取 Agent。请从 Markdown 文本中抽取可验证的实体关系。
每条事实必须包含 source、source_type、relation、target、target_type、paragraph、excerpt、confidence。
paragraph 是从 1 开始的段落编号；excerpt 必须来自原文，不得补写或推测；confidence 范围为 0 到 1。
批准的抽取计划：{plan.as_dict() if plan else '兼容模式：未提供独立计划'}。
实体链接要求：优先复用这些结构化图谱实体的标准名称：{', '.join(existing_entities or []) or '暂无'}。
只返回 JSON：{{"facts": [...]}}

文件：{source_name}
文本：
{text}
"""
        value = parse_json_response(self.client.complete(prompt))
        facts = []
        for item in value.get("facts", []):
            confidence = min(1.0, max(0.0, float(item["confidence"])))
            facts.append(
                ExtractedFact(
                    source=str(item["source"]).strip(),
                    source_type=str(item["source_type"]).strip(),
                    relation=str(item["relation"]).strip().upper(),
                    target=str(item["target"]).strip(),
                    target_type=str(item["target_type"]).strip(),
                    evidence=Evidence(
                        source_name=source_name,
                        locator=f"第 {int(item['paragraph'])} 段",
                        excerpt=str(item["excerpt"]).strip(),
                        confidence=confidence,
                    ),
                )
            )
        if plan:
            allowed_entities = set(plan.entity_types)
            allowed_relations = set(plan.fact_types)
            invalid = [
                fact
                for fact in facts
                if fact.source_type not in allowed_entities
                or fact.target_type not in allowed_entities
                or fact.relation not in allowed_relations
            ]
            if invalid:
                raise ValueError("模型抽取结果包含批准计划之外的实体类型或事实类型。")
        return facts

    def select_retrieval_strategy(self, question: str) -> str:
        """保留原 GraphRAG Agent 的工具选择职责，而不是固定一种检索。"""
        prompt = f"""你是金融 GraphRAG 检索路由 Agent。
问题：{question}
若问题只查询一个直接关系，选择 direct；若涉及影响路径、上下游或根因，选择 multi_hop。
只返回 JSON：{{"strategy": "direct"}}
"""
        value = parse_json_response(self.client.complete(prompt))
        strategy = str(value.get("strategy", "")).strip()
        if strategy not in {"direct", "multi_hop"}:
            raise ValueError("检索路由 Agent 返回了不支持的策略。")
        return strategy

    def answer(self, question: str, graph_context: str) -> str:
        prompt = f"""你是金融 GraphRAG 回答 Agent。只能依据给定的图路径和证据回答。
每个关键结论必须带对应的行内引用，例如 [1]。如果证据不足，请明确回答“证据不足”，不得使用常识补全。

问题：{question}
图路径与证据：
{graph_context or '没有检索到证据'}
"""
        return self.client.complete(prompt).strip()
