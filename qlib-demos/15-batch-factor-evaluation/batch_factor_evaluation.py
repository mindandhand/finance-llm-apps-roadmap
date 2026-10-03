import argparse
from datetime import date
import math
import json
from pathlib import Path
import sys
from typing import Sequence

# 15 只负责编排，不复制 14 的输入校验和因子计算。将两个目录加入路径后，
# 可以直接复用单因子服务契约，同时保持每一节仍可作为独立脚本运行。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "14-factor-evaluation-service"))

from factor_evaluation_service import (
    InputValidationError,
    JsonArgumentParser,
    SCHEMA_VERSION,
    error_payload,
    evaluate_request,
    serialize_payload,
    validate_request,
)
from qlib_demo_common import end_time, init_qlib, start_time
from qlib_evaluation_metadata import evaluation_context


class BatchConfigError(ValueError):
    """批量配置不满足可比较实验的最小契约。"""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = JsonArgumentParser(description="Evaluate multiple Qlib factors sequentially.")
    parser.add_argument("--input", required=True, help="Batch candidate JSON file.")
    parser.add_argument("--output", default="", help="Optional summary JSON output path.")
    return parser.parse_args(argv)


def load_config(path: str) -> dict:
    """读取并校验批次级配置；这类错误发生时不应开始任何因子计算。"""
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchConfigError(f"cannot read batch config: {exc}") from exc

    return validate_config(config)


def validate_config(config: dict) -> dict:
    """直接函数调用和 CLI 共用批级预检，候选表达式错误仍单独隔离。"""
    if not isinstance(config, dict):
        raise BatchConfigError("batch config must be a JSON object")
    if config.get("schema_version") != SCHEMA_VERSION:
        raise BatchConfigError(f"schema_version must be {SCHEMA_VERSION}")
    if not isinstance(config.get("label"), str) or not config["label"].strip():
        raise BatchConfigError("label must be a non-empty string")
    if not isinstance(config.get("candidates"), list) or not config["candidates"]:
        raise BatchConfigError("candidates must be a non-empty array")

    # name 是候选在汇总、失败记录和后续重跑中的稳定身份，因此不能为空或重复。
    # expression 允许暂时为空字符串：它会由 Demo 14 作为候选级错误记录，借此
    # 演示“一个坏候选不终止整个批次”的边界。
    names = []
    for index, candidate in enumerate(config["candidates"]):
        if not isinstance(candidate, dict):
            raise BatchConfigError(f"candidate {index} must be an object")
        name = candidate.get("name")
        expression = candidate.get("expression")
        if not isinstance(name, str) or not name.strip():
            raise BatchConfigError(f"candidate {index} name must be a non-empty string")
        if not isinstance(expression, str):
            raise BatchConfigError(f"candidate {name!r} expression must be a string")
        names.append(name)
    if len(names) != len(set(names)):
        raise BatchConfigError("candidate names must be unique")

    # label 和这些控制参数只能在批次级设置，不能由候选单独覆盖。否则两个
    # RankIC 可能来自不同预测目标或不同有效样本规则，放在同一排名中没有意义。
    quantiles = config.get("quantiles", 3)
    min_cross_section = config.get("min_cross_section", 3)
    if not isinstance(quantiles, int) or isinstance(quantiles, bool):
        raise BatchConfigError("quantiles must be an integer")
    if not isinstance(min_cross_section, int) or isinstance(min_cross_section, bool):
        raise BatchConfigError("min_cross_section must be an integer")
    try:
        validate_request("$close", config["label"], quantiles, min_cross_section)
    except InputValidationError as exc:
        raise BatchConfigError(str(exc)) from exc
    config = dict(config)
    selection = config.get("selection_period")
    test = config.get("test_period")
    if "evaluation_period" in config:
        if "selection_period" in config or "test_period" in config:
            raise BatchConfigError("evaluation_period cannot be combined with selection_period/test_period")
        if config["evaluation_period"] is None:
            raise BatchConfigError("evaluation_period must be a start/end date object")
    if (selection is None) != (test is None):
        raise BatchConfigError("selection_period and test_period must be provided together")
    if selection is None:
        # 将环境日期固化为可重放的诊断请求，同时保持“不请求最终测试”的语义。
        config.pop("selection_period", None)
        config.pop("test_period", None)
        config.setdefault("evaluation_period", {"start": start_time(), "end": end_time()})
    for name, period in (("evaluation_period", config.get("evaluation_period")),
                         ("selection_period", selection), ("test_period", test)):
        if period is None:
            continue
        try:
            if not isinstance(period, dict):
                raise ValueError("expected an object")
            first = date.fromisoformat(period["start"])
            last = date.fromisoformat(period["end"])
            if first.isoformat() != period["start"] or last.isoformat() != period["end"]:
                raise ValueError("expected YYYY-MM-DD")
            if first > last:
                raise ValueError("start is after end")
        except (KeyError, TypeError, ValueError) as exc:
            raise BatchConfigError(f"invalid {name}: use start/end ISO dates in chronological order") from exc
    if selection is not None and selection["end"] >= test["start"]:
        raise BatchConfigError("selection_period must end before test_period starts")
    top_k = config.get("top_k", 1)
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= len(names):
        raise BatchConfigError("top_k must be an integer between 1 and candidate count")
    config["top_k"] = top_k
    config["quantiles"] = quantiles
    config["min_cross_section"] = min_cross_section
    return config


