# 08 Team Research：多 Agent 金融研究团队

这个 demo 把一个金融研究任务拆给三个角色：`Researcher` 收集样例行情和新闻，`Analyst` 比较因子，`Reviewer` 检查证据和风险提示。

## 运行

```bash
cd agno-demos
./script/run_08.sh --sample-team
./script/run_08.sh --serve --port 7777
```

AgentOS 会注册 Team：

- `finance-research-team`

可在 `/docs` 或 `/teams` 中查看。真实调用会消耗模型 API；`--sample-team` 只展示团队分工，不调用模型。
