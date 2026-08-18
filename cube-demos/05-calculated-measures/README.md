# 05：定义计算指标

## 学习目标

理解基础 measure、计算 measure、加性与非加性指标，正确实现加权平均成交价和组合权重等教学指标。

本章提供可运行的 `transactions` 模型，在第 02 章基础指标上增加 `weighted_average_price`。

## 本章究竟解决什么问题

数据库保存的是每笔交易的“数量”和“价格”，第 02 章已经能计算总金额、总数量等基础聚合。但业务经常询问“这批交易的实际平均成交成本是多少”，它既不是数据库的一列，也不能用简单 `AVG(price)` 正确回答。

计算 Measure 的目的，是把多个基础 Measure 组合成一个有明确业务含义、可重复使用的指标。本章把：

```text
加权平均成交价 = 总成交金额 / 总成交数量
```

集中定义在 Cube 中，从而保证 Playground、REST API、Pandas、Dashboard 和 LLM 使用完全相同的公式。无论查询全体交易、BUY、SELL 还是某一天，Cube 都会在当前分组中重新计算总金额和总数量后再相除。

本章解决的是**指标口径统一和计算正确性**，不是查询性能；性能优化由第 08 章的预聚合处理。

## 为什么计算指标容易错

`SUM(price) / COUNT(*)` 是价格的简单平均，`SUM(quantity * price) / SUM(quantity)` 才是按成交量加权的平均成交价。两者都能执行，却回答不同问题。语义层的价值在于把选定公式集中定义并命名，而不是自动替你选择公式。

先看两笔最小数据：

| 成交数量 | 成交价格 | 成交金额 `数量 × 价格` |
|---:|---:|---:|
| 1 | 10 | 10 |
| 9 | 20 | 180 |

普通平均价格是 `(10 + 20) / 2 = 15`，它把数量 1 和数量 9 的交易看得同样重要。加权平均价格则是：

```text
总成交金额 / 总成交数量
= (10 + 180) / (1 + 9)
= 19
```

因为 90% 的成交数量发生在价格 20，所以 19 更能代表实际平均成交成本。

## 基础 Measure 和计算 Measure

- `total_amount` 是基础 Measure：`SUM(quantity * price)`；
- `total_quantity` 是基础 Measure：`SUM(quantity)`；
- `weighted_average_price` 是计算 Measure：`total_amount / total_quantity`。

计算 Measure 不直接聚合新的数据库字段，而是组合已经定义好的基础 Measure。

## 指标分类

| 类型 | 例子 | 能否跨分组直接相加 |
|---|---|---|
| 加性 | 成交金额、成交数量 | 通常可以 |
| 半加性 | 某日持仓市值 | 可跨证券求和，不能直接跨时间求和 |
| 非加性 | 收益率、权重、平均价格 | 不可以，应从组成项重新计算 |

例如 BUY 平均价和 SELL 平均价不能直接相加或再做简单平均。全体平均价必须重新使用基础项计算：

```text
全体加权均价 = (BUY 金额 + SELL 金额) / (BUY 数量 + SELL 数量)
```

计算 measure 应尽量引用已有 measure，让公式复用同一口径。例如平均成交价依赖 `total_amount / total_quantity`，而不是复制两段底层 SQL。

```yaml
- name: weighted_average_price
  title: 加权平均成交价
  sql: "{total_amount} / NULLIF({total_quantity}, 0)"
  type: number
```

## 底层如何处理

Cube 先把 `total_amount` 和 `total_quantity` 分别编译成 `SUM(quantity * price)` 与 `SUM(quantity)`，再把计算 Measure 展开为两项聚合结果的除法。它不是对每行先算平均价，也不是对子组平均价再次求平均。`NULLIF(..., 0)` 把零分母转为 `NULL`，防止数据库除零错误。

最终核心 SQL 等价于：

```sql
SUM(quantity * price) / NULLIF(SUM(quantity), 0)
```

如果总成交数量为 0，`NULLIF` 会把分母转换成 `NULL`。PostgreSQL 返回“无法计算”，而不是抛出除零错误，也不会用数字 0 冒充平均价。

```text
选择计算 Measure → 展开基础 Measure → PostgreSQL 聚合 → 聚合结果相除 → 返回 Decimal 字符串
```

## 运行与验证

```bash
cd cube-demos/05-calculated-measures
./demo.sh
python3 -m unittest test_demo.py -v
```

固定数据的成交金额为 `209350`、成交数量为 `27800`，加权平均成交价约为 `7.53057554`。脚本使用 Python `Decimal` 独立重算并比较，避免浮点误差。

## Playground 中如何找到指标

切换章节后，已打开的 Playground 可能仍保留上一章的成员列表。打开 `http://127.0.0.1:4000` 后先强制刷新页面：macOS 使用 `Command + Shift + R`，Windows/Linux 使用 `Ctrl + Shift + R`。

不同 Playground 界面可能显示中文标题或英文技术名，可以按下面的对应关系查找：

| 中文显示 | 英文技术名 |
|---|---|
| 交易计算指标 | `transactions` |
| 成交金额 | `total_amount` |
| 成交数量 | `total_quantity` |
| 加权平均成交价 | `weighted_average_price` |
| 交易方向 | `side` |

在 Build 页面展开 `transactions`，从 Measures 中选择 `total_amount`、`total_quantity` 和 `weighted_average_price`。如果仍看不到，可直接打开 `http://127.0.0.1:4000/cubejs-api/v1/meta`，搜索 `weighted_average_price`；存在该成员就说明 05 模型已经加载，问题只是浏览器页面没有刷新。

## 零分母与空值

没有成交量时，比率应该返回 `NULL`、0 还是错误，必须明确。教程将优先保留 `NULL` 表示“不可计算”，由展示层决定如何呈现，而不是把未知结果伪装成 0。

## 正确性验证

fixture 至少覆盖不同数量、不同价格、零数量或空集合。独立使用 Decimal 或数据库定点计算给出期望值，并验证更换分组粒度后，非加性指标由基础项重算，而不是对子组结果求和。

## 常见误区

- 对百分比直接求和或平均。
- 用浮点近似值做精确相等断言。
- 在 Dashboard 再写一遍公式。
- 指标名没有说明 gross/net、币种、时点或时间窗口。

## 验收标准

- 每个计算指标有书面公式。
- 固定样本覆盖正常值、零分母和空值。
- Cube 结果与独立基准计算一致。

## 下一步

第 06 章把这些指标作为 API 契约交给 Python 客户端。
