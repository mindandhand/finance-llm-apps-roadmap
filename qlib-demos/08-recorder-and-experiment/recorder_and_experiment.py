import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "06-factor-evaluation"))

from factor_evaluation import DEFAULT_FACTOR, DEFAULT_LABEL, evaluate_factor
from qlib_demo_common import init_qlib, print_context


def main() -> None:
    init_qlib()
    from qlib.workflow import R

    expression = os.getenv("QLIB_FACTOR_EXPR", DEFAULT_FACTOR)
    label = os.getenv("QLIB_LABEL_EXPR", DEFAULT_LABEL)
    print_context("Qlib Recorder / Experiment")

    with R.start(experiment_name="qlib_demo_factor_eval", recorder_name="factor_eval"):
        metrics = evaluate_factor(expression, label)
        R.log_params(
            factor_expression=expression,
            label_expression=label,
        )
        # MLflow 不接受 None；未定义指标保留在原始 artifact 中，不伪记成 0。
        R.log_metrics(**{
            name: metrics[name]
            for name in ("coverage", "ic_mean", "rank_ic_mean", "icir_daily", "rank_icir_daily")
            if metrics[name] is not None
        })
        R.save_objects(**{"metrics.pkl": metrics})

    print("recorded metrics:", metrics)


if __name__ == "__main__":
    main()
