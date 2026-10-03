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
  -> 比较有效样本指纹，相同才按选择期 RankIC 排名
  -> 冻结前 top_k 名，只对这些候选评估最终测试期
  -> 汇总结果、数据版本和代码版本
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
  "selection_period": {"start": "2020-01-01", "end": "2020-09-30"},
  "test_period": {"start": "2020-10-01", "end": "2020-12-31"},
  "top_k": 1,
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

它们使用同一个“未来 5 日收益”标签；仍需检查实际有效日期和标的完全相同，才能放进同一张诊断排名。不同回看窗口、缺失值和常量因子都可能改变有效样本。

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

- `request`：补齐默认值后的完整批量配置，包括 `top_k`、候选表达式和区间，便于重建请求。
- `status`：全部成功为 `ok`，部分候选失败为 `partial`。
- `summary`：候选总数、成功数和失败数。
- `ranked_by_abs_rank_ic`：仅在有效样本完全相同时，按选择期 `abs(rank_ic_mean)` 排序。
- `comparison`：有效 RankIC 日期—标的样本是否相同；未知或不同会禁用排名及最终测试选择。
- `selected_candidates`：依据选择期排名冻结的前 `top_k` 名，保留选择期符号和分数。
- `final_test`：仅对冻结名单计算的测试期结果及独立成功/失败统计；不产生测试期排名。
- `evaluation_context`：运行 ID、UTC 时间、日期区间、标的配置、provider 路径/内容 SHA256、Git revision、实际核心源文件 SHA256、配置 SHA256，以及实际 Python / pyqlib / pandas / numpy / scipy 版本。
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

上面的 JSON 省略了追溯、样本比较和测试字段，数字仅用于说明结构。`results` 才是选择期完整事实记录；`ranked_by_abs_rank_ic` 只是从成功结果中抽出的快捷索引。没有有效 RankIC 的成功候选仍保留在 `results` 中，但不会进入排名。

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

## 选择期与最终测试期

仓库配置明确设置两个互不重叠的区间，`selection_period.end` 必须早于 `test_period.start`。先在选择期评估全部候选，按绝对 RankIC 冻结 `top_k` 名，再只对冻结名单计算测试指标。测试指标不参与排名、方向选择或名单调整。第 6 节会依据标签未来窗口和交易日历，剔除标签越过各自区间结束日期的样本，避免选择标签读取测试期收益。

两个区间必须同时配置。只做样本内诊断时，可配置 `evaluation_period: {"start": "2020-01-01", "end": "2020-12-31"}`；它与 `selection_period` / `test_period` 互斥，不接受 `null` 或空对象。旧配置省略所有区间时，首次校验从 `QLIB_START_TIME` / `QLIB_END_TIME` 读取日期，并固化到输出 `request.evaluation_period`。重放该 `request` 会保留原日期和配置指纹，即使环境日期已改变，也不会自动请求最终测试；诊断结果仍明确告警。

`request` 固化的是评估日期和批量参数。provider、标的池、市场和依赖版本仍需按 `evaluation_context` 恢复，不能只靠 `request` 重建所有环境。`QLIB_REGION` 仅接受 `cn` / `us`（大小写兼容），未知值会在初始化 Qlib 前报错；追溯记录使用与实际初始化相同的归一化值。

最终测试失败也保持候选隔离：选择结果仍保留，`final_test.summary` 单独计数，总状态变为 `partial`。若要求最终测试却因样本不可比或无有效 RankIC 而无法选择，最终测试明确标为 `skipped`，总状态同样为 `partial`。可比较候选不足 `top_k`、或测试期没有有效 RankIC，也会明确报告原因并标为 `partial`；测试期空样本不计入成功。

这是一次研究运行中的分离机制，不会阻止人为反复查看同一测试期后修改候选。看过测试结果再调参，该区间就不再是未见测试集，应使用新的留出区间；本节不提供跨运行的测试集封存管理。

## 版本追溯与可比较样本

批次启动时对 provider 的日历/标的池 txt 和行情 features bin 内容计算 SHA256，对实际参与计算的核心 Python 文件计算 SHA256，并记录 Git revision。未提交代码修改会反映在源文件指纹中，同路径数据被替换会反映在 provider 指纹中。完整数据指纹需要读取一次这些核心数据文件；本实现适合教学小数据，真实大数据应使用受控的不可变快照版本。运行期间应保持 provider 不变。标的池配置在 `evaluation_context` 中，实际参与 RankIC 的日期—标的行集合由每个候选的 `metrics.sample.index_sha256` 标识。

相同 coverage、相同标签甚至相同有效天数都不足以证明样本相同。若成功且具有有限 RankIC 的候选指纹不一致，保留全部指标和告警，但不生成排名或测试名单；本节不另算“共同样本”指标。

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
