import importlib.util
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODULE_PATH = ROOT / "06-factor-evaluation" / "factor_evaluation.py"
SPEC = importlib.util.spec_from_file_location("factor_evaluation_under_test", MODULE_PATH)
factor_evaluation = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(factor_evaluation)


def make_cross_section(days: int, instruments: int) -> pd.DataFrame:
    """生成因子排序与标签排序完全一致的教学横截面。"""
    index = pd.MultiIndex.from_product(
        [
            pd.date_range("2024-01-01", periods=days, freq="D"),
            [f"S{i:03d}" for i in range(instruments)],
        ],
        names=["datetime", "instrument"],
    )
    factor = list(range(instruments)) * days
    return pd.DataFrame({"factor": factor, "label": factor}, index=index)


def test_evaluate_factor_reports_perfect_daily_ic(monkeypatch):
    frame = make_cross_section(days=30, instruments=5)
    monkeypatch.setattr(
        factor_evaluation,
        "load_features",
        lambda fields, names: frame.copy(),
    )

    metrics = factor_evaluation.evaluate_factor("factor", "label")

    assert metrics["coverage"] == 1.0
    assert metrics["ic_days"] == 30
    assert metrics["ic_mean"] == 1.0
    assert metrics["rank_ic_mean"] == 1.0
    assert metrics["cross_section_median"] == 5.0
    assert metrics["quantile_return_mean"] == {"0": 0.5, "1": 2.0, "2": 3.5}
    assert metrics["warnings"]


def test_evaluate_factor_skips_too_small_cross_sections(monkeypatch):
    frame = make_cross_section(days=5, instruments=2)
    monkeypatch.setattr(
        factor_evaluation,
        "load_features",
        lambda fields, names: frame.copy(),
    )

    metrics = factor_evaluation.evaluate_factor(
        "factor",
        "label",
        min_cross_section=3,
    )

    assert metrics["eligible_days"] == 0
    assert metrics["ic_days"] == 0
    assert metrics["ic_mean"] is None
    assert metrics["quantile_return_mean"] == {}


def test_evaluate_factor_rejects_invalid_controls():
    try:
        factor_evaluation.evaluate_factor("factor", "label", quantiles=1)
    except ValueError as exc:
        assert "quantiles" in str(exc)
    else:
        raise AssertionError("quantiles=1 should fail")
