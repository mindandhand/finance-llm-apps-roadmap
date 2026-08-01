import json
import math
import os
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qlib_demo_common import load_features, print_context, with_datetime_instrument_index


DEFAULT_FACTOR = "$close / Ref($close, 20) - 1"
# Ref 使用负数偏移会读取未来数据，因此这个表达式只能作为 label，不能作为 feature。
DEFAULT_LABEL = "Ref($close, -5) / $close - 1"


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
    # 只有一个分组无法比较高低组；只有一个标的也无法计算横截面相关系数。
    if quantiles < 2:
        raise ValueError("quantiles must be at least 2")
    if min_cross_section < 2:
        raise ValueError("min_cross_section must be at least 2")

    # Qlib 同时计算因子和标签，保证二者使用相同日期与标的索引。
    # 标准索引顺序是 (datetime, instrument)，这样才能按日期做横截面分组。
    data = with_datetime_instrument_index(
        load_features([expression, label], ["factor", "label"])
    )

    # coverage 的分母必须在 dropna 之前记录，否则覆盖率永远会是 100%。
    total_rows = len(data)
    data = data.dropna()

    # 每个日期是一张横截面：行数表示当天同时拥有 factor 和 label 的标的数。
    # IC 是“同一天不同标的之间”的相关性，不是单只标的沿时间方向的相关性。
    cross_section_sizes = data.groupby(level="datetime").size()
    eligible_dates = cross_section_sizes[cross_section_sizes >= min_cross_section].index

    # 样本不足的日期不参与 IC 和分组收益，但仍保留在 coverage 统计中。
    eligible = data[
        data.index.get_level_values("datetime").isin(eligible_dates)
    ]

    if eligible.empty:
        # 显式创建列，保证后续即使没有合格日期也能返回稳定的 JSON schema。
        daily = pd.DataFrame(columns=["ic", "rank_ic"], dtype=float)
    else:
        # 每天独立计算一次横截面相关：
        # Pearson IC 关注因子值与收益值的线性关系；
        # Spearman RankIC 关注因子排序与收益排序是否一致。
        daily = eligible.groupby(level="datetime").apply(
            lambda g: pd.Series(
                {
                    "ic": g["factor"].corr(g["label"]),
                    # Spearman 相关等价于“两个序列先排名，再计算 Pearson 相关”。
                    # 显式写出 rank 既便于学习，也避免 Pandas 隐式要求 SciPy。
                    "rank_ic": g["factor"].rank().corr(g["label"].rank()),
                }
            ),
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
    ic_std = daily["ic"].std()
    rank_ic_std = daily["rank_ic"].std()
    ic_days = int(daily["ic"].notna().sum())
    ic_mean = daily["ic"].mean()
    rank_ic_mean = daily["rank_ic"].mean()

    # 告警不会阻止程序输出，但提醒调用者不要把教学小样本当成统计结论。
    warnings = []
    median_size = float(cross_section_sizes.median()) if len(cross_section_sizes) else 0.0
    if median_size < 30:
        warnings.append(
            "横截面中位数少于 30；这些指标只适合演示计算流程，不适合判断因子有效性。"
        )
    if ic_days < 20:
        warnings.append("有效 IC 日期少于 20，稳定性指标不可靠。")

    return {
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
        "ic_positive_ratio": _rounded((daily["ic"] > 0).mean()) if ic_days else None,
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
        "quantile_return_mean": {str(int(k)): round(float(v), 6) for k, v in quantile_mean.items()},
        "warnings": warnings,
    }


def main() -> None:
    expression = os.getenv("QLIB_FACTOR_EXPR", DEFAULT_FACTOR)
    label = os.getenv("QLIB_LABEL_EXPR", DEFAULT_LABEL)
    print_context("Qlib factor evaluation")
    metrics = evaluate_factor(expression, label)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
