"""
07 Human Confirmation：在高风险动作前显式暂停，等待人工确认。

这个 demo 不做真实交易。它把“调仓建议”拆成两步：

1. Agent 或 API 只能创建 pending action。
2. 人通过 approve/reject 接口明确确认后，系统才把动作标记为 approved/rejected。

重点是交互边界：LLM 可以解释和起草动作，但不能直接执行高风险动作。
"""
import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from agno.os.app import AgentOS
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


APP_DIR = Path(__file__).resolve().parent
AGNO_DEMOS_DIR = APP_DIR.parent
REPO_DIR = AGNO_DEMOS_DIR.parent

for env_path in (APP_DIR / ".env", AGNO_DEMOS_DIR / ".env", REPO_DIR / ".env"):
    load_dotenv(env_path)


AGENT_ID = "human-confirmation-agent"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7777


class RebalanceRequest(BaseModel):
    user_id: str = Field(default="demo-user")
    source_symbol: str = Field(default="SH510300")
    target_symbol: str = Field(default="SH588000")
    amount_cny: float = Field(default=10000, gt=0)
    reason: str = Field(default="比较后希望调整 ETF 暴露")


class PendingAction(BaseModel):
    action_id: str
    user_id: str
    status: Literal["pending", "approved", "rejected"]
    source_symbol: str
    target_symbol: str
    amount_cny: float
    risk_notes: list[str]
    created_at: str
    decided_at: str | None = None
    decision_note: str | None = None


class DecisionRequest(BaseModel):
    note: str = Field(default="")


ACTION_STORE: dict[str, PendingAction] = {}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def prepare_rebalance_action(
    user_id: str,
    source_symbol: str,
    target_symbol: str,
    amount_cny: float,
    reason: str = "",
) -> dict[str, Any]:
    """创建待确认动作，而不是直接执行动作。

    这个函数可以作为 Agent tool 使用。返回值里故意包含 confirmation_required，
    方便前端渲染确认条，也提醒模型不能宣称动作已经完成。
    """
    action = PendingAction(
        action_id=f"act_{uuid4().hex[:12]}",
        user_id=user_id,
        status="pending",
        source_symbol=source_symbol.strip().upper(),
        target_symbol=target_symbol.strip().upper(),
        amount_cny=round(amount_cny, 2),
        risk_notes=[
            "这是 demo 中的模拟动作，不会连接券商或交易接口。",
            "高风险动作必须由用户在 API 或 UI 中显式确认。",
            "确认前只能作为研究建议，不应被描述为已执行。",
        ],
        created_at=now_iso(),
    )
    ACTION_STORE[action.action_id] = action
    return {
        "confirmation_required": True,
        "action": action.model_dump(),
        "reason": reason,
        "approve_endpoint": f"/risk-actions/{action.action_id}/approve",
        "reject_endpoint": f"/risk-actions/{action.action_id}/reject",
    }


def decide_action(
    action_id: str,
    status: Literal["approved", "rejected"],
    note: str = "",
) -> PendingAction:
    action = ACTION_STORE.get(action_id)
    if action is None:
        raise KeyError(action_id)
    if action.status != "pending":
        return action
    updated = action.model_copy(
        update={"status": status, "decided_at": now_iso(), "decision_note": note}
    )
    ACTION_STORE[action_id] = updated
    return updated


def build_agent() -> Agent:
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or "missing"
    model_id = os.getenv("DEEPSEEK_MODEL_ID", os.getenv("MODEL_ID", "deepseek-chat"))
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    return Agent(
        id=AGENT_ID,
        name="Human Confirmation Finance Agent",
        model=DeepSeek(id=model_id, api_key=api_key, base_url=base_url),
        tools=[prepare_rebalance_action],
        instructions=[
            "You can draft a rebalance action, but you must never say it is executed.",
            "When prepare_rebalance_action returns confirmation_required=true, ask the user to approve or reject it.",
            "Keep risk notes visible and do not provide personalized investment advice.",
        ],
        markdown=True,
        telemetry=False,
    )


