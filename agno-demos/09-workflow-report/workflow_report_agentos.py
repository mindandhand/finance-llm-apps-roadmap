"""
09 Workflow Report：用固定步骤生成可下载报告 artifact。

相比 Team 的“角色协作”，Workflow 更强调步骤可控：

1. collect_inputs
2. compute_metrics
3. render_report
4. save_artifact
"""
import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from agno.os.app import AgentOS
from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from agno.workflow import Step, Workflow
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent.parent
# 只从环境文件读取模型凭据；代码和生成的报告都不保存 API key。
for env_path in (APP_DIR / ".env", APP_DIR.parent / ".env", REPO_DIR / ".env"):
    load_dotenv(env_path)
# 报告文件放在 demo 自己的 artifacts 目录，便于查看、下载和清理。
ARTIFACT_DIR = APP_DIR / "artifacts"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7777

FACTOR_DATA = {
    # 这里使用固定样例数据，让 Workflow 可以离线、可重复地演示。
    "SH510300": {"name": "沪深300ETF", "20d_momentum": 0.041, "60d_volatility": 0.183},
    "SH588000": {"name": "科创50ETF", "20d_momentum": -0.026, "60d_volatility": 0.317},
}


class ReportRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["SH510300", "SH588000"], min_length=1, max_length=10)
    title: str = Field(default="ETF 样例研究报告", min_length=1, max_length=200)
    # 默认关闭模型，保证本地 sample 和基础接口不产生外部调用或费用。
    use_model: bool = False


class ReportArtifact(BaseModel):
    artifact_id: str
    title: str
    path: str
    symbols: list[str]
    created_at: str


# 进程内索引只负责快速查询；文件本身才是可下载的报告产物。
ARTIFACTS: dict[str, ReportArtifact] = {}


def normalize_symbol(symbol: str) -> str:
    """统一用户输入的标的格式，并拒绝不在样例数据集中的标的。"""
    value = symbol.strip().upper()
    aliases = {"510300": "SH510300", "588000": "SH588000"}
    value = aliases.get(value, value)
    if value not in FACTOR_DATA:
        raise ValueError(f"unsupported symbol: {symbol}")
    return value


def build_summary_agent() -> Agent:
    """创建只负责报告结论的模型 Agent。"""
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY or OPENAI_API_KEY is required when use_model=true")
    model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat"))
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    return Agent(
        id="finance-report-summary-agent",
        name="Finance Report Summary Agent",
        model=DeepSeek(id=model_id, api_key=api_key, base_url=base_url),
        instructions=[
            "Only use the supplied local factor rows.",
            "Explain the comparison in Chinese in two or three concise paragraphs.",
            "Include a clear non-investment-advice caveat.",
        ],
        markdown=True,
        telemetry=False,
    )


def generate_model_summary(rows: list[dict[str, Any]]) -> str:
    """把已校验的结构化数据交给模型，避免模型自行编造行情来源。"""
    prompt = (
        "请根据以下本地样例因子数据生成报告结论，不要补充数据之外的事实：\n"
        f"{json.dumps(rows, ensure_ascii=False)}"
    )
    result = build_summary_agent().run(prompt)
    if getattr(result, "status", None) == "ERROR":
        # 不把模型错误文本当成正常结论写入报告，避免生成误导性的成功 artifact。
        raise RuntimeError(f"model summary failed: {result.content}")
    return str(result.content or "模型未返回结论。")


