"""
Pydantic AI Agent、类型化检索工具和证据校验护栏。

这个文件是 11 号 demo 的“智能层”，负责三件事：

1. 定义模型最终必须返回的结构化数据：`Answer` 和 `Citation`。
2. 把向量库检索封装成 Pydantic AI 可调用的工具：`retrieve`。
3. 在模型回答前后都做校验，避免“没证据也回答”或“伪造引用”。

UI 在 `app.py`，资料入库和检索在 `rag.py`；这个文件只关心：
Agent 如何使用检索结果，以及回答是否可信。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_ai import Agent, RunContext

from rag import InMemoryVectorStore


DEFAULT_MIN_RELEVANCE = 0.2

# 统一的拒答文本。
# 只要检索分数不够、模型跳过工具、引用无效，都会返回这个结果。
REFUSAL_TEXT = (
    "已索引资料中没有足够证据回答这个问题。"
)

# Pydantic AI 使用 provider:model 格式表示模型。
# DeepSeek provider 的默认字符串会是：deepseek:deepseek-chat。
DEFAULT_DEEPSEEK_MODEL_ID = "deepseek-chat"


class Citation(BaseModel):
    """把回答连接到某个资料分块的精确引用。"""

    # source 和 chunk_id 必须原样来自 retrieve 工具返回结果。
    # 这样后续可以回到向量库里定位原始分块，验证 quoted_span 是否真实存在。
    source: str = Field(description="来源文档名称或 URL")
    chunk_id: str = Field(description="retrieve 返回的稳定分块 ID")
    quoted_span: str = Field(description="来自分块文本的短原文引用")

    @field_validator("source", "chunk_id", "quoted_span")
    @classmethod
    def values_must_not_be_blank(cls, value: str) -> str:
        # Pydantic 会在构造 Citation 时自动调用这个校验器。
        # 这里先去掉首尾空白，再拒绝空字符串，避免模型返回“看似有字段、实际没内容”的引用。
        value = value.strip()
        if not value:
            raise ValueError("引用字段不能为空")
        return value


class Answer(BaseModel):
    """Streamlit 应用渲染的已校验回答。"""

    # text 是最终展示给用户的正文。
    text: str

    # citations 是正文背后的原文证据。answered=True 时至少要有一个引用。
    citations: list[Citation]

    # confidence 被限制在 0 到 1 之间，避免模型返回 80、100、"high" 这类不可控格式。
    confidence: float = Field(ge=0.0, le=1.0)

    # answered 是一个显式决策：回答还是拒答。
    # UI 不需要猜测文本含义，只看这个布尔值决定渲染普通回答还是拒答状态。
    answered: bool

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        # 回答正文必须有实际内容；拒答也要用 REFUSAL_TEXT 说明原因。
        value = value.strip()
        if not value:
            raise ValueError("回答文本不能为空")
        return value

    @model_validator(mode="after")
    def answer_and_citations_must_agree(self) -> "Answer":
        # 这是跨字段校验：单个字段本身可能合法，但组合起来不一定合法。
        #
        # 合法组合只有两类：
        # 1. answered=True：必须有 citations。
        # 2. answered=False：必须没有 citations。
        if self.answered and not self.citations:
            raise ValueError("已回答内容至少需要一个引用")
        if not self.answered and self.citations:
            raise ValueError("拒答内容不能包含引用")
        return self

    @classmethod
    def insufficient_evidence(cls, top_score: float = 0.0) -> "Answer":
        # 所有拒答路径都走这里，保证 UI 收到的结构一致。
        # top_score 仍然保留为 confidence，方便用户看到“最接近的证据有多接近”。
        return cls(
            text=REFUSAL_TEXT,
            citations=[],
            confidence=round(min(max(top_score, 0.0), 1.0), 3),
            answered=False,
        )


class RetrievedChunk(BaseModel):
    """retrieve 工具返回的可序列化分块。"""

    # 这是从 rag.py 的 SearchResult 转换来的 LLM 可见结构。
    # 不直接把内部对象暴露给模型，方便控制输出字段。
    source: str
    chunk_id: str
    text: str
    score: float = Field(ge=0.0, le=1.0)


class RetrievalEvidence(BaseModel):
    """一次向量检索的类型化结果。"""

    # query 是本次检索实际使用的问题文本。
    query: str

    # enough_evidence 是确定性门禁判断，不交给模型自由决定。
    # top_score >= min_relevance 才会是 True。
    enough_evidence: bool

    # top_score 是最相关分块的相似度。
    top_score: float = Field(ge=0.0, le=1.0)

    # chunks 是按相关性排序后的候选证据。
    chunks: list[RetrievedChunk]


@dataclass
class RagDependencies:
    """通过 RunContext 注入到工具中的单次运行资源。"""

    # store 是 app.py 构建好的内存向量库。
    # 它不是全局变量，而是每次 answer_question 调用时显式传入。
    store: InMemoryVectorStore

    # 低于这个相似度阈值，系统会拒答，不让 LLM 硬猜。
    min_relevance: float = DEFAULT_MIN_RELEVANCE

    # 每次检索最多返回多少个分块给模型。
    top_k: int = 4


# 这是给 LLM 的系统规则。
# 注意它不能替代 Python 校验：模型可能漏调工具、引用错误或输出不合规。
# 所以下面仍然有 preflight 检索和 validate_grounded_answer 二次校验。
AGENT_INSTRUCTIONS = """
你只能根据 retrieve 工具返回的证据回答问题。

