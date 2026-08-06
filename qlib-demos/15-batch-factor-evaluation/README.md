# 15：批量因子评估与实验汇总

## 学习目标

这一节在第 14 节稳定的单因子契约之上增加本地顺序编排：从 JSON 读取多个候选，使用相同标签和参数逐个评估，保留每个成功、失败和告警，并输出一份汇总 JSON。

它不重新实现 IC，也不引入任务队列、数据库或并行框架。数值计算仍只有一个入口：第 14 节的 `evaluate_request()`。

一句话理解：**第 14 节像一台只检测一个样品的仪器，第 15 节像实验登记员，负责给多个样品编号、逐个送检，并把成功和失败整理成一份报告。**

## 和第 14 节的职责边界

| 层次 | 负责什么 | 不负责什么 |
| --- | --- | --- |
| Demo 14 单因子服务 | 校验一个表达式、读取数据、计算 IC/RankIC/分组收益、返回稳定结果 | 不读取候选列表，不比较多个实验 |
| Demo 15 批处理器 | 读取候选列表、统一参数、依次调用 Demo 14、隔离失败、生成汇总 | 不重新计算指标，不自动宣称因子有效 |

保持这个边界的好处是：无论用户手工运行一个因子，还是 Agent 一次提交一百个因子，数值真值都来自同一个函数，避免单因子和批处理得到不同口径的结果。

## 处理流程

```text
candidates.json
  -> 校验批次级配置
  -> 预检 Qlib 环境
  -> 候选 A 调用 Demo 14
  -> 候选 B 调用 Demo 14
  -> 候选 C 调用 Demo 14
  -> 汇总成功、失败和 RankIC 排名
  -> stdout / 可选 JSON 文件
```

单个候选失败不会中断批次。配置文件损坏、schema 不匹配、候选名称重复或 Qlib 环境不可用属于批次级错误，会在开始评估前结束。

## 一次运行的完整轨迹

1. `parse_args()` 读取 `--input` 和可选的 `--output`。
2. `load_config()` 读取 JSON，校验 schema、统一标签、控制参数和候选名称。
3. `init_qlib()` 预检 provider 是否可用。
4. `evaluate_batch()` 按输入顺序处理候选。
5. 每个候选调用 Demo 14 的 `evaluate_request()`。
6. 成功候选保存完整 `metrics`；失败候选保存结构化 `error`。
7. 汇总总数、成功数、失败数，并生成 RankIC 诊断排名。
8. 将同一份 JSON 打印到 stdout，并可选写入文件。

## 输入配置

仓库提供 `candidates.json`：

```json
{
  "schema_version": "1.0",
  "label": "Ref($close, -5) / $close - 1",
  "quantiles": 3,
  "min_cross_section": 3,
  "candidates": [
    {
      "name": "momentum_20d",
      "expression": "$close / Ref($close, 20) - 1"
    }
  ]
}
```

标签、分组数和最小横截面由整个批次共享，防止不同候选使用不同评估口径后被错误比较。候选名称必须唯一，便于后续追踪和重跑。

三个默认候选分别表示：

| 名称 | 表达式 | 含义 |
| --- | --- | --- |
| `momentum_20d` | `$close / Ref($close, 20) - 1` | 过去 20 个交易日的价格涨幅 |
| `ma_deviation_10d` | `$close / Mean($close, 10) - 1` | 当前价格相对 10 日均价的偏离程度 |
| `volume_ratio_20d` | `$volume / Mean($volume, 20)` | 当前成交量相对 20 日均量的倍数 |

它们都使用同一个“未来 5 日收益”标签，所以 RankIC 才可以放进同一张诊断排名。

## 运行方式

从仓库根目录运行：

```bash
./qlib-demos/script/run_15.sh
```

直接调用并保存结果：

```bash
python qlib-demos/15-batch-factor-evaluation/batch_factor_evaluation.py \
  --input qlib-demos/15-batch-factor-evaluation/candidates.json \
  --output qlib-demos/15-batch-factor-evaluation/artifacts/summary.json
```

## 输出与退出码

输出包含：

- `status`：全部成功为 `ok`，部分候选失败为 `partial`。
- `summary`：候选总数、成功数和失败数。
- `ranked_by_abs_rank_ic`：按 `abs(rank_ic_mean)` 排序的诊断列表。
- `results`：每个候选完整的 metrics 或结构化 error。

成功批次的简化结构如下：

```json
{
  "schema_version": "1.0",
  "status": "ok",
  "label": "Ref($close, -5) / $close - 1",
  "summary": {
    "total": 3,
    "succeeded": 3,
    "failed": 0
  },
  "ranked_by_abs_rank_ic": [
    {"name": "momentum_20d", "rank_ic_mean": 0.057689}
  ],
  "results": [
    {
      "name": "momentum_20d",
      "expression": "$close / Ref($close, 20) - 1",
      "status": "ok",
      "metrics": {"rank_ic_mean": 0.057689}
    }
  ]
}
```

`results` 才是完整事实记录；`ranked_by_abs_rank_ic` 只是从成功结果中抽出的快捷索引。没有有效 RankIC 的成功候选仍保留在 `results` 中，但不会进入排名。

## 候选失败为什么不会中断

例如加入一个读取未来价格的非法候选：

```json
{
  "name": "leaked_future_return",
  "expression": "Ref($close, -5) / $close - 1"
}
```

该项会得到：

```json
{
  "name": "leaked_future_return",
  "expression": "Ref($close, -5) / $close - 1",
  "status": "error",
  "error": {
    "code": "invalid_input",
    "type": "FutureDataLeakageError",
    "message": "factor expression must not use negative Ref offsets because they read future data"
  }
}
```

批次状态变成 `partial`，进程退出码为 1，但后面的合法候选仍会继续评估。这样失败候选不会丢失，也不会让一次长批次前功尽弃。

退出码：

| 退出码 | 含义 |
| --- | --- |
| `0` | 所有候选评估成功 |
| `1` | 部分候选失败、环境错误或输出文件错误 |
| `2` | 批量配置格式错误 |

按 RankIC 绝对值排序只是帮助检查信号强度，不能自动证明候选值得交易。正负方向、coverage、稳定性、分组单调性、经济含义和样本外回测仍需共同判断。

### 为什么使用 RankIC 绝对值

正 RankIC 表示因子排序与未来收益排序大体同向；负 RankIC 表示大体反向。如果负值长期稳定，反转因子方向后可能仍有研究价值，因此排序保留符号但使用绝对值比较强弱。

这仍然不是自动录取规则。至少还要检查：

- `coverage` 是否足够高。
- `rank_ic_std` 和 ICIR 是否显示一定稳定性。
- 分组收益是否具有合理单调性。
- 表达式是否有清晰经济含义。
- 更大股票池和样本外区间是否仍成立。
- 进入第 12 节一类的组合回测后，成本、换手和回撤是否可接受。

## 为什么暂时顺序执行

当前教学数据只有五只 ETF，单次评估成本较低。顺序执行最容易观察失败隔离和结果契约。只有候选达到数百或数千、运行时间成为瓶颈，并且需要超时、重试、断点恢复或多用户提交时，才值得继续引入并行执行、任务队列和实验数据库。

## 学习检查

- 添加一个含负数 `Ref` 偏移的候选，确认其他候选仍继续执行。
- 重复一个候选名称，确认整个批次在计算前失败。
- 使用相同候选但更换统一 label，比较排名变化，并解释为什么两次批次不能直接混排。
