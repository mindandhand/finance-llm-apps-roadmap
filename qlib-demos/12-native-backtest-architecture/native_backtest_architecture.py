"""训练 Alpha158 模型，并用 Qlib 原生组件完成样本外组合回测。

本例刻意把模型训练、信号保存、策略决策和撮合记账放在同一个脚本中，
方便观察一列预测分数如何逐步变成订单、持仓和组合风险指标。
"""

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qlib_demo_common import (
    benchmark,
    end_time,
    init_qlib,
    instrument_pool,
    instruments,
    print_context,
    start_time,
    test_start_time,
    train_end_time,
    valid_end_time,
    valid_start_time,
)


def build_dataset():
    """按时间顺序构造训练、验证和样本外测试数据集。

    Alpha158 同时负责生成特征和标签。``fit_end_time`` 限定 handler 中需要
    拟合的处理器只能看到训练期；DatasetH 的 segments 再决定模型训练、验证
    和预测分别读取哪段数据。
    """
    from qlib.contrib.data.handler import Alpha158
    from qlib.data.dataset import DatasetH

    # 特征处理器只能在训练区间拟合，避免用 valid/test 的统计量处理训练数据。
    handler = Alpha158(
        instruments=instruments(),
        start_time=start_time(),
        end_time=end_time(),
        fit_start_time=start_time(),
        fit_end_time=train_end_time(),
    )

    # 三个 segment 保持严格的时间顺序。回测只消费 test segment 生成的信号。
    return DatasetH(
        handler=handler,
        segments={
            "train": (start_time(), train_end_time()),
            "valid": (valid_start_time(), valid_end_time()),
            "test": (test_start_time(), end_time()),
        },
    )


def build_port_analysis_config(model, dataset) -> dict:
    """描述预测信号如何转为订单、成交、持仓和组合报告。

    这个字典对应 Qlib workflow 中的 ``port_analysis_config``。Qlib 会根据
    ``class`` 和 ``module_path`` 创建组件，并把 ``kwargs`` 传给组件构造函数。
    """
    return {
        # Executor 推进回测时钟，把 Strategy 产生的订单交给 Exchange 撮合，
        # 并在每个交易步结束后通知 Account 更新持仓和组合价值。
        "executor": {
            "class": "SimulatorExecutor",
            "module_path": "qlib.backtest.executor",
            "kwargs": {
                # 本例每天调仓一次，并保留日频组合净值、收益和成本序列。
                "time_per_step": "day",
                "generate_portfolio_metrics": True,
            },
        },
        # Strategy 只负责把 score 排名转成买卖决策，不负责判断能否成交。
        "strategy": {
            "class": "TopkDropoutStrategy",
            "module_path": "qlib.contrib.strategy",
            "kwargs": {
                # (model, dataset) 是 Qlib 支持的信号来源，Strategy 会据此取得
                # test score。SignalRecord 还会把同一批预测单独归档为 pred.pkl。
                "signal": (model, dataset),
                # topk 是目标持仓数；n_drop 是单个调仓日最多替换的持仓数。
                "topk": int(os.getenv("QLIB_TOPK", "50")),
                "n_drop": int(os.getenv("QLIB_N_DROP", "5")),
            },
        },
        # Backtest 定义测试区间、初始资金、比较基准和市场成交假设。
        "backtest": {
            # 与 DatasetH 的 test segment 对齐，避免把训练期表现计入结果。
            "start_time": test_start_time(),
            "end_time": end_time(),
            "account": float(os.getenv("QLIB_ACCOUNT", "100000000")),
            "benchmark": benchmark(),
            "exchange_kwargs": {
                "freq": "day",
                # 涨跌幅达到阈值时，Exchange 会按 Qlib 的限制规则判断可交易性。
                "limit_threshold": float(os.getenv("QLIB_LIMIT_THRESHOLD", "0.095")),
                # deal_price 决定模拟成交价；必须和信号可用时间一起检查，
                # 否则可能引入未来信息。
                "deal_price": os.getenv("QLIB_DEAL_PRICE", "close"),
                # 买入费率、卖出费率和单笔最低费用都在 Exchange 撮合时扣除。
                "open_cost": float(os.getenv("QLIB_OPEN_COST", "0.0005")),
                "close_cost": float(os.getenv("QLIB_CLOSE_COST", "0.0015")),
                "min_cost": float(os.getenv("QLIB_MIN_COST", "5")),
            },
        },
    }


def main() -> None:
    # 阶段 1：连接本地 provider，并打印本次实验实际使用的标的和日期。
    init_qlib()
    print_context("Qlib native portfolio backtest")

    from qlib.contrib.model.gbdt import LGBModel
    from qlib.workflow import R
    from qlib.workflow.record_temp import PortAnaRecord, SignalRecord

    # 阶段 2：准备按时间切分的数据，并声明模型。此时还没有训练或交易。
    dataset = build_dataset()
    model = LGBModel(
        loss="mse",
        learning_rate=0.05,
        num_leaves=32,
        max_depth=6,
        num_threads=4,
    )

    # 回测配置保留 model/dataset 引用，Qlib 会在生成组合分析时读取预测信号。
    port_analysis_config = build_port_analysis_config(model, dataset)
    print(f"benchmark: {port_analysis_config['backtest']['benchmark']}")

    # 阶段 3：Recorder 把参数、预测、持仓和分析结果归档到同一次实验运行。
    with R.start(experiment_name="qlib_demo_native_backtest", recorder_name="alpha158_topk"):
        R.log_params(
            # ``market`` 是 Qlib 原生策略接口规定的参数名，值是标的池名称。
            market=instrument_pool(),
            benchmark=port_analysis_config["backtest"]["benchmark"],
            topk=port_analysis_config["strategy"]["kwargs"]["topk"],
            n_drop=port_analysis_config["strategy"]["kwargs"]["n_drop"],
            deal_price=port_analysis_config["backtest"]["exchange_kwargs"]["deal_price"],
            open_cost=port_analysis_config["backtest"]["exchange_kwargs"]["open_cost"],
            close_cost=port_analysis_config["backtest"]["exchange_kwargs"]["close_cost"],
        )

        # fit 只使用 DatasetH 的 train/valid segment；test 留给样本外预测和回测。
        model.fit(dataset)
        recorder = R.get_recorder()

        # 阶段 4：先生成 test score 和 label，并保存为 pred.pkl / label.pkl。
        SignalRecord(model, dataset, recorder).generate()

        # 阶段 5：PortAnaRecord 检查 pred.pkl 依赖后，依次运行 Strategy、
        # Executor、Exchange 和 Account，保存日频报告、持仓和风险分析。
        PortAnaRecord(recorder, port_analysis_config, "day").generate()

        # artifact 路径相对于当前 Recorder，而不是当前工作目录。
        report = recorder.load_object("portfolio_analysis/report_normal_1day.pkl")
        analysis = recorder.load_object("portfolio_analysis/port_analysis_1day.pkl")

    # report 是逐日序列；analysis 是由逐日超额收益汇总出的风险统计量。
    print("portfolio report tail:")
    print(report.tail(10).to_string())
    print("\nportfolio analysis:")
    print(analysis.to_string())


if __name__ == "__main__":
    main()