规则：
1. 生成最终输出前，必须先调用 retrieve。
2. 如果 retrieve 返回 enough_evidence=false，必须设置 answered=false，
   不要返回 citations，并说明已索引资料中没有足够证据。
3. 如果证据充分，只能回答 returned chunks 支持的结论。
4. 每个 citation 必须从 retrieve 结果中原样复制 source 和 chunk_id。
5. quoted_span 必须是对应 chunk text 中的一小段原文子串。
6. confidence 必须是 0 到 1 之间的数字；证据不完整时应降低置信度。
7. 不要使用背景知识填补资料中的空白。
""".strip()


rag_agent: Agent[RagDependencies, Answer] = Agent(
    # deps_type 告诉 Pydantic AI：本 Agent 的工具运行时会收到 RagDependencies。
    deps_type=RagDependencies,

    # output_type 告诉 Pydantic AI：最终输出必须能被解析成 Answer。
    # 这就是“类型化 RAG”的核心。
    output_type=Answer,

    # instructions 是模型行为约束；它指导模型调用 retrieve 并返回引用。
    instructions=AGENT_INSTRUCTIONS,

    # 输出不符合 Answer schema 时，Pydantic AI 会尝试让模型重试修正。
    retries=2,
)


async def retrieve_evidence(deps: RagDependencies, query: str) -> RetrievalEvidence:
    """检索依赖中的资料，并用类型化数据暴露相关性判断。"""
    # deps.store.search 是确定性检索步骤，返回 SearchResult 列表。
    # 这里没有调用 LLM，只是用本地向量库找最相关的分块。
    results = await deps.store.search(query, limit=deps.top_k)

    # 如果没有任何结果，就把 top_score 视为 0。
    top_score = results[0].score if results else 0.0

    # 把内部 SearchResult 转换成 RetrievalEvidence。
    # 这个对象既可以给 preflight 门禁用，也可以作为 retrieve 工具结果给模型看。
    return RetrievalEvidence(
        query=query,
        enough_evidence=bool(results and top_score >= deps.min_relevance),
        top_score=top_score,
        chunks=[
            RetrievedChunk(
                source=result.chunk.source,
                chunk_id=result.chunk.chunk_id,
                text=result.chunk.text,
                score=result.score,
            )
            for result in results
        ],
    )


@rag_agent.tool
async def retrieve(ctx: RunContext[RagDependencies], query: str) -> RetrievalEvidence:
    """检索与用户问题相关的来源分块。"""
    # @rag_agent.tool 把这个函数注册成 LLM 可调用工具。
    # ctx.deps 就是 answer_question 里传入的 RagDependencies。
    return await retrieve_evidence(ctx.deps, query)


def default_deepseek_model_name() -> str:
    """返回 Pydantic AI 的 DeepSeek 模型字符串。"""
    # 项目里统一使用 DEEPSEEK_MODEL_ID；MODEL_ID 作为历史兼容兜底。
    model_id = os.getenv(
        "DEEPSEEK_MODEL_ID",
        os.getenv("MODEL_ID", DEFAULT_DEEPSEEK_MODEL_ID),
    ).strip()

    # 如果用户已经写成 deepseek:xxx，就不要重复加前缀。
    if ":" in model_id:
        return model_id
    return f"deepseek:{model_id}"


def resolve_model_name() -> str:
    """从环境变量解析 Pydantic AI 模型配置。"""
    # RAG_MODEL 是最高优先级，方便用户直接填 Pydantic AI 支持的完整模型字符串。
    if configured := os.getenv("RAG_MODEL", "").strip():
        return configured

    # 默认路径要求配置 DeepSeek key，并根据 DEEPSEEK_MODEL_ID 生成模型字符串。
    if os.getenv("DEEPSEEK_API_KEY"):
        return default_deepseek_model_name()
    raise RuntimeError("提问前请先配置 DEEPSEEK_API_KEY")


def _normalize_quote(value: str) -> str:
    # 引用校验时忽略大小写和连续空白差异。
    # 这样模型复制原文时即使换行或多空格不同，也能被正确匹配。
    return re.sub(r"\s+", " ", value).strip().casefold()


def _valid_citations(answer: Answer, deps: RagDependencies) -> list[Citation]:
    # 过滤出真实可验证的 citations。
    # 模型返回的引用不能直接相信，必须回到 store 里检查 source/chunk_id/quoted_span。
    valid = []
    for citation in answer.citations:
        # 先用 source + chunk_id 定位原始分块。
        chunk = deps.store.find_chunk(citation.source, citation.chunk_id)
        quoted_span = _normalize_quote(citation.quoted_span)
        if (
            chunk
            # 太短的引用没有足够约束力，例如 "the"、"policy"。
            and len(quoted_span) >= 8
            # quoted_span 必须真的出现在对应分块文本中。
            and quoted_span in _normalize_quote(chunk.text)
        ):
            valid.append(citation)
    return valid


def _used_retrieve(messages: list[Any]) -> bool:
    # Pydantic AI 会记录一次 run 的消息和工具事件。
    # 这里检查模型是否真的调用过 retrieve，防止模型跳过检索直接回答。
    return any(
        getattr(part, "tool_name", None) == "retrieve"
        and getattr(part, "part_kind", None) in {"tool-call", "tool-return"}
        for message in messages
        for part in message.parts
    )


def validate_grounded_answer(
    answer: Answer,
    deps: RagDependencies,
    preflight: RetrievalEvidence,
    *,
    used_retrieve: bool,
) -> Answer:
    """拒绝跳过检索或引用不在资料库中的回答。"""
    # 如果模型自己已经拒答，统一改成系统标准拒答结构。
    if not answer.answered:
        return Answer.insufficient_evidence(preflight.top_score)

    # 如果模型没有调用 retrieve，即使回答看起来合理，也不接受。
    if not used_retrieve:
        return Answer.insufficient_evidence(preflight.top_score)

    # 校验引用是否真的对应已索引资料。
    citations = _valid_citations(answer, deps)
    if not citations:
        return Answer.insufficient_evidence(preflight.top_score)

    # 如果部分引用有效、部分无效，只保留有效引用。
    return answer.model_copy(update={"citations": citations})


async def answer_question(
    question: str,
    deps: RagDependencies,
    model: str | None = None,
) -> Answer:
    """先经过确定性检索门禁，再运行类型化 Agent。"""
    question = question.strip()
    if not question:
        raise ValueError("问题不能为空")

    # 第一层防线：先不调用 LLM，直接用本地向量库检索。
    # 如果最高分都低于阈值，说明资料里大概率没有答案，直接拒答。
    preflight = await retrieve_evidence(deps, question)
    if not preflight.enough_evidence:
        return Answer.insufficient_evidence(preflight.top_score)

    # 第二层：证据够时才调用 Pydantic AI Agent。
    # deps 会注入给 retrieve 工具；model 允许 UI 传入 deepseek:xxx。
    run_options: dict[str, Any] = {"deps": deps}
    if model is not None:
        run_options["model"] = model
    result = await rag_agent.run(question, **run_options)

    # 第三层防线：模型回答后继续验证工具调用和引用真实性。
    return validate_grounded_answer(
        result.output,
        deps,
        preflight,
        used_retrieve=_used_retrieve(result.all_messages()),
    )
