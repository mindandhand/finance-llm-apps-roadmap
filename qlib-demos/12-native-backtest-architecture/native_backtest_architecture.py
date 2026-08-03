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
    """Build chronological model-selection and out-of-sample segments."""
    from qlib.contrib.data.handler import Alpha158
    from qlib.data.dataset import DatasetH

    handler = Alpha158(
        instruments=instruments(),
        start_time=start_time(),
        end_time=end_time(),
        fit_start_time=start_time(),
        fit_end_time=train_end_time(),
    )
    return DatasetH(
        handler=handler,
        segments={
            "train": (start_time(), train_end_time()),
            "valid": (valid_start_time(), valid_end_time()),
            "test": (test_start_time(), end_time()),
        },
    )


def build_port_analysis_config(model, dataset) -> dict:
    """Describe how signals become orders, fills, holdings, and reports."""
    return {
        "executor": {
            "class": "SimulatorExecutor",
            "module_path": "qlib.backtest.executor",
            "kwargs": {
                "time_per_step": "day",
                "generate_portfolio_metrics": True,
            },
        },
        "strategy": {
            "class": "TopkDropoutStrategy",
            "module_path": "qlib.contrib.strategy",
            "kwargs": {
                "signal": (model, dataset),
                "topk": int(os.getenv("QLIB_TOPK", "50")),
                "n_drop": int(os.getenv("QLIB_N_DROP", "5")),
            },
        },
        "backtest": {
            "start_time": test_start_time(),
            "end_time": end_time(),
            "account": float(os.getenv("QLIB_ACCOUNT", "100000000")),
            "benchmark": benchmark(),
            "exchange_kwargs": {
                "freq": "day",
                "limit_threshold": float(os.getenv("QLIB_LIMIT_THRESHOLD", "0.095")),
                "deal_price": os.getenv("QLIB_DEAL_PRICE", "close"),
                "open_cost": float(os.getenv("QLIB_OPEN_COST", "0.0005")),
                "close_cost": float(os.getenv("QLIB_CLOSE_COST", "0.0015")),
                "min_cost": float(os.getenv("QLIB_MIN_COST", "5")),
            },
        },
    }


def main() -> None:
    init_qlib()
    print_context("Qlib native portfolio backtest")

    from qlib.contrib.model.gbdt import LGBModel
    from qlib.workflow import R
    from qlib.workflow.record_temp import PortAnaRecord, SignalRecord

    dataset = build_dataset()
    model = LGBModel(
        loss="mse",
        learning_rate=0.05,
        num_leaves=32,
        max_depth=6,
        num_threads=4,
    )
    port_analysis_config = build_port_analysis_config(model, dataset)
    print(f"benchmark: {port_analysis_config['backtest']['benchmark']}")

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

        model.fit(dataset)
        recorder = R.get_recorder()

        SignalRecord(model, dataset, recorder).generate()
        PortAnaRecord(recorder, port_analysis_config, "day").generate()

        report = recorder.load_object("portfolio_analysis/report_normal_1day.pkl")
        analysis = recorder.load_object("portfolio_analysis/port_analysis_1day.pkl")

    print("portfolio report tail:")
    print(report.tail(10).to_string())
    print("\nportfolio analysis:")
    print(analysis.to_string())


if __name__ == "__main__":
    main()
