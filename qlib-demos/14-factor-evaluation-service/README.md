# 14：自动因子评估服务

## 学习目标

完成本节后，你应该能够通过稳定 CLI 调用确定性因子评估，处理成功和失败 JSON、退出码、输出文件及小样本告警。成功输出包含 `schema_version`、`status` 和 `metrics`；失败输出包含结构化 `error`。

这一节把 Qlib 数据读取、表达式计算、标签构造和指标评估收口成一个 CLI。它是后续 Agent / LangGraph 自动因子挖掘系统可以调用的确定性入口。

## 图结构

```mermaid
graph TD
    A["CLI args / Agent candidate"] --> B["parse_args()"]
    B --> C["init_qlib()"]
    C --> D["evaluate_factor(expression, label)"]
    D --> E["D.features"]
    E --> F["coverage / IC / RankIC / ICIR / quantile returns"]
    F --> G["JSON stdout"]
    F --> H["optional output file"]
```

## Python 文件逐段拆解

### `parse_args()`

定义 CLI 参数：

```text
--expression
--label
--output
```

这让外部系统可以把候选因子表达式作为参数传入，而不是修改源码。

### `init_qlib()`

服务启动后先初始化 Qlib provider。没有 provider 时直接失败，因为评估必须由 Qlib 数据层确定性计算。

### `evaluate_factor(args.expression, args.label)`

复用第 6 节的核心函数。这样 CLI 只是薄封装，指标逻辑集中在一个地方，便于测试和复用。

### `--output`

如果传入输出路径，脚本把 JSON metrics 写入文件；否则打印到 stdout。Agent 调用时通常读取 stdout 或指定 output file。

## 一次运行的完整执行轨迹

1. Agent 或用户传入候选表达式。
2. CLI 解析参数。
3. 初始化 Qlib。
4. 调用 `evaluate_factor`。
5. 输出 JSON 指标。
6. 上游系统根据指标决定接受、拒绝或继续观察。

## 运行方式

```bash
QLIB_PROVIDER_URI=~/.qlib/qlib_data/cn_data \
python factor_evaluation_service.py \
  --expression '$close / Ref($close, 20) - 1' \
  --label 'Ref($close, -5) / $close - 1'
```

输出到文件：

```bash
python factor_evaluation_service.py \
  --expression '$close / Ref($close, 20) - 1' \
  --output artifacts/mom20.json
```

## 输出 schema

```json
{
  "schema_version": "1.0",
  "status": "ok",
  "metrics": {
    "expression": "$close / Ref($close, 20) - 1",
    "label": "Ref($close, -5) / $close - 1",
    "rows": 12345,
    "coverage": 0.98,
    "cross_section_median": 300,
    "ic_days": 240,
    "ic_mean": 0.02,
    "ic_std": 0.05,
    "ic_positive_ratio": 0.58,
    "ic_t_stat": 6.2,
    "rank_ic_mean": 0.03,
    "icir_daily": 0.4,
    "icir_annualized": 6.349803,
    "quantile_return_mean": {},
    "warnings": []
  }
}
```

非法表达式或环境错误返回 `status: "error"`、结构化错误类型和消息，并以退出码 1 结束。输出禁止出现非标准 JSON 值 `NaN` 和 `Infinity`。

## 核心原理

LLM/Agent 可以生成候选，但不能凭语言判断因子好坏：

```mermaid
graph LR
    A["LLM candidate"] --> B["Qlib deterministic evaluation"]
    B --> C["metrics"]
    C --> D["rule / human decision"]
```

数值计算、时间对齐、缺失处理和评估记录必须由确定性程序完成。

## 常见坑

- 让 Agent 直接解释因子好坏，不跑数据。
- 没有固定 label 和时间区间，导致候选不可比。
- 单标的评估 IC，缺少横截面意义。
- 不保存失败候选。

## 学习检查

- 分别传入合法表达式和非法表达式，检查 JSON 的 `status` 与进程退出码。
- 使用 `--output` 保存结果，并确认 stdout 与文件具有相同 schema。
- 设计一个包含三个候选表达式的批处理调用，记录成功和失败候选。
