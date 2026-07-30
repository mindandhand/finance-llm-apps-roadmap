"""
12 Finance Research Console：把 AG-UI 运行过程整理成研究任务。

12 不再自己模拟一条独立的聊天链路，而是作为产品层控制台：

    浏览器 -> 12 创建任务 -> 10 /agui -> 记录事件 -> 生成报告 artifact

这样可以同时看到任务状态、工具时间线和最终研究报告。
"""
import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.request import Request, urlopen
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field


APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent.parent
for env_path in (APP_DIR / ".env", APP_DIR.parent / ".env", REPO_DIR / ".env"):
    load_dotenv(env_path)


ARTIFACT_DIR = APP_DIR / "artifacts"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7777
AGUI_AGENT_URL = os.getenv("AGUI_AGENT_URL", "http://127.0.0.1:7777").rstrip("/")
TASK_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="research-task")


class ResearchTaskRequest(BaseModel):
    topic: str = Field(default="比较 SH510300 和 SH588000 的行情、新闻和因子", min_length=1, max_length=500)
    symbols: list[str] = Field(default_factory=lambda: ["SH510300", "SH588000"], min_length=1, max_length=10)


class ResearchTask(BaseModel):
    task_id: str
    topic: str
    symbols: list[str]
    status: Literal["pending", "running", "completed", "failed"]
    run_id: str | None = None
    event_count: int = 0
    report_path: str | None = None
    error: str | None = None
    created_at: str


TASKS: dict[str, ResearchTask] = {}
TASK_EVENTS: dict[str, list[dict[str, Any]]] = {}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def update_task(task_id: str, **changes: Any) -> ResearchTask:
    task = TASKS[task_id]
    updated = task.model_copy(update=changes)
    TASKS[task_id] = updated
    return updated


def parse_agui_stream(stream: Any, task_id: str) -> str:
    """读取官方 AG-UI 的 data JSON 行，保存时间线并拼接最终回答。"""
    answer_parts: list[str] = []
    pending_data: list[str] = []
    for raw_line in stream:
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if line.startswith("data: "):
            pending_data.append(line[6:])
            continue
        if line or not pending_data:
            continue
        try:
            event = json.loads("\n".join(pending_data))
        except json.JSONDecodeError:
            pending_data.clear()
            continue
        event["received_at"] = now_iso()
        TASK_EVENTS[task_id].append(event)
        if event.get("type") == "TEXT_MESSAGE_CONTENT":
            answer_parts.append(str(event.get("delta", "")))
        pending_data.clear()
    return "".join(answer_parts)


def run_agent_task(task_id: str, request: ResearchTaskRequest) -> None:
    """后台执行一次 AG-UI run，避免浏览器请求被模型调用长时间阻塞。"""
    update_task(task_id, status="running")
    TASK_EVENTS[task_id] = []
    run_id = f"run-{uuid4().hex[:12]}"
    update_task(task_id, run_id=run_id)
    payload = {
        "threadId": f"research-thread-{task_id}",
        "runId": run_id,
        "state": {},
        "messages": [
            {
                "id": f"message-{uuid4().hex[:12]}",
                "role": "user",
                "content": f"{request.topic}\n研究标的：{', '.join(request.symbols)}",
            }
        ],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }
    try:
        http_request = Request(
            f"{AGUI_AGENT_URL}/agui",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            method="POST",
        )
        with urlopen(http_request, timeout=180) as response:
            answer = parse_agui_stream(response, task_id)
        artifact_id = f"report_{uuid4().hex[:12]}"
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = ARTIFACT_DIR / f"{artifact_id}.md"
        timeline = TASK_EVENTS[task_id]
        report = "\n".join(
            [
                f"# {request.topic}",
                "",
                f"- task_id: `{task_id}`",
                f"- run_id: `{run_id}`",
                f"- symbols: `{', '.join(request.symbols)}`",
                f"- event_count: `{len(timeline)}`",
                "",
                "## Agent 结论",
                "",
                answer or "Agent 未返回文本结论。",
                "",
                "## 执行时间线",
                "",
                *[f"- `{event.get('type', 'UNKNOWN')}`" for event in timeline],
                "",
                "## 风险提示",
                "",
                "本报告由研究 Agent 生成，数据来源和时间戳应在生产系统中继续保留；不构成投资建议。",
            ]
        )
        report_path.write_text(report + "\n", encoding="utf-8")
        update_task(task_id, status="completed", event_count=len(timeline), report_path=str(report_path))
    except Exception as exc:  # 后台任务必须把失败状态写回控制台。
        update_task(task_id, status="failed", event_count=len(TASK_EVENTS.get(task_id, [])), error=str(exc))


