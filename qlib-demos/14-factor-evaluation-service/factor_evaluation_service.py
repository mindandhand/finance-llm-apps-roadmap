import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "06-factor-evaluation"))

from factor_evaluation import DEFAULT_FACTOR, DEFAULT_LABEL, evaluate_factor
from qlib_demo_common import init_qlib


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a Qlib factor expression deterministically.")
    parser.add_argument("--expression", default=DEFAULT_FACTOR, help="Qlib factor expression.")
    parser.add_argument("--label", default=DEFAULT_LABEL, help="Qlib label expression.")
    parser.add_argument("--quantiles", type=int, default=3, help="Cross-sectional return buckets.")
    parser.add_argument(
        "--min-cross-section",
        type=int,
        default=3,
        help="Minimum instruments required for a daily metric.",
    )
    parser.add_argument("--output", default="", help="Optional JSON output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        init_qlib()
        metrics = evaluate_factor(
            args.expression,
            args.label,
            quantiles=args.quantiles,
            min_cross_section=args.min_cross_section,
        )
        payload = {"schema_version": "1.0", "status": "ok", "metrics": metrics}
        exit_code = 0
    except Exception as exc:
        payload = {
            "schema_version": "1.0",
            "status": "error",
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }
        exit_code = 1

    serialized = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    print(serialized)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