def build_base_app() -> FastAPI:
    base_app = FastAPI(title="07 Human Confirmation Demo")

    @base_app.get("/human-confirmation-ui", response_class=HTMLResponse)
    def human_confirmation_ui() -> str:
        """提供一个无构建依赖的浏览器测试页，模拟人工点击确认动作。"""
        return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>07 Human Confirmation</title>
  <style>
    body { max-width: 760px; margin: 40px auto; padding: 0 16px; font: 16px/1.5 system-ui, sans-serif; color: #17202a; }
    h1 { margin-bottom: 8px; }
    form, .action { border: 1px solid #d9dee5; border-radius: 8px; padding: 16px; margin-top: 20px; }
    label { display: block; margin: 10px 0 4px; font-weight: 600; }
    input, textarea { box-sizing: border-box; width: 100%; padding: 8px; border: 1px solid #aeb7c2; border-radius: 4px; }
    button { margin: 14px 8px 0 0; padding: 9px 14px; border: 0; border-radius: 4px; cursor: pointer; }
    button[type=submit], .approve { background: #176b45; color: white; }
    .reject { background: #a83232; color: white; }
    button:disabled { cursor: not-allowed; opacity: .55; }
    pre { white-space: pre-wrap; background: #f4f6f8; padding: 12px; overflow-wrap: anywhere; }
    .pending { border-left: 5px solid #bd7b00; }
    .approved { border-left: 5px solid #176b45; }
    .rejected { border-left: 5px solid #a83232; }
  </style>
</head>
<body>
  <h1>Human Confirmation</h1>
  <p>先创建 pending 动作，再由用户点击批准或拒绝。</p>
  <form id="create-form">
    <label for="source">卖出标的</label>
    <input id="source" value="SH510300" required>
    <label for="target">买入标的</label>
    <input id="target" value="SH588000" required>
    <label for="amount">金额（CNY）</label>
    <input id="amount" type="number" value="10000" min="0.01" step="0.01" required>
    <label for="reason">原因</label>
    <textarea id="reason">模拟用户请求调仓</textarea>
    <button type="submit">创建待确认动作</button>
  </form>
  <section id="result" aria-live="polite"></section>
  <script>
    const result = document.querySelector('#result');
    let actionId = null;
    const render = (action) => {
      actionId = action.action_id;
      result.replaceChildren();
      const box = document.createElement('div');
      box.className = `action ${action.status}`;
      const title = document.createElement('h2');
      title.textContent = `状态：${action.status}`;
      const details = document.createElement('pre');
      details.textContent = JSON.stringify(action, null, 2);
      const approve = document.createElement('button');
      approve.className = 'approve';
      approve.textContent = '批准';
      const reject = document.createElement('button');
      reject.className = 'reject';
      reject.textContent = '拒绝';
      approve.disabled = reject.disabled = action.status !== 'pending';
      approve.onclick = () => decide('approve', approve, reject);
      reject.onclick = () => decide('reject', approve, reject);
      box.append(title, details, approve, reject);
      result.append(box);
    };
    const decide = async (decision, approve, reject) => {
      approve.disabled = reject.disabled = true;
      const response = await fetch(`/risk-actions/${actionId}/${decision}`, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({note: '浏览器模拟用户点击'})
      });
      if (!response.ok) { result.textContent = `请求失败：${response.status}`; return; }
      render(await response.json());
    };
    document.querySelector('#create-form').onsubmit = async (event) => {
      event.preventDefault();
      const response = await fetch('/risk-actions', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
          source_symbol: document.querySelector('#source').value,
          target_symbol: document.querySelector('#target').value,
          amount_cny: Number(document.querySelector('#amount').value),
          reason: document.querySelector('#reason').value
        })
      });
      if (!response.ok) { result.textContent = `请求失败：${response.status}`; return; }
      const payload = await response.json();
      render(payload.action);
    };
  </script>
</body>
</html>"""

    @base_app.get("/risk-actions")
    def list_actions() -> list[dict[str, Any]]:
        return [action.model_dump() for action in ACTION_STORE.values()]

    @base_app.post("/risk-actions")
    def create_action(request: RebalanceRequest) -> dict[str, Any]:
        return prepare_rebalance_action(**request.model_dump())

    @base_app.post("/risk-actions/{action_id}/approve")
    def approve_action(action_id: str, request: DecisionRequest) -> dict[str, Any]:
        try:
            return decide_action(action_id, "approved", request.note).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="action not found") from exc

    @base_app.post("/risk-actions/{action_id}/reject")
    def reject_action(action_id: str, request: DecisionRequest) -> dict[str, Any]:
        try:
            return decide_action(action_id, "rejected", request.note).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="action not found") from exc

    return base_app


def build_app() -> FastAPI:
    agent_os = AgentOS(
        id="human-confirmation-demo",
        name="07 Human Confirmation Demo",
        agents=[build_agent()],
        base_app=build_base_app(),
        on_route_conflict="preserve_base_app",
        telemetry=False,
    )
    return agent_os.get_app()


app = build_app()


def print_sample_confirmation() -> None:
    created = prepare_rebalance_action(
        user_id="demo-user",
        source_symbol="SH510300",
        target_symbol="SH588000",
        amount_cny=10000,
        reason="演示高风险动作先进入 pending 状态",
    )
    action_id = created["action"]["action_id"]
    approved = decide_action(action_id, "approved", "人工确认通过")
    print(json.dumps({"created": created, "approved": approved.model_dump()}, ensure_ascii=False, indent=2))


def print_routes(fastapi_app: FastAPI) -> None:
    routes = []
    for route in fastapi_app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path and methods:
            routes.append({"path": path, "methods": sorted(methods)})
    print(json.dumps(routes, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the human confirmation demo.")
    parser.add_argument("--sample-confirmation", action="store_true")
    parser.add_argument("--routes", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.sample_confirmation:
        print_sample_confirmation()
        return
    if args.routes:
        print_routes(app)
        return
    if args.serve:
        AgentOS(agents=[build_agent()], base_app=build_base_app(), telemetry=False).serve(
            app, host=args.host, port=args.port
        )
        return
    print_sample_confirmation()


if __name__ == "__main__":
    main()
