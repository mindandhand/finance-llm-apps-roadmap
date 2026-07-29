import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "06-factor-evaluation"))

from factor_evaluation import evaluate_factor
from qlib_demo_common import init_qlib, print_context


CONFIG = {
    "experiment_id": "qlib_factor_eval_001",
    "factor_expression": "$close / Ref($close, 20) - 1",
    "label_expression": "Ref($close, -5) / $close - 1",
}


def main() -> None:
    init_qlib()
    print_context("Qlib config-driven factor workflow")

    metrics = evaluate_factor(CONFIG["factor_expression"], CONFIG["label_expression"])
    out = Path(__file__).resolve().parent / "artifacts" / CONFIG["experiment_id"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(json.dumps(CONFIG, indent=2), encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("metrics:", json.dumps(metrics, indent=2, ensure_ascii=False))
    print("artifacts:", out)


if __name__ == "__main__":
    main()
