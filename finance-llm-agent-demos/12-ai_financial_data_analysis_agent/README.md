# AI 金融数据分析 Agent

这是一个面向 CSV / Excel 的本地金融数据分析 demo。用户上传表格后，可以用自然语言提问；应用会让 DeepSeek 生成只读 DuckDB SQL，在本地执行查询，然后再让 DeepSeek 基于真实查询结果生成中文解释。

这个项目的重点不是让模型“直接分析文件”，而是演示一个更可控的边界：

```text
自然语言问题
  -> DeepSeek 生成只读 SQL
  -> Python 校验 SQL
  -> DuckDB 本地执行
  -> DeepSeek 解释真实查询结果
  -> Streamlit 展示 SQL、表格和结论
```

## 功能

- 上传 CSV、XLSX 或 XLS 文件。
- 自动读取字段名、字段类型和前几行样例数据。
- 使用 DeepSeek 生成 DuckDB 只读 SQL。
- 只允许执行 `SELECT` 查询，阻止写入、删除、建表、管理类 SQL。
- 在本地 DuckDB 中执行 SQL，不把完整原始文件交给模型。
- 展示模型生成的 SQL 和真实查询结果。
- 基于查询结果生成中文解释，包括关键发现、异常点、可能原因和下一步建议。
- 提供 `sample_financial_data.csv` 作为可直接测试的数据文件。

## 适合什么场景

这个 demo 适合学习：

- 如何把自然语言问题转换成可审计 SQL。
- 如何把 LLM 放在“生成查询计划”和“解释结果”的位置，而不是让它直接编结论。
- 如何在 Agent 应用里设置只读数据分析边界。
- 如何用 Streamlit 快速做一个文件上传 + 数据分析原型。

它不适合直接用于生产财务审计、投资决策或自动交易。

## 文件结构

```text
12-ai_financial_data_analysis_agent/
├── app.py                       # Streamlit 应用和核心分析流程
├── README.md                    # 本说明文档
├── requirements.txt             # Python 依赖
└── sample_financial_data.csv    # 可上传测试的样例金融数据
```

仓库根目录还提供统一启动脚本：

```text
finance-llm-agent-demos/scripts/run_12_agent.sh
```

## 运行准备

从仓库根目录进入本 demo：

```bash
cd finance-llm-agent-demos/12-ai_financial_data_analysis_agent
```

建议使用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

如果你已经把依赖安装在别的 Python 环境里，也可以继续使用那个环境。

## DeepSeek 配置

在当前目录、`finance-llm-agent-demos/.env` 或仓库根目录 `.env` 中配置：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_ID=deepseek-chat
```

加载顺序是：

```text
12-ai_financial_data_analysis_agent/.env
  -> finance-llm-agent-demos/.env
  -> 仓库根目录 .env
```

## 启动方式

在当前目录启动：

```bash
python -m streamlit run app.py
```

也可以从仓库根目录运行：

```bash
./finance-llm-agent-demos/scripts/run_12_agent.sh
```

启动脚本会优先使用：

```text
finance-llm-agent-demos/12-ai_financial_data_analysis_agent/.venv/bin/python
```

如果没有 `.venv`，脚本会优先尝试 `python3.11`，再退回 `python3`。

如果依赖装在其他 Python 环境里，可以显式指定：

```bash
PYTHON_BIN=/path/to/python ./finance-llm-agent-demos/scripts/run_12_agent.sh
```

## 使用样例数据

本目录已经提供：

```text
sample_financial_data.csv
```

它包含 24 行模拟金融经营数据，字段包括：

| 字段 | 含义 |
| --- | --- |
| `date` | 交易或业务日期 |
| `month` | 月份 |
| `department` | 部门 |
| `customer` | 客户 |
| `category` | 业务类别 |
| `product` | 产品或服务 |
| `region` | 区域 |
| `revenue` | 收入 |
| `cost` | 成本 |
| `profit` | 利润 |
| `amount` | 金额 |
| `transaction_count` | 交易笔数 |

启动应用后，上传 `sample_financial_data.csv`，可以直接使用默认问题：

```text
按类别汇总金额，并找出占比最高的前 5 项。
```

## 示例问题

你可以尝试这些问题：

- 按月份统计收入、成本和利润。
- 找出金额最大的前 20 笔交易，并解释异常点。
- 按客户汇总销售额，列出贡献最高的前 10 个客户。
- 计算每个部门的费用占比。
- 找出利润率最低的业务类别。
- 按区域统计总收入和平均利润率。
- 对比基金销售和投研服务的收入、成本和利润。
- 找出交易笔数最高但利润较低的记录。

## 核心流程

### 1. 读取表格

`load_table()` 根据文件后缀选择读取方式：

- `.csv` 使用 `pandas.read_csv()`。
- `.xlsx` / `.xls` 使用 `pandas.read_excel()`。

读取成功后，页面展示前 30 行数据，并显示总行数和列数。

### 2. 构造字段上下文

`dataframe_schema()` 会把 DataFrame 字段转成类似下面的结构：

```text
- month: object
- category: object
- amount: int64
- profit: int64
```

`build_sql_prompt()` 会把用户问题、字段结构和前 8 行样例数据一起发给 DeepSeek，让它生成 JSON：

```json
{"sql":"SELECT ...", "reason":"为什么这样查询"}
```

### 3. 校验 SQL

`safe_sql()` 是关键安全边界：

- SQL 必须以 `SELECT` 开头。
- 禁止 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER`、`CREATE`、`COPY`、`ATTACH`、`DETACH`、`PRAGMA`。
- 去掉结尾分号。

