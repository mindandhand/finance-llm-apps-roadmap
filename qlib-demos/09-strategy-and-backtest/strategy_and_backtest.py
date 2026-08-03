import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qlib_demo_common import load_features, print_context, with_datetime_instrument_index


DEFAULT_SCORE = "$close / Ref($close, 20) - 1"
# 在 t 日收盘后生成信号，假设 t+1 日完成建仓，再持有到 t+2 日。
# 因此收益标签使用“t+1 收盘到 t+2 收盘”，避免把信号形成前的收益算进去。
DEFAULT_LABEL = "Ref($close, -2) / Ref($close, -1) - 1"


def build_daily_report(data, topk: int, cost_rate: float):
    """把每日横截面分数转换成一个等权 top-k 组合收益表。

    这是教学回测，只回答四个问题：每天选谁、组合赚多少、换了多少持仓、
    扣除简化成本后还剩多少。它不模拟订单、成交量、涨跌停或现金账户。
    """
    import pandas as pd

    if topk < 1:
        raise ValueError("topk must be at least 1")
    if cost_rate < 0:
        raise ValueError("cost_rate must be non-negative")

    reports = []
    # previous 保存上一交易日持有的标的代码，用于和当天持仓做集合比较。
    # 第一天 previous 为空，所以首次建仓也会产生买入换手和成本。
    previous: set[str] = set()

    # 每次循环只处理一个交易日；group 是当天所有可用标的构成的横截面。
    for date, group in data.groupby(level="datetime", sort=True):
        # score 越高排名越靠前。head(topk) 就是当天希望持有的股票池。
        picked = group.sort_values("score", ascending=False).head(topk)
        current = set(picked.index.get_level_values("instrument"))

        # 集合差得到实际调仓名单：今天新出现的是买入，昨天有而今天没有的是卖出。
        buys = current - previous
        sells = previous - current

        # 这里采用双边换手定义：(买入数量 + 卖出数量) / 目标持仓数。
        # 首次买满 top-k 时 turnover=1；持仓全部替换时 turnover=2。
        turnover = (len(buys) + len(sells)) / topk

        # 假设所有入选标的等权，因此组合毛收益就是它们未来收益标签的算术平均。
        # 这里没有根据 score 大小分配不同权重。
        gross_return = float(picked["label"].mean())

        # cost_rate 表示每一单位换手的成本率。由于 turnover 同时统计买卖，
        # 完全换仓会扣除约 2 * cost_rate。
        cost = turnover * cost_rate
        net_return = gross_return - cost

        reports.append(
            {
                "datetime": date,
                "holdings": len(current),
                "buys": len(buys),
                "sells": len(sells),
                "gross_return": gross_return,
                "turnover": turnover,
                "cost": cost,
                "net_return": net_return,
            }
        )
        previous = current

    if not reports:
        return pd.DataFrame(
            columns=["holdings", "buys", "sells", "gross_return", "turnover", "cost", "net_return", "equity"]
        ).rename_axis("datetime")

    report = pd.DataFrame(reports).set_index("datetime")
    # 净值按复利累乘：第二天是在第一天剩余资金的基础上继续获得收益。
    report["equity"] = (1 + report["net_return"]).cumprod()
    return report


def main() -> None:
    score_expr = os.getenv("QLIB_SCORE_EXPR", DEFAULT_SCORE)
    label_expr = os.getenv("QLIB_LABEL_EXPR", DEFAULT_LABEL)
    # 内置数据只有五只 ETF，默认选两只才能真正体现 score 的排序作用。
    topk = int(os.getenv("QLIB_TOPK", "2"))
    cost_rate = float(os.getenv("QLIB_COST_RATE", "0.001"))

    print_context("Qlib score to simple top-k backtest")
    data = with_datetime_instrument_index(load_features([score_expr, label_expr], ["score", "label"])).dropna()

    report = build_daily_report(data, topk=topk, cost_rate=cost_rate)
    if report.empty:
        raise RuntimeError("No valid score/label rows are available for backtesting")

    max_universe = int(data.groupby(level="datetime").size().max())
    if topk >= max_universe:
        print("warning: topk covers the full available universe; score ranking has little effect")
    print(report.head(20).to_string())
    print("total net return:", round(float(report["equity"].iloc[-1] - 1), 6))
    print("mean turnover:", round(float(report["turnover"].mean()), 6))


if __name__ == "__main__":
    main()
