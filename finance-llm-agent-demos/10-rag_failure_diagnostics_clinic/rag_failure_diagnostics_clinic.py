"""
RAG Failure Diagnostics Clinic

Framework-agnostic example for finance-llm-agent-demos.
Diagnose LLM + RAG bugs into reusable failure patterns (P01–P12).
"""

import json
import os
import textwrap
import time

import requests
from dotenv import load_dotenv


APP_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(APP_DIR)
WORKSPACE_DIR = os.path.dirname(REPO_DIR)
for env_path in (
    os.path.join(APP_DIR, ".env"),
    os.path.join(REPO_DIR, ".env"),
    os.path.join(WORKSPACE_DIR, ".env"),
):
    load_dotenv(env_path)


PATTERNS = [
    {
        "id": "P01",
        "name": "检索幻觉 / 事实依据漂移",
        "summary": "回答自信地违背或忽略检索到的文档。",
    },
    {
        "id": "P02",
        "name": "文本分块边界问题",
        "summary": "相关事实在分块之间被拆散、截断或错误组合。",
    },
    {
        "id": "P03",
        "name": "Embedding 不匹配",
        "summary": "向量相似度与真实语义相关性不一致。",
    },
    {
        "id": "P04",
        "name": "索引偏移或过期",
        "summary": "索引返回相对于事实源的旧数据或缺失数据。",
    },
    {
        "id": "P05",
        "name": "查询改写或路由错位",
        "summary": "路由器或改写器把问题发送到了错误的工具或数据集。",
    },
    {
        "id": "P06",
        "name": "长链推理漂移",
        "summary": "多步骤任务逐渐忘记早期约束或目标。",
    },
    {
        "id": "P07",
        "name": "工具调用误用",
        "summary": "工具参数错误，或在缺少事实依据时调用工具。",
    },
    {
        "id": "P08",
        "name": "会话记忆泄漏或上下文缺失",
        "summary": "对话在轮次或会话之间丢失重要事实。",
    },
    {
        "id": "P09",
        "name": "评估盲区",
        "summary": "系统通过测试，却在真实事件或边界条件下失败。",
    },
    {
        "id": "P10",
        "name": "启动顺序或依赖未就绪",
        "summary": "部署后的最初几分钟内服务崩溃或返回 5xx。",
    },
    {
        "id": "P11",
        "name": "环境配置或密钥漂移",
        "summary": "本地正常，但因配置不同在测试或生产环境失败。",
    },
    {
        "id": "P12",
        "name": "多租户或多 Agent 相互干扰",
        "summary": "请求或 Agent 相互覆盖状态或资源。",
    },
]


EXAMPLE_1 = """=== 示例 1：检索幻觉（P01 风格） ===

背景：
你有一个简单的 RAG 聊天机器人，用来基于产品 FAQ 回答用户问题。
这份 FAQ 只覆盖 SaaS 产品的账单规则，没有任何关于加密货币的说明。

用户问题：
“我可以用比特币支付订阅费用吗？”

检索上下文（来自向量库）：
- “我们只接受主流信用卡和 PayPal。”
- “所有付款都以美元处理。”

模型回答：
“可以，你可以使用比特币付款。我们通过第三方支付网关支持多种加密货币。”

日志：
没有报错。检索结果显示的就是上面的 FAQ 片段，但模型仍然自信地编造了支持比特币支付。
"""


EXAMPLE_2 = """=== 示例 2：启动顺序 / 依赖未就绪（P10 风格） ===

背景：
你有一个 RAG API，由三个服务组成：api-gateway、rag-worker 和 vector-db（例如 Qdrant 或 FAISS）。
在本地 docker compose 环境中，一切运行正常。

部署方式：
生产环境使用 Kubernetes 部署这些服务。

现象：
每次新版本刚部署完成后的前几分钟，api-gateway 会返回 500 错误。
日志显示 api-gateway 连接 vector-db 超时。

几分钟后，错误会自动消失，系统恢复正常。
你怀疑 api-gateway 和 vector-db 之间存在启动竞态，但不确定应该如何正确修复。
"""


EXAMPLE_3 = """=== 示例 3：配置或密钥漂移（P11 风格） ===

背景：
你给 RAG 流水线新增了一个环境变量：SECRET_RAG_KEY。
一个中间件需要使用这个密钥，对发往内部搜索 API 的请求进行签名。

本地环境：
开发者机器上的 .env 文件里配置了 SECRET_RAG_KEY，所以一切正常。

生产环境：
你部署了新版本，但忘记把 SECRET_RAG_KEY 添加到生产环境变量中。
部署后的第一批请求返回 500 错误，日志中出现 “missing secret” 信息。

临时把密钥补到生产环境后，错误停止。
但是，类似“首次部署因为缺少配置而失败”的事故仍然反复发生。
"""


