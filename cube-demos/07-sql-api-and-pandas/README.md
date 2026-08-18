# 07：通过 SQL API 接入 Pandas

## 学习目标

理解 Cube SQL API 与源数据库 SQL 的区别，通过 PostgreSQL-compatible 接口查询语义成员并加载到 Pandas。

本章提供 `query_with_pandas.py`，通过 PostgreSQL-compatible SQL API 查询第 05 章的语义指标。

## 两个“SQL”不是一回事

连接源 PostgreSQL 时，SQL 面向物理表和列，调用者自己负责 Join 与公式。连接 Cube SQL API 时，SQL 面向语义模型，由 Cube 验证成员、应用权限并生成对源数据库的查询。客户端使用熟悉的 SQL 协议，不等于绕过语义层。

```mermaid
graph LR
    A[Pandas SQL] --> B[Cube SQL API]
    B --> C[语义模型与访问策略]
    C --> D[生成源 SQL]
    D --> E[PostgreSQL]
```

Cube 的 Semantic SQL 是 PostgreSQL-compatible 接口，但不能假设它支持 PostgreSQL 的所有系统表、扩展和任意底层列。教程只使用官方支持且在固定版本验证过的语法。

## Pandas 使用方式

Pandas 通过兼容驱动连接 Cube SQL 端口，执行对公开 View/measure 的查询并生成 DataFrame。连接信息、SSL 和凭据从环境读取，不能硬编码在 Notebook。

## 一致性实验

使用 REST API 和 SQL API 查询同一日期范围、粒度和指标，对列名、类型、排序与数值做规范化后比较。接口格式可以不同，业务结果必须一致，因为它们共享一份语义模型。

## 底层如何处理

Pandas 通过 `psycopg` 连接宿主机 `15432`，这个端口由 Cube Core 提供，不是源 PostgreSQL 的 `55432`。Cube SQL API 解析 `MEASURE(total_amount)`，将它还原为模型中的 `SUM(quantity * price)`，再生成源数据库 SQL。简单查询可以走常规语义查询、缓存和预聚合；需要复杂 SQL 后处理或 pushdown 时，执行路径可能不同。

```text
Pandas → PostgreSQL 协议 :15432 → Semantic SQL 计划 → Cube 模型 → PostgreSQL :5432 → DataFrame
```

## 运行与验证

```bash
cd cube-demos/07-sql-api-and-pandas
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./demo.sh
python3 -m unittest test_demo.py -v
```

示例按 `side` 分组查询 `MEASURE(total_amount)`，预期 BUY 为 `203650`、SELL 为 `5700`。代码中没有 `public.transactions`，证明客户端面对的是语义模型而不是物理表。

## 常见误区

- 把 Cube SQL 端口误当源 PostgreSQL 端口。
- 在 SQL 客户端重新实现指标公式。
- 使用 `SELECT *` 读取大量数据。
- 比较结果时忽略排序、时区和 Decimal 类型差异。

## 验收标准

- Pandas 能读取公开的语义指标。
- SQL API 与 REST API 对同一指标返回一致结果。
- 示例明确区分 Semantic SQL 和底层数据源 SQL。

## 下一步

第 08 章保持查询接口不变，在服务端加入预聚合。
