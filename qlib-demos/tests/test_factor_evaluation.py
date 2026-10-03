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

    metrics = factor_evaluation.evaluate_factor("$close", "$close")

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
        "$close",
        "$close",
        min_cross_section=3,
    )

    assert metrics["eligible_days"] == 0
    assert metrics["ic_days"] == 0
    assert metrics["ic_mean"] is None
    assert metrics["quantile_return_mean"] == {}


def test_evaluate_factor_rejects_invalid_controls():
    try:
        factor_evaluation.evaluate_factor("$close", "$close", quantiles=1)
    except ValueError as exc:
        assert "quantiles" in str(exc)
    else:
        raise AssertionError("quantiles=1 should fail")


def test_nonfinite_rows_are_excluded_and_output_is_strict_json(monkeypatch):
    import json

    frame = make_cross_section(days=2, instruments=5).astype(float)
    frame.iloc[0, 0] = float("inf")
    frame.iloc[1, 1] = float("-inf")
    frame.iloc[5, 0] = float("nan")
    monkeypatch.setattr(factor_evaluation, "load_features", lambda *a: frame)
    metrics = factor_evaluation.evaluate_factor("$close", "$close")
    assert metrics["rows"] == 7
    assert metrics["coverage"] == 0.7
    json.dumps(metrics, allow_nan=False)


def test_positive_ratio_uses_only_defined_ic_days(monkeypatch):
    frame = make_cross_section(days=2, instruments=5)
    frame.iloc[:5, 0] = 1
    monkeypatch.setattr(factor_evaluation, "load_features", lambda *a: frame)
    metrics = factor_evaluation.evaluate_factor("$close", "$close")
    assert metrics["ic_days"] == 1
    assert metrics["ic_positive_ratio"] == 1.0


def test_empty_and_constant_samples_return_json_safe_metrics(monkeypatch):
    import json

    for frame in (make_cross_section(0, 5), make_cross_section(1, 5).assign(factor=1)):
        monkeypatch.setattr(factor_evaluation, "load_features", lambda *a: frame)
        metrics = factor_evaluation.evaluate_factor("$close", "$close")
        assert metrics["ic_mean"] is None
        assert metrics["ic_positive_ratio"] is None
        json.dumps(metrics, allow_nan=False)


def test_overflowed_group_returns_are_json_safe(monkeypatch):
    import json

    frame = make_cross_section(2, 5).assign(label=1e308)
    monkeypatch.setattr(factor_evaluation, "load_features", lambda *a: frame)
    json.dumps(factor_evaluation.evaluate_factor("$close", "$close"), allow_nan=False)


def test_direct_evaluation_rejects_unsafe_expressions_before_loading(monkeypatch):
    import pytest

    monkeypatch.setattr(factor_evaluation, "load_features", lambda *a: pytest.fail("loaded unsafe input"))
    with pytest.raises(ValueError):
        factor_evaluation.evaluate_factor("Ref($close, -(1))", "$close")


def test_label_boundary_uses_trading_calendar_and_forwards_dates(monkeypatch):
    import types

    calendar = pd.bdate_range("2024-01-01", periods=7)
    frame = make_cross_section(7, 5)
    frame.index = pd.MultiIndex.from_product([calendar, [f"S{i:03d}" for i in range(5)]], names=["datetime", "instrument"])
    calls = []

    def load(fields, names, **kwargs):
        calls.append(kwargs)
        return frame

    monkeypatch.setattr(factor_evaluation, "load_features", load)
    monkeypatch.setitem(sys.modules, "qlib.data", types.SimpleNamespace(D=types.SimpleNamespace(calendar=lambda **kwargs: calendar)))
    metrics = factor_evaluation.evaluate_factor(
        "$close", "Ref($close, -2)", start_time="2024-01-01", end_time="2024-01-09", label_end_time="2024-01-09",
    )
    assert calls == [{"date_start": "2024-01-01", "date_end": "2024-01-09"}]
    assert metrics["rows"] == 25
    assert metrics["sample"]["rows"] == 25


