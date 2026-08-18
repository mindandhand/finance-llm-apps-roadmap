# 02：定义第一个金融 Cube

## 学习目标

用 YAML 把 `transactions` 表变成可查询的语义模型，理解 Cube、Dimension（维度）、Measure（度量）、Primary Key（主键）和生成 SQL 的关系。

运行本章后，应能通过 Cube REST API 查询交易笔数、成交数量和成交金额，并解释为什么无效成员会在到达 PostgreSQL 之前被拒绝。

一句话理解：第 01 章解决“Cube 能否连接数据库”，第 02 章解决“数据库字段在业务上叫什么、怎样统一计算”。

## 复用公共环境

本章不再复制 PostgreSQL、`.env.example`、Compose 或 fixture。它们位于 `cube-demos` 根目录：

```text
cube-demos/
├── .env.example
├── compose.yaml
├── demo.sh
├── data/
└── 02-first-financial-cube/
    ├── README.md
    ├── demo.sh
    ├── model/
    │   └── transactions.yml
    └── test_demo.py
```

章节脚本设置 `CUBE_MODEL_DIR=./02-first-financial-cube/model`，公共 Compose 据此挂载本章模型。第 01、02 章共用一个 PostgreSQL、数据卷、网络和 `4000` 端口；运行某章时，Cube 会切换为该章模型。

## 从表到语义模型

原始表只描述列和约束，没有说明哪些字段用于分组、哪些表达式代表业务指标。`model/transactions.yml` 把这些语义声明为可查询成员：

```yaml
cubes:
  - name: transactions
    title: 交易
    sql_table: public.transactions

    dimensions:
      - name: id
        sql: id
        type: number
        primary_key: true

      - name: side
        title: 交易方向
        sql: side
        type: string

      - name: traded_at
        title: 交易时间
        sql: traded_at
        type: time

    measures:
      - name: count
        title: 交易笔数
        type: count

      - name: total_quantity
        title: 成交数量
        sql: quantity
        type: sum

      - name: total_amount
        title: 成交金额
        sql: "quantity * price"
        type: sum
```

完整模型还公开 `tenant_id`、`portfolio_id` 和 `security_id` 维度，为后续过滤与 Join（关联）章节保留业务标识。

## 中文业务语义在哪里完成

中文名称和计算规则都定义在 `model/transactions.yml`，但各配置项职责不同：

| 中文含义 | `name`（API 成员名） | `title`（Playground 显示名） | `sql` / `type`（数据库映射或计算） |
|---|---|---|---|
| 交易方向 | `side` | `交易方向` | 读取 `side`，类型为字符串 |
| 证券标识 | `security_id` | `证券标识` | 读取 `security_id`，类型为数字 |
| 交易笔数 | `count` | `交易笔数` | `type: count`，生成 `COUNT(*)` |
| 成交数量 | `total_quantity` | `成交数量` | `SUM(quantity)` |
| 成交金额 | `total_amount` | `成交金额` | `SUM(quantity * price)` |

- `name` 是稳定的技术标识，因此 REST API 仍查询 `transactions.total_amount`，不会使用中文名称。
- `title` 和 `description` 面向阅读者，Playground 会用它们解释成员的中文含义和指标口径。
- `sql` 指定原始字段或公式，`type` 告诉 Cube 如何分组或聚合。
- `buy`、`sell` 是数据库中的原始值，本章只给字段添加中文标题，不修改数据值。
- `security_id` 只是内部证券标识；需要关联证券表后，才能取得股票代码等真正的证券代码。

## Dimension 与 Measure

- `side` 是 Dimension，因为消费者可以按 `buy`、`sell` 分组。
- `traded_at` 是 Time Dimension（时间维度），后续可按日期范围过滤和按日、月聚合。
- `count` 是 Measure，表示交易表行数。
- `total_quantity` 是 Measure，Cube 会把 `quantity` 包装为 `SUM(quantity)`。
- `total_amount` 是 Measure，Cube 会把表达式包装为 `SUM(quantity * price)`。