def _evaluate_candidates(candidates: list[dict], config: dict, period: dict) -> list[dict]:
    results = []
    for candidate in candidates:
        result = {"name": candidate["name"], "expression": candidate["expression"]}
        try:
            result["metrics"] = evaluate_request(
                candidate["expression"], config["label"],
                quantiles=config["quantiles"], min_cross_section=config["min_cross_section"],
                initialize=False, start_time=period["start"], end_time=period["end"],
                label_end_time=period["end"],
            )
            result["status"] = "ok"
        except InputValidationError as exc:
            result.update(error_payload("invalid_input", exc))
            result.pop("schema_version")
        except Exception as exc:
            result.update(error_payload("evaluation_error", exc))
            result.pop("schema_version")
        results.append(result)
    return results


def evaluate_batch(config: dict) -> dict:
    """先在选择期排名并冻结名单，再独立评估最终测试期。"""
    config = validate_config(config)
    selection = config.get("selection_period") or config["evaluation_period"]
    context = evaluation_context(config, selection)
    results = _evaluate_candidates(config["candidates"], config, selection)
    succeeded = sum(result["status"] == "ok" for result in results)
    failed = len(results) - succeeded
    rankable = [result for result in results if result["status"] == "ok"
                and isinstance(result["metrics"].get("rank_ic_mean"), (int, float))
                and math.isfinite(result["metrics"]["rank_ic_mean"])]
    # coverage 相等也不保证日期/标的相同；只比较拥有完全相同有效样本的候选。
    samples = [result["metrics"].get("sample", {}).get("index_sha256") for result in rankable]
    comparable = bool(samples) and all(samples) and len(set(samples)) == 1
    ranked = sorted(
        ({"name": result["name"], "rank_ic_mean": result["metrics"]["rank_ic_mean"]}
         for result in rankable),
        key=lambda item: abs(item["rank_ic_mean"]), reverse=True,
    ) if comparable else []
    selected = ranked[:config["top_k"]] if config.get("test_period") else []
    selected_names = {item["name"] for item in selected}
    final_results = _evaluate_candidates(
        [candidate for candidate in config["candidates"] if candidate["name"] in selected_names],
        config, config["test_period"],
    ) if selected else []
    for result in final_results:
        if result["status"] != "ok":
            continue
        score = result["metrics"].get("rank_ic_mean")
        if not isinstance(score, (int, float)) or not math.isfinite(score):
            result.update(error_payload("insufficient_test_data", ValueError("final test has no valid RankIC")))
            result.pop("schema_version")
    test_failed = sum(result["status"] != "ok" for result in final_results)
    test_skipped = bool(config.get("test_period")) and not selected
    selection_shortfall = bool(config.get("test_period")) and len(selected) < config["top_k"]
    if test_skipped:
        test_status, test_reason = "skipped", "no_comparable_selection"
    elif test_failed:
        test_status, test_reason = "partial", "test_candidate_failed"
    elif selection_shortfall:
        test_status, test_reason = "partial", "insufficient_selected_candidates"
    else:
        test_status, test_reason = ("ok", None) if selected else ("not_requested", None)
    warnings = []
    if selection_shortfall:
        warnings.append("满足可比较有效样本条件的候选少于 top_k，最终测试未达到配置目标。")
    if not comparable:
        warnings.append("候选有效 RankIC 样本不同或未知，已禁用排名和最终测试选择。")
    if not config.get("test_period"):
        warnings.append("未配置独立测试期；结果仅供样本内诊断，不构成样本外验证。")
    return {
        "schema_version": SCHEMA_VERSION,
        "request": config,
        "status": "ok" if failed == 0 and test_failed == 0 and not selection_shortfall else "partial",
        "label": config["label"],
        "quantiles": config["quantiles"],
        "min_cross_section": config["min_cross_section"],
        "evaluation_context": context,
        "comparison": {"comparable": comparable,
                       "reason": "identical_rank_ic_samples" if comparable else "different_or_unknown_rank_ic_samples"},
        "warnings": warnings,
        "summary": {"total": len(results), "succeeded": succeeded, "failed": failed},
        "ranked_by_abs_rank_ic": ranked,
        "selected_candidates": selected,
        "final_test": {"period": config.get("test_period"), "results": final_results,
                       "status": test_status, "reason": test_reason,
                       "summary": {"total": len(final_results), "failed": test_failed,
                                   "succeeded": len(final_results) - test_failed}},
        "results": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        # JSON 损坏、schema 不匹配或候选名称重复属于批次级错误。此时无法可靠
        # 标识或比较候选，所以应在访问 Qlib 前以退出码 2 结束。
        config = load_config(args.input)
    except (BatchConfigError, InputValidationError) as exc:
        print(serialize_payload(error_payload("invalid_batch_config", exc)))
        return 2

    try:
        # 在循环前预检 provider，避免环境根本不可用时为每个候选制造重复错误。
        init_qlib()
    except Exception as exc:
        print(serialize_payload(error_payload("environment_error", exc)))
        return 1

    try:
        payload = evaluate_batch(config)
        serialized = serialize_payload(payload)
    except Exception as exc:
        print(serialize_payload(error_payload("evaluation_error", exc)))
        return 1
    if args.output:
        try:
            # 先完成全部评估，再一次性写汇总；stdout 与文件使用完全相同的 JSON。
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(serialized, encoding="utf-8")
        except OSError as exc:
            print(serialize_payload(error_payload("output_error", exc)))
            return 1
    print(serialized)
    # partial 返回 1，方便 Shell、CI 或 Agent 在不解析 JSON 前先发现批次不完整；
    # 详细到哪个候选失败，仍以 results 中的结构化 error 为准。
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