def test_sample_hash_distinguishes_instruments_with_same_row_count(monkeypatch):
    frame = make_cross_section(2, 5)
    monkeypatch.setattr(factor_evaluation, "load_features", lambda *a: frame)
    first = factor_evaluation.evaluate_factor("$close", "$close")
    frame = frame.rename(index={"S000": "DIFFERENT"}, level="instrument")
    second = factor_evaluation.evaluate_factor("$close", "$close")
    assert first["sample"]["rows"] == second["sample"]["rows"]
    assert first["sample"]["index_sha256"] != second["sample"]["index_sha256"]


def test_controls_require_integers_before_loading(monkeypatch):
    import pytest

    monkeypatch.setattr(factor_evaluation, "load_features", lambda *a: pytest.fail("loaded invalid controls"))
    for parameter in ("quantiles", "min_cross_section"):
        for value in (True, False, 2.5, 3.0, "3", None):
            with pytest.raises(ValueError, match=parameter):
                factor_evaluation.evaluate_factor("$close", "$close", **{parameter: value})


def test_rejects_literal_ast_placeholder():
    import pytest

    with pytest.raises(ValueError):
        factor_evaluation.validate_expression("$close + __field_close")


def test_tied_factor_values_warn_about_arbitrary_buckets(monkeypatch):
    frame = make_cross_section(2, 5).assign(factor=1)
    monkeypatch.setattr(factor_evaluation, "load_features", lambda *a: frame)
    metrics = factor_evaluation.evaluate_factor("$close", "$close")
    assert any("并列" in warning for warning in metrics["warnings"])


def test_default_label_boundary_purges_at_configured_end(monkeypatch):
    import types

    calendar = pd.bdate_range("2024-01-01", periods=7)
    frame = make_cross_section(7, 5)
    frame.index = pd.MultiIndex.from_product([calendar, [f"S{i:03d}" for i in range(5)]], names=["datetime", "instrument"])
    calls = []

    def load_calendar(**kwargs):
        calls.append(kwargs)
        return calendar

    monkeypatch.setattr(factor_evaluation, "load_features", lambda *a: frame)
    monkeypatch.setenv("QLIB_END_TIME", "2024-01-09")
    monkeypatch.setitem(sys.modules, "qlib.data", types.SimpleNamespace(D=types.SimpleNamespace(calendar=load_calendar)))
    metrics = factor_evaluation.evaluate_factor("$close", "Ref($close, -2)")
    assert metrics["rows"] == 25
    assert calls == [{"end_time": "2024-01-09", "freq": "day"}]


def test_rank_ic_preserves_factor_order_across_extreme_magnitudes(monkeypatch):
    frame = make_cross_section(1, 3).astype(float)
    frame["factor"] = [1e-300, 2e-300, 1e300]
    frame["label"] = [3., 1., 2.]
    monkeypatch.setattr(factor_evaluation, "load_features", lambda *a: frame)

    metrics = factor_evaluation.evaluate_factor("$close", "$close")

    assert metrics["rank_ic_mean"] == -0.5
    assert metrics["ic_mean"] == 0.0


def test_rank_ic_preserves_label_order_across_extreme_magnitudes(monkeypatch):
    frame = make_cross_section(1, 3).astype(float)
    frame["factor"] = [3., 1., 2.]
    frame["label"] = [1e-300, 2e-300, 1e300]
    monkeypatch.setattr(factor_evaluation, "load_features", lambda *a: frame)

    metrics = factor_evaluation.evaluate_factor("$close", "$close")

    assert metrics["rank_ic_mean"] == -0.5
    assert metrics["ic_mean"] == 0.0


def test_rank_ic_ties_and_sample_hash_use_original_valid_rows(monkeypatch):
    frame = make_cross_section(1, 3).astype(float)
    frame["factor"] = [1., 1., 2.]
    frame["label"] = [1., 2., 3.]
    monkeypatch.setattr(factor_evaluation, "load_features", lambda *a: frame)
    tied = factor_evaluation.evaluate_factor("$close", "$close")
    assert tied["rank_ic_mean"] == 0.866025

    frame["factor"] = [1e-300, 2e-300, 1e300]
    frame["label"] = [3., 1., 2.]
    extreme = factor_evaluation.evaluate_factor("$close", "$close")
    assert tied["sample"]["rows"] == extreme["sample"]["rows"] == 3
    assert tied["sample"]["index_sha256"] == extreme["sample"]["index_sha256"]
