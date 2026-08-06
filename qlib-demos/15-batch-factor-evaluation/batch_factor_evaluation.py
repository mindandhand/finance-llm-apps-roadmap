import argparse
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
    SCHEMA_VERSION,
    error_payload,
    evaluate_request,
    serialize_payload,
)
from qlib_demo_common import init_qlib


class BatchConfigError(ValueError):
    """批量配置不满足可比较实验的最小契约。"""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate multiple Qlib factors sequentially.")
    parser.add_argument("--input", required=True, help="Batch candidate JSON file.")
    parser.add_argument("--output", default="", help="Optional summary JSON output path.")
    return parser.parse_args(argv)


def load_config(path: str) -> dict:
    """读取并校验批次级配置；这类错误发生时不应开始任何因子计算。"""
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchConfigError(f"cannot read batch config: {exc}") from exc

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
    config["quantiles"] = quantiles
    config["min_cross_section"] = min_cross_section
    return config


def evaluate_batch(config: dict) -> dict:
    """顺序评估全部候选，隔离单项失败，并生成批次汇总。"""
    results = []
    for candidate in config["candidates"]:
        # 每个结果始终回显 name/expression，使失败记录也能脱离输入文件单独审计。
        result = {"name": candidate["name"], "expression": candidate["expression"]}
        try:
            # main() 已完成 Qlib 环境预检，这里关闭服务层的重复预检。底层仍通过
            # 第 6 节的 evaluate_factor() 读取数据并计算唯一一套指标。
            result["metrics"] = evaluate_request(
                candidate["expression"],
                config["label"],
                quantiles=config["quantiles"],
                min_cross_section=config["min_cross_section"],
                initialize=False,
            )
            result["status"] = "ok"
        except InputValidationError as exc:
            # 输入问题属于这个候选，例如空表达式或负数 Ref；记录后继续下一个。
            result.update(error_payload("invalid_input", exc))
            result.pop("schema_version")
        except Exception as exc:
            # Qlib 表达式解析或指标计算错误同样只污染当前候选，不中断批次。
            result.update(error_payload("evaluation_error", exc))
            result.pop("schema_version")
        results.append(result)

    succeeded = sum(result["status"] == "ok" for result in results)
    failed = len(results) - succeeded
    # 负 RankIC 可能表示方向稳定但需要反向使用，因此诊断列表按绝对值排序，
    # 同时保留原始正负号。这个排名不是自动选因子规则，也不代表投资收益。
    ranked = sorted(
        (
            {
                "name": result["name"],
                "rank_ic_mean": result["metrics"].get("rank_ic_mean"),
            }
            for result in results
            if result["status"] == "ok"
            and result["metrics"].get("rank_ic_mean") is not None
        ),
        key=lambda item: abs(item["rank_ic_mean"]),
        reverse=True,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok" if failed == 0 else "partial",
        "label": config["label"],
        "quantiles": config["quantiles"],
        "min_cross_section": config["min_cross_section"],
        "summary": {"total": len(results), "succeeded": succeeded, "failed": failed},
        "ranked_by_abs_rank_ic": ranked,
        "results": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        # JSON 损坏、schema 不匹配或候选名称重复属于批次级错误。此时无法可靠
        # 标识或比较候选，所以应在访问 Qlib 前以退出码 2 结束。
        config = load_config(args.input)
    except BatchConfigError as exc:
        print(serialize_payload(error_payload("invalid_batch_config", exc)))
        return 2

    try:
        # 在循环前预检 provider，避免环境根本不可用时为每个候选制造重复错误。
        init_qlib()
    except Exception as exc:
        print(serialize_payload(error_payload("environment_error", exc)))
        return 1

    payload = evaluate_batch(config)
    serialized = serialize_payload(payload)
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
