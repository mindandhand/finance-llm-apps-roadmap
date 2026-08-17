# 02：定义第一个金融 Cube

## 学习目标

用 YAML 把 `transactions` 表变成可查询的语义模型，理解 Cube、dimension、measure、primary key 和生成 SQL 的关系。

> 本章尚未实现代码，示例展示计划采用的模型形态。

## 从表到语义模型

原始表告诉数据库有哪些列，却没有告诉消费者哪一列能分组、哪一列应求和、成交金额采用什么公式。Cube 把这些业务语义声明为成员：

```yaml
cubes:
  - name: transactions
    sql_table: transactions

    dimensions:
      - name: id
        sql: id
        type: number
        primary_key: true
      - name: side
        sql: side
        type: string
      - name: traded_at
        sql: traded_at
        type: time

    measures:
      - name: count
        type: count
      - name: total_quantity
        sql: quantity
        type: sum
      - name: total_amount
        sql: quantity * price
        type: sum
```

实际实现会按固定的 Cube 版本验证语法，不能仅凭示意配置运行。

## Dimension 与 Measure 的区别

`side` 是 dimension，因为可以按 BUY/SELL 分组；`traded_at` 是时间 dimension，因为可以按日期范围筛选；`total_amount` 是 measure，因为它跨多笔交易求和。

判断方法不是“字符串就是 dimension、数字就是 measure”。证券 ID 是数字但仍是标识维度；成交金额也是数字，却具有聚合语义。

## Primary key 为什么重要

主键声明告诉 Cube 一行事实如何唯一识别。单表查询可能看不出影响，进入 Join 后错误或缺失的主键会让去重和基数推断失去可靠基础。主键不是为了让界面更好看，而是保证后续模型正确性的契约。

## 查询如何变成 SQL

语义查询：

```json
{
  "measures": ["transactions.total_amount"],
  "dimensions": ["transactions.side"]
}
```

概念上会生成类似：

```sql
SELECT side, SUM(quantity * price)
FROM transactions
GROUP BY side;
```

客户端没有决定表名、Join 或公式，只选择模型允许的成员。这正是语义层与“API 里拼 SQL”的根本差异。

## 实操步骤

1. 启动第 01 章环境。
2. 添加 `transactions` YAML 模型。
3. 在 Playground 查看成员是否成功编译。
4. 查询交易数、数量和金额。
5. 查看生成 SQL，并用 PostgreSQL 基准 SQL 交叉验证。

## 正确性测试

固定 fixture 至少包含 BUY、SELL、多证券和不同日期。测试不能只断言 HTTP 200，还要断言实际数值。增加一条交易后，明确哪些 measure 应变化以及变化多少。

## 常见误区

- 把 `price` 定义为 `sum`，得到没有业务意义的价格总和。
- 用浮点类型保存货币，产生精度问题；fixture 应使用适合货币的定点数。
- 在客户端重复计算 `quantity * price`，破坏统一口径。
- 认为 YAML 能阻止一切错误；语法正确不等于业务定义正确。

## 验收标准

- 能查询交易数量、成交数量和成交金额。
- 固定 fixture 上的指标结果有自动化断言。
- 无效成员查询明确失败。

## 下一步

第 03 章加入时间粒度和日期范围，把单个聚合值扩展为金融时间序列。
