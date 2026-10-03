import ast
import hashlib
import json
import math
import os
import re
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qlib_demo_common import (
    load_features, print_context, with_datetime_instrument_index,
    end_time as configured_end_time,
)


DEFAULT_FACTOR = "$close / Ref($close, 20) - 1"
# Ref 使用负数偏移会读取未来数据，因此这个表达式只能作为 label，不能作为 feature。
DEFAULT_LABEL = "Ref($close, -5) / $close - 1"


class InputValidationError(ValueError):
    """评估请求不满足受限表达式契约。"""


class FutureDataLeakageError(InputValidationError):
    """候选因子包含未来数据引用。"""


def validate_expression(expression: str, *, allow_future: bool = False) -> int:
    """只允许已知的日频算子和数值语法，返回保守的未来交易日窗口。"""
    if not isinstance(expression, str) or not expression.strip():
        raise InputValidationError("expression must not be empty")
    if "__field_" in expression:
        raise InputValidationError("reserved field placeholder in expression")
    fields = set()

    def field(match):
        name = "__field_" + match.group(1)
        fields.add(name)
        return name

    source = re.sub(r"\$([A-Za-z_][A-Za-z_0-9]*)", field, expression)
    try:
        tree = ast.parse(source.strip(), mode="eval")
    except (SyntaxError, RecursionError) as exc:
        raise InputValidationError("invalid expression syntax") from exc
    # 窗口算子最后一个参数必须为整数字面量，不执行 Python 常量表达式。
    rolling = {"Ref", "Mean", "Sum", "Std", "Var", "Max", "Min", "Med", "Rank",
               "Delta", "EMA", "WMA", "Slope", "Rsquare", "Resi", "IdxMax", "IdxMin"}
    arities = {**dict.fromkeys(rolling, 2), "Corr": 3, "Cov": 3,
               "Abs": 1, "Log": 1, "Sign": 1, "Power": 2,
               "Greater": 2, "Less": 2, "If": 3}

    def visit(node):
        if isinstance(node, ast.Name) and node.id in fields:
            return 0
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if not math.isfinite(node.value):
                raise InputValidationError("numeric literals must be finite")
            return 0
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.BitAnd, ast.BitOr)):
            return max(visit(node.left), visit(node.right))
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq)):
            return max(visit(node.left), visit(node.comparators[0]))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            if name not in arities or node.keywords or len(node.args) != arities[name]:
                raise InputValidationError("unsupported operator, arguments or keywords")
            horizon = max(visit(arg) for arg in node.args)
            if name in rolling | {"Corr", "Cov"}:
                offset_node = node.args[-1]
                sign = 1
                if isinstance(offset_node, ast.UnaryOp) and isinstance(offset_node.op, (ast.UAdd, ast.USub)):
                    sign = -1 if isinstance(offset_node.op, ast.USub) else 1
                    offset_node = offset_node.operand
                if not isinstance(offset_node, ast.Constant) or type(offset_node.value) is not int:
                    raise InputValidationError("window/Ref offset must be a signed integer literal")
                offset = sign * offset_node.value
                if offset < 0:
                    if name != "Ref" or not allow_future:
                        raise FutureDataLeakageError("factor/window must not read future data")
                    horizon += -offset
            return horizon
        raise InputValidationError("unsupported expression syntax")

    try:
        return visit(tree.body)
    except (RecursionError, OverflowError) as exc:
        raise InputValidationError("expression is too complex") from exc


def _rounded(value: float) -> float | None:
    """把指标转换为 JSON 安全的数值。

    相关系数可能因为样本不足或序列没有波动而得到 NaN。标准 JSON 不支持
    NaN/Infinity，所以这里统一转换为 None，序列化后会得到 null。
    """
    return round(float(value), 6) if pd.notna(value) and math.isfinite(value) else None


