# 06：Qlib 单因子评估

## 学习目标

完成本节后，你应该能够计算并解释 coverage、IC、RankIC、ICIR 和分组收益，同时根据横截面数量与有效日期判断指标是否可靠。成功运行时 JSON 应同时包含指标、样本诊断和 `warnings`。

这一节把一个候选 Qlib 表达式和一个未来收益标签对齐，计算 coverage、IC、RankIC、ICIR 和分组收益。它是自动因子评估服务的核心函数。

## 图结构

```mermaid
graph TD
    A["factor expression"] --> C["D.features"]
    B["label expression"] --> C
    C --> D["dropna 后的 factor/label 表"]
    D --> E["按 datetime 分组"]
    E --> F["Pearson IC"]
    E --> G["Spearman RankIC"]
    E --> H["qcut 分组收益"]
    F --> I["JSON metrics"]
    G --> I
    H --> I
```

## Python 文件逐段拆解

### `DEFAULT_FACTOR` / `DEFAULT_LABEL`

默认候选因子：

```python
DEFAULT_FACTOR = "$close / Ref($close, 20) - 1"
```

默认标签：

```python
DEFAULT_LABEL = "Ref($close, -5) / $close - 1"
```

因子只看过去，标签看未来。这个边界是自动因子评估里最重要的安全线。

### `evaluate_factor(expression, label, quantiles=5)`

这是本节的核心函数。输入是两个 Qlib 表达式，输出是一个普通 Python `dict`，方便后续 CLI、Recorder 或 Agent 调用。

第一步调用：

```python
load_features([expression, label], ["factor", "label"])
```

底层仍是 `D.features`。Qlib 负责表达式计算和时间/标的对齐。

### `coverage`

```python
coverage = len(data.dropna()) / len(data)
```

coverage 衡量表达式计算后有多少样本可用。滚动窗口太长、字段缺失、停牌或表达式非法都会降低 coverage。

### IC

```python
g["factor"].corr(g["label"])
```

每天在横截面上计算 Pearson 相关系数。它回答：因子数值和未来收益数值是否同向变化？

### RankIC

```python
g["factor"].rank().corr(g["label"].rank())
```

每天先分别计算因子排名和标签排名，再对排名计算 Pearson 相关；这就是 Spearman 等级相关。它回答：因子排序和未来收益排序是否一致？选股研究通常更关注这个指标。

### ICIR 与统计诊断

```python
ic_mean / ic_std
```

`icir_daily` 是未年化的每日 IC 均值除以标准差；`icir_annualized` 再乘以 `sqrt(252)`。脚本还输出有效 IC 日期数、正 IC 日期比例和基础 t 统计量。平均 IC 高但波动也高，未必是好信号；这些诊断也不能消除小股票池、序列相关或反复筛选造成的偏差。

### 分组收益

```python
pd.qcut(group["factor"].rank(method="first"), bucket_count)
```

先按因子值做横截面分组，再计算每组未来收益均值。分组数不会超过当天有效标的数。它用于观察因子是否有单调性。

## 一次运行的完整执行轨迹

1. 从环境变量读取 `QLIB_FACTOR_EXPR` 和 `QLIB_LABEL_EXPR`。
2. 初始化 Qlib provider。
3. `D.features` 计算 factor 和 label。
4. 按日期分组计算 IC、RankIC、分组收益。
5. 打印 JSON metrics。

## 运行方式

```bash
QLIB_PROVIDER_URI=~/.qlib/qlib_data/cn_data python factor_evaluation.py
```

可选：

```bash
QLIB_FACTOR_EXPR='$close / Ref($close, 20) - 1' \
QLIB_LABEL_EXPR='Ref($close, -5) / $close - 1' \
python factor_evaluation.py
```

## 常见坑

- 横截面标的太少，IC/RankIC 没有统计意义。
- 只看平均 IC，不看 IC 稳定性。
- 反复用测试期筛因子。
- 因子方向不统一，导致正负号解释混乱。

## 学习检查

- 依次评估动量、动量取负和常数因子，比较 IC 方向与告警。
- 把 `quantiles` 从 3 改为 2，解释五只 ETF 下为什么结果仍不能用于显著性判断。

## 下一步

进入 `07-model-training-baseline`，把多个 Qlib 特征放进模型，生成样本外预测分数。
