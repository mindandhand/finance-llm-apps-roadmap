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
        R.log_metrics(
            coverage=metrics["coverage"],
            ic_mean=metrics["ic_mean"],
            rank_ic_mean=metrics["rank_ic_mean"],
            icir_daily=metrics["icir_daily"] or 0.0,
            rank_icir_daily=metrics["rank_icir_daily"] or 0.0,
        )
        R.save_objects(**{"metrics.pkl": metrics})

    print("recorded metrics:", metrics)


if __name__ == "__main__":
    main()
