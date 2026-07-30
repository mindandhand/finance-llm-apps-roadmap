# 09 Workflow Report：工作流生成报告

这个 demo 展示固定步骤的报告生成：收集输入、计算指标、生成结论、渲染报告、保存 artifact。

它提供两种模式：

- 默认模式使用本地固定样例数据和固定结论，不调用大模型，适合离线测试。
- `--llm` 或 `use_model=true` 模式调用 DeepSeek，根据已经计算好的结构化因子数据生成报告结论。

因此，09 同时演示了 Workflow 的可控步骤和大模型在其中承担的“解释结论”职责。模型不会自行抓取行情，也不能绕过前面的输入校验。

## 执行流程

一次报告请求的执行顺序如下：

```text
CLI / POST /reports
        |
        v
1. collect_inputs
   接收 symbols、title 和 use_model
        |
        v
2. normalize_symbol
   统一标的格式，并拒绝不支持的标的
        |
        v
3. compute_metrics
   从本地样例数据计算动量和波动率
        |
        v
4. generate_model_summary
   use_model=false：使用固定结论
   use_model=true ：调用 DeepSeek 解释结构化数据
        |
        v
5. render_report
   生成 Markdown 内容
        |
        v
6. save_artifact
   写入 artifacts/<artifact_id>.md
        |
        v
返回 artifact_id、路径和元数据
```

离线模式和模型模式只在第 4 步有区别，前面的输入校验和指标计算保持一致。模型调用失败时流程停止，不会返回一个伪装成成功的报告。

## 运行

```bash
cd agno-demos
./script/run_09.sh --sample-report
./script/run_09.sh --serve --port 7777
```

默认报告使用固定样例数据和固定结论，便于离线测试。要让大模型参与结论生成，确认上层 `.env` 已配置 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY`，然后运行：

```bash
./script/run_09.sh --sample-report --llm
```

如果模型服务不可访问，`--llm` 会明确返回模型错误，不会把错误文本保存成成功报告。确认上层 `.env` 中的 key、模型地址和本机网络可用后再重试。

服务模式下也可以在 `POST /reports` 的 JSON 中传入：

```json
{"symbols":["SH510300","SH588000"],"title":"ETF 研究报告","use_model":true}
```

此时 Workflow 仍先校验标的并计算本地因子，再把结构化数据交给模型生成结论，最后保存为 Markdown artifact。模型只负责解释已提供的数据，不负责自行抓取行情。

`POST /reports` 示例：

```bash
curl -s -X POST http://127.0.0.1:7777/reports \
  -H 'Content-Type: application/json' \
  -d '{"symbols":["SH510300","SH588000"],"title":"ETF 研究报告","use_model":true}'
```

响应中的 `artifact_id` 用于下载报告：

```bash
curl -s -o report.md \
  http://127.0.0.1:7777/reports/<ARTIFACT_ID>/download
```

接口：

- `POST /reports`
- `GET /reports`
- `GET /reports/{artifact_id}/download`

生成的 Markdown 报告保存在 `09-workflow-report/artifacts/`。