def build_system_prompt() -> str:
    """构造说明故障模式和诊断任务的系统提示词。"""
    header = """
你是一名负责诊断 LLM 与 RAG 流水线故障的助手。

你有一套可复用的故障模式库 P01–P12。针对每个故障描述，你必须：

1. 从 P01–P12 中选择且只能选择一个主要模式。
2. 可选地选择最多两个次要候选模式。
3. 使用清晰的中文要点解释判断依据。
4. 提出最小结构性修复：可以涉及检索、索引、路由、评估、工具或基础设施，避免只说“增加上下文”或“换更好的模型”。

不允许编造新的模式编号，只能从下面列出的模式中选择。

请用中文 Markdown 输出，并包含以下部分：

- 主要模式
- 次要候选模式（可选）
- 判断依据
- 最小结构性修复
"""
    pattern_lines = []
    for p in PATTERNS:
        line = f"{p['id']}: {p['name']} — {p['summary']}"
        pattern_lines.append(line)

    patterns_block = "\n".join(pattern_lines)
    return textwrap.dedent(header).strip() + "\n\nFailure patterns:\n" + patterns_block


def read_model_config() -> tuple[str, str, str]:
    """读取 DeepSeek 配置，不打印 API Key。"""
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("未找到 DEEPSEEK_API_KEY，请在 .env 中配置。")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model_name = os.getenv("DEEPSEEK_MODEL_ID", "deepseek-chat")
    print(f"\n模型服务：{base_url}")
    print(f"模型名称：{model_name}\n")
    return api_key, base_url, model_name


def call_deepseek(api_key: str, base_url: str, model_name: str, system_prompt: str, bug: str) -> str:
    """调用 DeepSeek，并对临时网络或服务错误进行重试。"""
    payload = {
        "model": model_name,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "以下是故障描述，请按规则诊断：\n\n" + bug},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    retryable_statuses = {429, 500, 502, 503, 504}
    for attempt in range(3):
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
        except requests.RequestException as exc:
            if attempt == 2:
                raise RuntimeError(f"DeepSeek 网络请求失败：{exc}") from exc
            time.sleep(2**attempt)
            continue

        if response.status_code < 400:
            data = response.json()
            return data["choices"][0]["message"]["content"] or "未返回诊断内容。"
        if response.status_code not in retryable_statuses or attempt == 2:
            detail = response.text[:300]
            if response.status_code == 503:
                raise RuntimeError("DeepSeek 当前服务繁忙，已自动重试 3 次，请稍后再试。")
            raise RuntimeError(f"DeepSeek 请求失败（HTTP {response.status_code}）：{detail}")
        time.sleep(2**attempt)
    raise RuntimeError("DeepSeek 请求失败。")


def choose_bug_description() -> str:
    """让用户选择内置示例或粘贴自己的故障描述。"""
    print("请选择示例，或粘贴自己的故障描述：\n")
    print("  [1] 示例 1：检索幻觉（P01）")
    print("  [2] 示例 2：启动顺序问题（P10）")
    print("  [3] 示例 3：配置或密钥漂移（P11）")
    print("  [p] 粘贴自己的 RAG / LLM 故障\n")

    choice = input("你的选择：").strip().lower()
    print()

    if choice == "1":
        bug = EXAMPLE_1
        print("你选择了示例 1，完整故障描述：\n")
        print(bug)
        print()
        return bug

    if choice == "2":
        bug = EXAMPLE_2
        print("你选择了示例 2，完整故障描述：\n")
        print(bug)
        print()
        return bug

    if choice == "3":
        bug = EXAMPLE_3
        print("你选择了示例 3，完整故障描述：\n")
        print(bug)
        print()
        return bug

    print("请粘贴故障描述，输入空行结束：")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)

    user_bug = "\n".join(lines).strip()
    if not user_bug:
        print("没有检测到故障描述，本轮结束。\n")
        return ""

    print("\n你输入的故障描述：\n")
    print(user_bug)
    print()
    return user_bug


def run_once(api_key: str, base_url: str, model_name: str, system_prompt: str) -> None:
    """执行一轮故障诊断。"""
    bug = choose_bug_description()
    if not bug:
        return

    print("正在进行故障诊断……\n")

    try:
        reply = call_deepseek(api_key, base_url, model_name, system_prompt, bug)
    except Exception as exc:
        print(f"调用 DeepSeek 失败：{exc}")
        return

    print(reply)

    report = {
        "bug_description": bug,
        "model": model_name,
        "assistant_markdown": reply,
    }

    try:
        with open("rag_failure_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("\n诊断报告已保存到 rag_failure_report.json\n")
    except OSError as exc:
        print(f"\n无法写入报告文件：{exc}\n")


def main():
    system_prompt = build_system_prompt()
    try:
        api_key, base_url, model_name = read_model_config()
    except RuntimeError as exc:
        print(f"配置错误：{exc}")
        return

    while True:
        run_once(api_key, base_url, model_name, system_prompt)
        again = input("是否继续诊断其他故障？（y/n）：").strip().lower()
        if again != "y":
            print("诊断结束。")
            break
        print()


if __name__ == "__main__":
    main()
