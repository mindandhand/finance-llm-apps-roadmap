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
    StructuredGraphPlan,
    build_structured_critic_prompt,
    build_structured_schema_prompt,
    revise_structured_plan,
)
from tools import FileSample
from unstructured_schema_proposal import UnstructuredGraphPlan, build_unstructured_schema_prompt
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
