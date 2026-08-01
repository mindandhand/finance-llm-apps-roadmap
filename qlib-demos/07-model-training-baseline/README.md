# 07：Qlib 模型训练基线

## 学习目标

完成本节后，你应该能够用 DataHandlerLP/DatasetH 构造训练数据，用 valid segment 选择模型，并只在 test segment 报告样本外 IC。成功运行时应看到预测行数、test IC 和 score/label 对齐结果。

这一节使用 Qlib `DataHandlerLP`、`DatasetH` 和 `LGBModel` 训练 LightGBM 基线模型，并在 test segment 上产生样本外预测分数。

## 图结构

```mermaid
graph TD
    A["feature / label expression config"] --> B["DataHandlerLP"]
    B --> C["DatasetH train/valid/test"]
    C --> D["LGBModel.fit(dataset)"]
    D --> E["LGBModel.predict(test)"]
    E --> F["score(datetime, instrument)"]
    C --> G["test label"]
    F --> H["join score + label"]
    G --> H
    H --> I["daily IC"]
```

## Python 文件逐段拆解

### `FEATURE_FIELDS` / `LABEL_FIELDS`

这里定义模型输入和训练目标。特征包括动量、收益率波动率、成交量比例，标签是未来收益。
`RETURN_VOLATILITY_20` 表示日收益率的 20 日滚动标准差，不是 20 日成交量。

Qlib 的关键点是：这些不是提前落盘的 CSV 列，而是交给 `QlibDataLoader` 计算的表达式。

### `build_dataset()`

这个函数创建：

```text
DataHandlerLP
  -> QlibDataLoader
  -> learn_processors
  -> DatasetH segments
```

`DataHandlerLP` 负责把表达式加载结果处理成训练/推理可用的数据。`DatasetH` 负责按时间段切出 `train` 和 `test`。

### `learn_processors`

脚本使用：

```text
DropnaLabel
ProcessInf
Fillna
```

这些 Processor 的作用是让训练数据更适合模型：删除无标签样本，处理无穷值，填补缺失特征。正式项目里还要特别注意 infer 和 learn 处理链一致性。

### `LGBModel`

`LGBModel` 是 Qlib 对 LightGBM 的模型封装。它的 `fit(dataset)` 会从 `DatasetH` 中取出 train segment 的 feature/label，再训练模型。

### `model.predict(dataset, segment="test")`

预测阶段只取 test segment 的 feature，输出：

```text
score(datetime, instrument)
```

score 是模型排序信号，不是策略收益。它后续还要进入 IC 评估或组合回测。

### `daily_ic`

脚本把 score 和 test label join 后，按日期计算横截面相关系数。这一步验证模型预测分数是否和未来收益有关系。

## 一次运行的完整执行轨迹

1. 初始化 Qlib。
2. 构造 `DataHandlerLP` 和 `DatasetH`。
3. `LGBModel.fit(dataset)` 训练模型。
4. `model.predict(..., segment="test")` 生成样本外 score。
5. 读取 test label，并计算 daily IC。

## 运行方式

```bash
QLIB_PROVIDER_URI=~/.qlib/qlib_data/cn_data python model_training_baseline.py
```

## 常见坑

- 用 test 数据参与训练或调参。
- 训练和推理处理链不一致。
- 把 label 混进 feature。
- 把 score 当成可交易收益。

## 学习检查

- 删除 valid segment 后观察训练接口或模型选择行为的变化。
- 将模型 test IC 与单一 MOM20 因子的 test IC 比较，而不是只看模型自身结果。

## 下一步

进入 `08-recorder-and-experiment`，用 Qlib Recorder 保存参数、指标和 artifact。