def create_sample_task() -> ResearchTask:
    """生成离线样例，便于不启动 10 时验证 12 的 artifact 展示。"""
    task_id = f"task_{uuid4().hex[:12]}"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = ARTIFACT_DIR / f"{task_id}.md"
    report_path.write_text(
        "# 离线研究台样例\n\n这是 12 的本地 artifact 测试，不调用 10 或大模型。\n",
        encoding="utf-8",
    )
    task = ResearchTask(
        task_id=task_id,
        topic="离线研究台样例",
        symbols=["SH510300", "SH588000"],
        status="completed",
        event_count=0,
        report_path=str(report_path),
        created_at=now_iso(),
    )
    TASKS[task_id] = task
    return task


app = FastAPI(title="12 Finance Research Console")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent_url": AGUI_AGENT_URL}


@app.post("/api/tasks")
def post_task(request: ResearchTaskRequest) -> dict[str, Any]:
    task_id = f"task_{uuid4().hex[:12]}"
    task = ResearchTask(
        task_id=task_id,
        topic=request.topic,
        symbols=request.symbols,
        status="pending",
        created_at=now_iso(),
    )
    TASKS[task_id] = task
    TASK_EVENTS[task_id] = []
    TASK_EXECUTOR.submit(run_agent_task, task_id, request)
    return task.model_dump()


@app.get("/api/tasks")
def list_tasks() -> list[dict[str, Any]]:
    return [task.model_dump() for task in TASKS.values()]


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    task = TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {**task.model_dump(), "events": TASK_EVENTS.get(task_id, [])}


@app.get("/api/tasks/{task_id}/report", response_class=PlainTextResponse)
def get_report(task_id: str) -> str:
    task = TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task.status != "completed" or not task.report_path:
        raise HTTPException(status_code=409, detail=f"report is not ready: {task.status}")
    return Path(task.report_path).read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>12 Research Console</title>
<style>body{font-family:system-ui;max-width:1100px;margin:32px auto;padding:0 16px}input{width:70%;padding:10px}button{padding:10px 16px}.grid{display:grid;grid-template-columns:320px 1fr;gap:16px;margin-top:20px}pre{white-space:pre-wrap;border:1px solid #ddd;padding:12px;min-height:360px;overflow:auto}@media(max-width:700px){.grid{grid-template-columns:1fr}input{width:100%}}</style></head>
<body><h1>Finance Research Console</h1><p>提交任务后，控制台会显示 AG-UI 运行状态、事件时间线和最终报告。</p>
<form id="form"><input id="topic" value="比较 SH510300 和 SH588000 的行情、新闻和因子"><button>Run</button></form>
<div class="grid"><pre id="task">等待任务</pre><pre id="report">报告将在任务完成后显示</pre></div>
<script>
const taskBox=document.querySelector('#task'), reportBox=document.querySelector('#report');
document.querySelector('#form').onsubmit=async(event)=>{event.preventDefault();
  const task=await fetch('/api/tasks',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({topic:document.querySelector('#topic').value})}).then(r=>r.json());
  const poll=async()=>{const current=await fetch(`/api/tasks/${task.task_id}`).then(r=>r.json()); taskBox.textContent=JSON.stringify(current,null,2);
    if(current.status==='completed'){reportBox.textContent=await fetch(`/api/tasks/${task.task_id}/report`).then(r=>r.text());return;}
    if(current.status==='failed'){reportBox.textContent=`任务失败：${current.error}`;return;}
    setTimeout(poll,700);}; poll();
};
</script></body></html>"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the finance research console.")
    parser.add_argument("--sample-task", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.sample_task:
        print(json.dumps(create_sample_task().model_dump(), ensure_ascii=False, indent=2))
        return
    if args.serve:
        import uvicorn

        uvicorn.run(app, host=args.host, port=args.port)
        return
    print(json.dumps({"endpoint": "/", "api": ["/api/tasks", "/api/tasks/{task_id}", "/api/tasks/{task_id}/report"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