`total_amount` 表示手续费前的成交总额，不根据买卖方向添加正负号，也不扣除 `fee`。这个口径写在模型中，客户端不能自行重新定义。

## Primary Key 为什么重要

`id` 被声明为 Primary Key。单表聚合时通常看不出差异，但后续把交易连接到证券和投资组合时，Cube 会依赖主键和 Join 基数避免 fan-out（连接后行数膨胀）导致重复聚合。

## 运行

```bash
cd cube-demos/02-first-financial-cube
./demo.sh
```

脚本会：

1. 调用根目录公共入口启动或更新 Cube 与 PostgreSQL。
2. 查询全部交易的三个 Measure。
3. 按 `side` Dimension 分组并断言 BUY/SELL 结果。
4. 查询 `transactions.not_a_member`，断言 Cube 返回 HTTP 400。

预期输出：

```text
transaction totals: {'transactions.count': '8', 'transactions.total_quantity': '27800.0000', 'transactions.total_amount': '209350.00000000'}
side breakdown: {'buy': (...), 'sell': (...)}
invalid member rejected: HTTP 400
Chapter 02 passed.
```

常用命令：

```bash
./demo.sh verify  # 验证当前第 02 章模型和结果
./demo.sh logs    # 查看公共 Cube/PostgreSQL 日志
./demo.sh stop    # 停止公共环境并保留数据卷
./demo.sh reset   # 重建公共数据卷并重新验证本章
```

## Playground 测试例子

打开 `http://127.0.0.1:4000`，进入 Build（查询构建）页面：

1. 在 `transactions` Cube 下选择 Measures：`count`、`total_quantity`、`total_amount`。
2. 选择 Dimension：`side`。
3. 点击 Run Query（执行查询）。

预期结果：

| `side` | `count` | `total_quantity` | `total_amount` |
|---|---:|---:|---:|
| `buy` | 7 | 26800 | 203650 |
| `sell` | 1 | 1000 | 5700 |

Playground 背后的 Cube Query（Cube 语义查询）等价于：

```json
{
  "measures": [
    "transactions.count",
    "transactions.total_quantity",
    "transactions.total_amount"
  ],
  "dimensions": ["transactions.side"]
}
```

Cube 概念上生成类似以下 SQL，具体别名由 Cube 决定：

```sql
SELECT
    side,
    COUNT(*) AS count,
    SUM(quantity) AS total_quantity,
    SUM(quantity * price) AS total_amount
FROM public.transactions
GROUP BY side;
```

客户端只选择模型公开的成员，没有传入表名或指标公式。

## 自动化测试

静态契约测试：

```bash
python3 -m unittest test_demo.py -v
```

真实集成验证：

```bash
./demo.sh verify
```

测试不只断言 HTTP 200，还断言固定 fixture 的精确数值：

- 总计：8 笔、27800 单位、成交总额 209350；
- BUY：7 笔、26800 单位、成交总额 203650；
- SELL：1 笔、1000 单位、成交总额 5700；
- 无效成员：HTTP 400，错误响应包含被拒绝的成员名。

## 常见误区

- 把 `price` 定义为 `sum`，得到没有业务意义的价格总和。
- 用浮点类型保存货币，产生精度问题；公共 fixture 使用 PostgreSQL `NUMERIC`。
- 在客户端重复计算 `quantity * price`，破坏统一指标口径。
- 把 `sell` 数量自动当成负数；本章的 `total_quantity` 明确定义为绝对成交数量之和。
- 认为 YAML 语法通过就代表业务定义正确；本章还用独立固定结果验证指标含义。

## 验收标准

- `./demo.sh` 一条命令加载本章模型并完成验证。
- 能查询交易笔数、成交数量和成交金额。
- 按买卖方向分组的结果与固定 fixture 一致。
- 无效成员在语义层明确失败。
- 第 01、02 章共用根目录环境，不复制 `.env`、Compose 和数据库 fixture。

## 下一步

第 03 章加入时间粒度和日期范围，把单个聚合值扩展为金融时间序列。
