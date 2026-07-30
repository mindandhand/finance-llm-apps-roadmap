# 07 Human Confirmation：人工确认

这个 demo 展示高风险动作的边界：Agent 可以起草调仓动作，但不能直接执行。动作会先进入 `pending` 状态，前端或人工调用确认接口后，才会变成 `approved` 或 `rejected`。

## 运行

```bash
cd agno-demos
./script/run_07.sh --sample-confirmation
./script/run_07.sh --serve --port 7777
./script/run_07.sh --print-examples
```

关键接口：

- `GET /risk-actions`
- `POST /risk-actions`
- `POST /risk-actions/{action_id}/approve`
- `POST /risk-actions/{action_id}/reject`
- `POST /agents/human-confirmation-agent/runs`

## 浏览器模拟用户点击

启动服务后打开：`http://127.0.0.1:7777/human-confirmation-ui`。

页面会执行这条链路：

1. 点击“创建待确认动作”，调用 `POST /risk-actions`，页面显示 `pending`。
2. 点击“批准”或“拒绝”，调用对应的决策接口。
3. 按钮被禁用，页面刷新为 `approved` 或 `rejected`，同一个动作不能重复决定。

这个页面是 07 自带的测试 UI，适合验证人工确认状态机。Agno Agent UI 可以用来发消息、验证 Agent 是否正确调用 `prepare_rebalance_action`；但它不会自动把自定义的 `approve/reject` 接口渲染成按钮，所以最终确认动作要用这个页面或自行扩展前端。

## 测试思路

先用 `POST /risk-actions` 创建动作，确认返回 `confirmation_required=true` 和 `status=pending`。再调用 approve/reject，确认状态被显式改变。真实产品里，这一步应该由 UI 展示风险说明后由用户点击完成。
