import argparse
import json
from pathlib import Path
import re
import sys
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "06-factor-evaluation"))

from factor_evaluation import DEFAULT_FACTOR, DEFAULT_LABEL, evaluate_factor
from qlib_demo_common import init_qlib


SCHEMA_VERSION = "1.0"


class InputValidationError(ValueError):
    """CLI 输入不满足单因子评估契约。"""


class FutureDataLeakageError(InputValidationError):
    """候选因子包含明显的未来数据引用。"""


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


def _ref_offsets(expression: str) -> list[int]:
    """提取 Ref(..., offset) 的整数 offset，支持第一个参数中包含嵌套函数。"""
    offsets = []
    for match in re.finditer(r"\bRef\s*\(", expression, flags=re.IGNORECASE):
        depth = 1
        comma = None
        index = match.end()
        while index < len(expression) and depth:
            char = expression[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and comma is not None:
                    raw_offset = expression[comma + 1 : index].strip()
                    if re.fullmatch(r"[+-]?\d+", raw_offset):
                        offsets.append(int(raw_offset))
            elif char == "," and depth == 1:
                comma = index
            index += 1
    return offsets


def validate_request(expression: str, label: str, quantiles: int, min_cross_section: int) -> None:
    if not expression.strip():
        raise InputValidationError("expression must not be empty")
    if not label.strip():
        raise InputValidationError("label must not be empty")
    if quantiles < 2:
        raise InputValidationError("quantiles must be at least 2")
    if min_cross_section < 2:
        raise InputValidationError("min_cross_section must be at least 2")
    if any(offset < 0 for offset in _ref_offsets(expression)):
        raise FutureDataLeakageError(
            "factor expression must not use negative Ref offsets because they read future data"
        )


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
) -> dict:
    """校验并评估一个因子；成功返回 metrics，失败抛出原始异常。"""
    validate_request(expression, label, quantiles, min_cross_section)
    if initialize:
        init_qlib()
    return evaluate_factor(
        expression,
        label,
        quantiles=quantiles,
        min_cross_section=min_cross_section,
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
        return success_payload(metrics), 0
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