def run_report_workflow(request: ReportRequest) -> ReportArtifact:
    """执行确定性的报告流程，便于测试 artifact 生命周期。

    HTTP 请求和命令行示例都从这里进入，因此报告生成逻辑只有一个实现。
    真实系统可以把这里的固定数据替换为行情、新闻和因子服务。
    """
    # 第一步：校验并规范化输入，避免后续步骤处理多个符号格式。
    symbols = [normalize_symbol(symbol) for symbol in request.symbols]
    # 第二步：把样例因子数据整理成报告表格需要的行。
    rows = [{"symbol": symbol, **FACTOR_DATA[symbol]} for symbol in symbols]
    # 第三步：先生成稳定的 artifact ID，再用它同时命名内存记录和 Markdown 文件。
    artifact_id = f"report_{uuid4().hex[:12]}"
    created_at = datetime.now(UTC).isoformat()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{artifact_id}.md"

    # 第四步：可选地让模型生成结论；关闭时使用固定文案保持离线可重复。
    conclusion = (
        generate_model_summary(rows)
        if request.use_model
        else "SH588000 的样例 60 日波动率高于 SH510300；本报告只使用本地样例数据，不构成投资建议。"
    )
    # 第五步：渲染 Markdown。报告是普通文件，便于浏览器下载或后续交给其他系统。
    lines = [
        f"# {request.title}",
        "",
        f"- artifact_id: `{artifact_id}`",
        f"- created_at: `{created_at}`",
        f"- data_source: `local_demo_factor_data`",
        "",
        "| symbol | name | 20d_momentum | 60d_volatility |",
        "|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['symbol']} | {row['name']} | {row['20d_momentum']:.3f} | {row['60d_volatility']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            conclusion,
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 保存元数据，列表接口可以不读取 Markdown 内容就返回报告清单。
    artifact = ReportArtifact(
        artifact_id=artifact_id,
        title=request.title,
        path=str(path),
        symbols=symbols,
        created_at=created_at,
    )
    ARTIFACTS[artifact_id] = artifact
    return artifact


def collect_inputs(_: Any) -> dict[str, Any]:
    # Workflow 的第一步提供默认输入；HTTP 入口使用 run_report_workflow 保持简单。
    return {"symbols": ["SH510300", "SH588000"], "title": "ETF 样例研究报告"}


def compute_metrics(step_input: Any) -> dict[str, Any]:
    # 从上一步的输入读取 symbols，并计算下一步需要的结构化行数据。
    payload = getattr(step_input, "input", None) or {}
    symbols = [normalize_symbol(symbol) for symbol in payload.get("symbols", ["SH510300", "SH588000"])]
    return {"symbols": symbols, "rows": [{"symbol": symbol, **FACTOR_DATA[symbol]} for symbol in symbols]}


def render_report(step_input: Any) -> str:
    # 这个步骤只负责展示摘要，完整 Markdown artifact 由 HTTP/CLI 入口保存。
    payload = getattr(step_input, "input", None) or {}
    rows = payload.get("rows", [])
    return "\n".join([f"{row['symbol']}: vol={row['60d_volatility']:.3f}" for row in rows])


def build_workflow() -> Workflow:
    # AgentOS 会把这个 Workflow 注册到 /workflows 和 /workflows/{id}/runs。
    return Workflow(
        id="finance-report-workflow",
        name="Finance Report Workflow",
        description="A deterministic report workflow with artifact output.",
        steps=[
            Step(name="collect_inputs", executor=collect_inputs),
            Step(name="compute_metrics", executor=compute_metrics),
            Step(name="render_report", executor=render_report),
        ],
        telemetry=False,
    )


def build_base_app() -> FastAPI:
    base_app = FastAPI(title="09 Workflow Report Demo")

    @base_app.post("/reports")
    def create_report(request: ReportRequest) -> dict[str, Any]:
        # 创建报告后直接返回 artifact 元数据，客户端再按 artifact_id 下载文件。
        return run_report_workflow(request).model_dump()

    @base_app.get("/reports")
    def list_reports() -> list[dict[str, Any]]:
        # 只返回当前进程已登记的元数据，不把整个报告内容塞进列表响应。
        return [artifact.model_dump() for artifact in ARTIFACTS.values()]

    @base_app.get("/reports/{artifact_id}/download")
    def download_report(artifact_id: str) -> FileResponse:
        # 优先查内存索引；服务重启后仍允许按已知 ID 下载磁盘上的报告。
        artifact = ARTIFACTS.get(artifact_id)
        if artifact is None:
            # Also allow downloading files from a previous process if the artifact id is known.
            candidate = ARTIFACT_DIR / f"{artifact_id}.md"
            if not candidate.exists():
                raise HTTPException(status_code=404, detail="artifact not found")
            return FileResponse(candidate, media_type="text/markdown", filename=candidate.name)
        return FileResponse(artifact.path, media_type="text/markdown", filename=Path(artifact.path).name)

    return base_app


def build_app() -> FastAPI:
    # base_app 提供自定义报告路由，AgentOS 同时提供 Workflow 管理路由。
    return AgentOS(
        id="workflow-report-demo",
        name="09 Workflow Report Demo",
        workflows=[build_workflow()],
        base_app=build_base_app(),
        on_route_conflict="preserve_base_app",
        telemetry=False,
    ).get_app()


app = build_app()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the workflow report demo.")
    parser.add_argument("--sample-report", action="store_true")
    parser.add_argument("--llm", action="store_true", help="Use the configured model to generate the conclusion.")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.sample_report:
        # 离线样例只生成一份报告，不启动 HTTP 服务，也不调用模型。
        artifact = run_report_workflow(ReportRequest(use_model=args.llm))
        print(json.dumps(artifact.model_dump(), ensure_ascii=False, indent=2))
        return
    if args.serve:
        # --serve 用于 Swagger、Agent UI 或其他客户端连接。
        AgentOS(workflows=[build_workflow()], base_app=build_base_app(), telemetry=False).serve(
            app, host=args.host, port=args.port
        )
        return
    artifact = run_report_workflow(ReportRequest(use_model=args.llm))
    print(json.dumps(artifact.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
