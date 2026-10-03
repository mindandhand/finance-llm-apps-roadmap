import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "06-factor-evaluation"))

from factor_evaluation import (
    DEFAULT_FACTOR, DEFAULT_LABEL, evaluate_factor, validate_expression,
    InputValidationError, FutureDataLeakageError,
)
from qlib_demo_common import init_qlib, start_time, end_time
from qlib_evaluation_metadata import evaluation_context


SCHEMA_VERSION = "1.0"


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InputValidationError(message)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = JsonArgumentParser(description="Evaluate a Qlib factor expression deterministically.")
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
    return parser.parse_args(argv)


def validate_request(expression: str, label: str, quantiles: int, min_cross_section: int) -> None:
    if not isinstance(expression, str) or not expression.strip():
        raise InputValidationError("expression must not be empty")
    if not isinstance(label, str) or not label.strip():
        raise InputValidationError("label must not be empty")
    if type(quantiles) is not int or quantiles < 2:
        raise InputValidationError("quantiles must be an integer of at least 2")
    if type(min_cross_section) is not int or min_cross_section < 2:
        raise InputValidationError("min_cross_section must be an integer of at least 2")
    validate_expression(expression)
    validate_expression(label, allow_future=True)


def success_payload(metrics: dict) -> dict:
    return {"schema_version": SCHEMA_VERSION, "status": "ok", "metrics": metrics}


def error_payload(code: str, exc: Exception) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "error": {"code": code, "type": type(exc).__name__, "message": str(exc)},
    }


def evaluate_request(
    expression: str,
    label: str,
    quantiles: int = 3,
    min_cross_section: int = 3,
    initialize: bool = True,
    *,
    start_time: str | None = None,
    end_time: str | None = None,
    label_end_time: str | None = None,
) -> dict:
    """校验并评估一个因子；成功返回 metrics，失败抛出原始异常。"""
    validate_request(expression, label, quantiles, min_cross_section)
    if initialize:
        init_qlib()
    date_options = {key: value for key, value in {
        "start_time": start_time, "end_time": end_time, "label_end_time": label_end_time,
    }.items() if value is not None}
    return evaluate_factor(
        expression,
        label,
        quantiles=quantiles,
        min_cross_section=min_cross_section,
        **date_options,
    )


def run(args: argparse.Namespace) -> tuple[dict, int]:
    try:
        validate_request(args.expression, args.label, args.quantiles, args.min_cross_section)
    except InputValidationError as exc:
        return error_payload("invalid_input", exc), 2

    try:
        init_qlib()
    except Exception as exc:
        return error_payload("environment_error", exc), 1

    try:
        metrics = evaluate_request(
            args.expression,
            args.label,
            quantiles=args.quantiles,
            min_cross_section=args.min_cross_section,
            initialize=False,
        )
        request = {
            "expression": args.expression, "label": args.label,
            "quantiles": args.quantiles, "min_cross_section": args.min_cross_section,
            "start_time": start_time(), "end_time": end_time(),
        }
        payload = success_payload(metrics)
        payload["request"] = request
        payload["evaluation_context"] = evaluation_context(
            request, {"start": request["start_time"], "end": request["end_time"]},
        )
        return payload, 0
    except Exception as exc:
        return error_payload("evaluation_error", exc), 1


def serialize_payload(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_args(argv)
    except InputValidationError as exc:
        print(serialize_payload(error_payload("invalid_input", exc)))
        return 2

    payload, exit_code = run(args)
    serialized = serialize_payload(payload)
    if args.output:
        try:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(serialized, encoding="utf-8")
        except OSError as exc:
            serialized = serialize_payload(error_payload("output_error", exc))
            exit_code = 1
    print(serialized)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
