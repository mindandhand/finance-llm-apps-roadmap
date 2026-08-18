# 06：通过 REST API 查询语义层

## 学习目标

理解 Meta API 与 Query API 的不同职责，用最小 Python 客户端发现公开成员、构造结构化查询、处理结果和错误。

本章提供只依赖 Python 标准库的 `CubeClient`，可以直接读取 Meta API 和 Query API，不需要安装 SDK。

## 本章究竟解决什么问题

前 05 章已经能在 Playground 中查询指标，但真实应用不能要求用户手工打开 Playground。Dashboard、批处理程序或 Agent 需要一种稳定方式告诉 Cube“我要哪个指标”，并取得机器可处理的结果。

06 的目的就是把 Cube 当成一个分析服务使用：Python 不连接 PostgreSQL、不知道 `quantity * price` 公式，只通过 HTTP 查询已经定义好的语义成员。

本章同时包含两部分：

- **Cube 提供的能力**：Meta API 用于发现模型，Query API 用于执行语义查询；
- **客户端处理原理**：Python 把字典编码成 JSON，通过 HTTP 发送，随后区分成功结果、空结果、HTTP 错误和网络错误。

## 先理解本章术语

- API：两个程序之间约定好的调用入口；
- REST API：通过 HTTP 地址和 JSON 数据调用服务；
- JSON：跨语言传递对象和数组的文本格式；
- Meta：描述“可以查询什么”的元数据，不包含交易结果；
- Query：描述“这一次要查询什么”的结构化对象；
- Token：随请求发送的身份凭证，第 09 章再详细处理权限。

## 两类 API

- Meta API 返回可查询的数据模型：Cube/View、measure、dimension、类型和可见性。
- Query API 接受选择成员、过滤、排序、限制和时间维度的结构化请求，返回查询结果。

Meta 不返回业务数据；Query 也不应该被用来猜有哪些成员。前端和 Agent 可以先读取 Meta，再限制用户只能选择真实且公开的成员。

可以把它们理解成餐厅的两个动作：

```text
Meta API  = 先拿菜单，看哪些菜可以点
Query API = 按菜单点菜，取得实际结果
```

最直接的区别是：

| 对比 | Meta API | Query API |
|---|---|---|
| 回答的问题 | 能查什么？ | 查询结果是多少？ |
| 输入 | 通常不需要查询条件 | Measure、Dimension、Filter 等 |
| 输出 | 成员名称、中文标题、类型 | 实际业务数据 |
| 是否查询交易数据 | 否 | 是 |
| 常见用途 | 构建字段选择器、生成允许列表 | 指标卡、报表、图表、Agent 工具调用 |

### 具体例子：先发现，再查询

第一步调用 Meta API：

```http
GET /cubejs-api/v1/meta
```

简化后的返回内容：

```json
{
  "name": "transactions.weighted_average_price",
  "title": "加权平均成交价",
  "type": "number"
}
```

它只说明“加权平均成交价存在，并且是数值指标”，没有计算结果。

第二步调用 Query API：

```json
{
  "measures": ["transactions.weighted_average_price"]
}
```

返回：

```json
{
  "data": [{
    "transactions.weighted_average_price": "7.5305755395683453"
  }]
}
```

这一步 Cube 才会展开第 05 章公式、查询 PostgreSQL 并返回实际数值。

一句话记忆：**Meta API 返回指标说明书，Query API 返回按说明书计算出的答案。**

### 分别什么时候调用

| 场景 | 调用的 API |
|---|---|
| 页面首次加载，需要生成指标和维度选择器 | Meta API |
| Agent 需要确认成员是否存在、当前身份是否可见 | Meta API |
| Cube 模型发布后，需要刷新客户端成员缓存 | Meta API |
| 用户点击查询或修改日期、组合、交易方向 | Query API |
| Dashboard 刷新指标卡或图表 | Query API |
| 定时任务生成报表 | Query API |

典型流程是：