这一步是为了避免模型生成写入或管理类 SQL。

### 4. 本地执行

`execute_query()` 使用 DuckDB 在本地执行查询：

```text
DataFrame -> DuckDB table named data -> SELECT query -> result DataFrame
```

模型不能直接执行 SQL，也不能直接访问本地文件；它只生成查询文本。

### 5. 解释结果

`build_explain_prompt()` 只把用户问题、SQL 和查询结果前 30 行发给 DeepSeek。模型解释的是 DuckDB 已经算出来的真实结果，而不是凭记忆猜测。

## 你应该观察什么

运行时重点看三块输出：

- **SQL**：模型生成了什么查询，是否符合你的问题。
- **查询结果**：DuckDB 实际返回的数据表。
- **中文解释**：模型如何解释关键发现、异常点和下一步建议。

如果模型生成的 SQL 不对，可以直接改问题，让字段名、分组维度和指标更明确。

## 常见问题

### `No module named 'duckdb'`

说明当前运行脚本使用的 Python 环境没有安装依赖。推荐在本目录创建 `.venv`：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

如果你已经装在其他环境里，用 `PYTHON_BIN` 指向那个 Python：

```bash
PYTHON_BIN=/path/to/python ./finance-llm-agent-demos/scripts/run_12_agent.sh
```

### `未找到 DEEPSEEK_API_KEY`

确认 `.env` 中有：

```bash
DEEPSEEK_API_KEY=你的DeepSeek API Key
```

并确认 `.env` 放在当前目录、`finance-llm-agent-demos` 目录或仓库根目录之一。

### `只允许执行 SELECT 查询`

说明模型生成的 SQL 不是只读查询。可以把问题改得更明确，例如：

```text
请只生成 SELECT 查询，按 category 汇总 amount，并按金额倒序取前 5 行。
```

### 字段名不存在

如果模型使用了不存在的字段，通常是问题里的字段说法和 CSV 字段名差异太大。可以直接在问题中写明字段名，例如：

```text
使用 revenue、cost、profit 三列，按 month 汇总。
```

## 安全边界

这个 demo 做了几件事来降低风险：

- 不让模型直接执行代码。
- 不让模型直接读取本地文件。
- SQL 执行前先做只读校验。
- DuckDB 只注册当前上传的 DataFrame，表名固定为 `data`。
- 解释阶段只发送查询结果样例，不发送完整原始文件。

仍然需要注意：

- 上传敏感真实数据前要自行脱敏。
- LLM 生成的解释需要人工复核。
- 本项目只是学习和原型验证，不构成投资建议、审计结论或业务决策依据。

## 扩展方向

- 增加 SQL 预览和人工确认后再执行。
- 增加图表生成，例如按月趋势图、部门占比图。
- 使用 Pydantic schema 约束 SQL plan 输出。
- 保存每次分析的 SQL、结果和解释，形成审计记录。
- 支持多表上传和表间 join，但需要更严格的 SQL 权限控制。