def evaluate_factor(
    expression: str,
    label: str,
    quantiles: int = 3,
    min_cross_section: int = 3,
    *,
    start_time: str | None = None,
    end_time: str | None = None,
    label_end_time: str | None = None,
) -> dict:
    """在每天的横截面上评估一个候选因子。

    参数：
    - expression：候选因子的 Qlib 表达式，只能使用当日及历史数据。
    - label：未来收益标签表达式。
    - quantiles：每天把标的按因子值分成几组。
    - min_cross_section：某天至少有多少只有效标的，才计算这一天的指标。

    返回值不仅包含 IC 等结果，也包含横截面大小和警告。仓库内置的五只 ETF
    适合演示计算过程，但不适合据此判断因子是否真的有效。
    """
    validate_expression(expression)
    label_horizon = validate_expression(label, allow_future=True)

    # 只有一个分组无法比较高低组；只有一个标的也无法计算横截面相关系数。
    if type(quantiles) is not int or quantiles < 2:
        raise InputValidationError("quantiles must be an integer of at least 2")
    if type(min_cross_section) is not int or min_cross_section < 2:
        raise InputValidationError("min_cross_section must be an integer of at least 2")

    # Qlib 同时计算因子和标签，保证二者使用相同日期与标的索引。
    # 标准索引顺序是 (datetime, instrument)，这样才能按日期做横截面分组。
    date_options = {}
    if start_time is not None:
        date_options["date_start"] = start_time
    if end_time is not None:
        date_options["date_end"] = end_time
    data = with_datetime_instrument_index(
        load_features([expression, label], ["factor", "label"], **date_options)
    )
    if label_horizon or label_end_time is not None:
        from qlib.data import D

        label_end_time = label_end_time or end_time or configured_end_time()

        calendar = pd.DatetimeIndex(D.calendar(end_time=label_end_time, freq="day"))
        safe_dates = calendar[:-label_horizon] if label_horizon else calendar
        data = data[data.index.get_level_values("datetime").isin(safe_dates)]

    # coverage 的分母必须在 dropna 之前记录，否则覆盖率永远会是 100%。
    total_rows = len(data)
    data = data.replace([float("inf"), float("-inf")], float("nan")).dropna()

    # 每个日期是一张横截面：行数表示当天同时拥有 factor 和 label 的标的数。
    # IC 是“同一天不同标的之间”的相关性，不是单只标的沿时间方向的相关性。
    cross_section_sizes = data.groupby(level="datetime").size()
    eligible_dates = cross_section_sizes[cross_section_sizes >= min_cross_section].index

    # 样本不足的日期不参与 IC 和分组收益，但仍保留在 coverage 统计中。
    eligible = data[
        data.index.get_level_values("datetime").isin(eligible_dates)
    ]

    def daily_correlation(group: pd.DataFrame) -> pd.Series:
        if group["factor"].nunique() < 2 or group["label"].nunique() < 2:
            return pd.Series({"ic": float("nan"), "rank_ic": float("nan")})
        # 缩放可避免极大但有限的输入在相关系数计算时溢出。
        factor = group["factor"] / group["factor"].abs().max()
        label_values = group["label"] / group["label"].abs().max()
        # 排名使用原值，避免缩放下溢把不同的小数值压成相同的 0。
        return pd.Series({"ic": factor.corr(label_values),
                          "rank_ic": group["factor"].rank().corr(group["label"].rank())})

    if eligible.empty:
        # 显式创建列，保证后续即使没有合格日期也能返回稳定的 JSON schema。
        daily = pd.DataFrame(columns=["ic", "rank_ic"], dtype=float)
    else:
        # 每天独立计算一次横截面相关：
        # Pearson IC 关注因子值与收益值的线性关系；
        # Spearman RankIC 关注因子排序与收益排序是否一致。
        daily = eligible.groupby(level="datetime").apply(
            daily_correlation,
        )

    def quantile_return(group: pd.DataFrame) -> pd.Series:
        """计算某一天各因子分组的平均未来收益。"""
        # 分组数不能多于当天标的数。例如只有 3 只标的时，不能硬分成 5 组。
        bucket_count = min(quantiles, len(group))

        # 先 rank 再 qcut，可以把重复因子值稳定地分配到不同位置。
        # method="first" 只用于打破并列，不代表这些细小顺序具有经济意义。
        bucket = pd.qcut(
            group["factor"].rank(method="first"),
            bucket_count,
            labels=False,
            duplicates="drop",
        )
        return group.groupby(bucket)["label"].mean()

    # 先得到“日期 × 分组”的收益，再跨日期求每个分组的平均收益。
    # 如果因子具有稳定单调性，通常高分组与低分组应呈现有序差异。
    # 不使用 groupby.apply 拼接结果，因为不同 Pandas 版本对 apply 返回形状
    # 的处理有差异。显式保存“日期、分组、收益”也更容易观察中间结果。
    quantile_records = []
    for date, group in eligible.groupby(level="datetime"):
        for bucket, bucket_return in quantile_return(group).items():
            quantile_records.append(
                {
                    "datetime": date,
                    "bucket": int(bucket),
                    "return": float(bucket_return),
                }
            )
    quantile_frame = pd.DataFrame.from_records(quantile_records)
    quantile_mean = (
        quantile_frame.groupby("bucket")["return"].mean().to_dict()
        if not quantile_frame.empty
        else {}
    )

    # daily 中每一行代表一天。这里的标准差衡量每日 IC 的时间稳定性。
    daily = daily.replace([float("inf"), float("-inf")], float("nan"))
    valid_ic = daily["ic"].dropna()
    ic_std = valid_ic.std()
    rank_ic_std = daily["rank_ic"].std()
    ic_days = int(daily["ic"].notna().sum())
    ic_mean = daily["ic"].mean()
    rank_ic_mean = daily["rank_ic"].mean()

    # 告警不会阻止程序输出，但提醒调用者不要把教学小样本当成统计结论。
    warnings = ["IC t 统计量及年化 ICIR 未校正自相关；重叠未来收益标签会产生序列相关，不能据此判断显著性。"]
    if any(group["factor"].duplicated().any() for _, group in eligible.groupby(level="datetime")):
        warnings.append("因子存在并列值；分组收益用标的顺序打破并列，其组间差异不能解释为因子排序信息。")
    median_size = float(cross_section_sizes.median()) if len(cross_section_sizes) else 0.0
    if median_size < 30:
        warnings.append(
            "横截面中位数少于 30；这些指标只适合演示计算流程，不适合判断因子有效性。"
        )
    if ic_days < 20:
        warnings.append("有效 IC 日期少于 20，稳定性指标不可靠。")

    rank_dates = daily.index[daily["rank_ic"].notna()]
    sample_index = eligible.index[eligible.index.get_level_values("datetime").isin(rank_dates)]
    sample_rows = [(pd.Timestamp(date).isoformat(), str(instrument)) for date, instrument in sample_index]
    sample_hash = hashlib.sha256(json.dumps(sample_rows, separators=(",", ":")).encode()).hexdigest()
    return {
        "sample": {"index_sha256": sample_hash, "rows": len(sample_rows)},
        "expression": expression,
        "label": label,
        "rows": int(len(data)),
        "coverage": round(float(len(data) / total_rows), 6) if total_rows else 0.0,
        "cross_section_min": int(cross_section_sizes.min()) if len(cross_section_sizes) else 0,
        "cross_section_median": _rounded(median_size),
        "eligible_days": int(len(eligible_dates)),
        "ic_days": ic_days,
        "ic_mean": _rounded(ic_mean),
        "ic_std": _rounded(ic_std),
        # 正 IC 日期占比用于观察方向是否稳定；它不是统计显著性的替代品。
        "ic_positive_ratio": _rounded((valid_ic > 0).mean()) if ic_days else None,
        # t 统计量 = 均值 / 均值的标准误，仅作为基础诊断，未处理自相关等问题。
        "ic_t_stat": _rounded(ic_mean / (ic_std / math.sqrt(ic_days)))
        if ic_days > 1 and ic_std
        else None,
        "rank_ic_mean": _rounded(rank_ic_mean),
        "rank_ic_std": _rounded(rank_ic_std),
        # daily 版本是不年化的 mean/std；annualized 假设一年约 252 个交易日。
        "icir_daily": _rounded(ic_mean / ic_std) if ic_std else None,
        "icir_annualized": _rounded(ic_mean / ic_std * math.sqrt(252)) if ic_std else None,
        "rank_icir_daily": _rounded(rank_ic_mean / rank_ic_std) if rank_ic_std else None,
        "rank_icir_annualized": _rounded(rank_ic_mean / rank_ic_std * math.sqrt(252))
        if rank_ic_std
        else None,
        "quantile_return_mean": {str(int(k)): _rounded(v) for k, v in quantile_mean.items()},
        "warnings": warnings,
    }


def main() -> None:
    expression = os.getenv("QLIB_FACTOR_EXPR", DEFAULT_FACTOR)
    label = os.getenv("QLIB_LABEL_EXPR", DEFAULT_LABEL)
    print_context("Qlib factor evaluation")
    metrics = evaluate_factor(expression, label)
    print(json.dumps(metrics, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