```text
页面启动 → Meta API → 生成可选字段
用户选择字段和条件 → Query API → 显示结果
用户修改条件 → 再次调用 Query API
```

Meta API 通常低频调用并适当缓存；Query API 会随每次业务查询反复调用。如果程序使用完全固定的成员，可以直接调用 Query API；动态 UI 和 Agent 最好先读取 Meta API，用当前身份可见的成员限制选择范围。

## 客户端边界

`CubeClient` 只负责 HTTP、认证头、超时、JSON 编解码和错误映射。它不会包装一套复杂 ORM，也不会在本地重复计算指标。

```python
query = {
    "measures": ["transactions.weighted_average_price"]
}
result = client.load(query)
```

这里返回字符串而不是 Python 浮点数，是为了避免金额和高精度小数在传输时丢失精度。需要计算时应显式转换成 `Decimal`。

## `CubeClient` 每一步做什么

```python
client = CubeClient("http://127.0.0.1:4000", timeout=10)
```

这一步只保存 Cube 地址和超时时间，没有连接数据库。

```python
metadata = client.meta()
```

这一步请求 `/cubejs-api/v1/meta`，读取当前可见的 Cube、Measure 和 Dimension。

```python
result = client.load(query)
```

这一步把 Python 字典序列化成 JSON 并进行 URL 编码，然后请求 `/cubejs-api/v1/load`。客户端不会把指标翻译成 SQL，这仍然是 Cube 的职责。

## 结果处理原则

不要假设所有值都是 Python 数字。分析 API 经常以字符串表达精确数值或时间，需要根据元数据做显式转换。保留原始响应便于排查，同时向调用方提供结构清晰的结果。

## 错误分层

- 网络错误：无法连接、DNS、超时。
- HTTP 错误：认证失败、请求无效、服务端异常。
- Cube 查询错误：成员不存在、模型无法编译、生成 SQL 执行失败。
- 业务空结果：合法查询但没有数据，不应当作异常。

测试分别覆盖这四层，禁止用一个笼统的“查询失败”吞掉原因。

## 安全与可靠性

设置连接和读取超时；Token 不写进日志；客户端查询成员来自允许列表；对分页/limit 设置合理上限；重试只用于安全的临时故障，模型或权限错误不能盲目重试。

## 底层如何处理

`meta()` 请求 `/cubejs-api/v1/meta`，得到当前身份可见的成员目录；`load(query)` 把 Python 字典编码成 JSON Query 后请求 `/cubejs-api/v1/load`。Cube 校验成员并生成 SQL，客户端只接收语义成员名组成的结果。HTTP 4xx/5xx 被转换为带状态码的 `CubeApiError`，网络错误则转换为 `CubeConnectionError`，合法空数组保持为空结果。

```text
Python dict → URL 编码 → Cube REST API → 模型/权限/SQL → JSON → Python dict
```

完整过程是：

1. Python 发送 `transactions.weighted_average_price`；
2. Cube 检查该成员是否存在且当前身份可见；
3. Cube 将它展开成第 05 章定义的计算公式；
4. Cube 生成 PostgreSQL SQL并执行；
5. PostgreSQL 返回数值；
6. Cube 将数据库列映射回语义成员名；
7. Python 解析 JSON，但不重新计算指标。

## 运行与验证

```bash
cd cube-demos/06-rest-api-client
./demo.sh
python3 -m unittest test_demo.py -v
```

脚本先加载第 05 章模型，再用 Meta 发现 `transactions`，最后通过 REST 查询加权平均成交价。单元测试使用内存 transport，不依赖容器也能验证 URL、超时和结果解析。

## 验收标准

- 客户端能读取元数据并查询时间序列。
- 查询参数由结构化对象构造，不拼接底层 SQL。
- 服务端错误能保留状态码和可读原因。

## 下一步

第 07 章使用 SQL API，让熟悉 SQL 和 Pandas 的工具消费相同语义模型。
