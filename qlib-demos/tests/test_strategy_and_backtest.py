import importlib.util
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODULE_PATH = ROOT / "09-strategy-and-backtest" / "strategy_and_backtest.py"
SPEC = importlib.util.spec_from_file_location("strategy_backtest_under_test", MODULE_PATH)
strategy_backtest = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(strategy_backtest)


def test_build_daily_report_matches_hand_calculation():
    index = pd.MultiIndex.from_tuples(
        [
            ("2024-01-02", "A"),
            ("2024-01-02", "B"),
            ("2024-01-02", "C"),
            ("2024-01-03", "A"),
            ("2024-01-03", "B"),
            ("2024-01-03", "C"),
        ],
        names=["datetime", "instrument"],
    )
    data = pd.DataFrame(
        {
            "score": [3.0, 2.0, 1.0, 1.0, 2.0, 3.0],
            "label": [0.02, 0.01, -0.01, -0.02, 0.01, 0.03],
        },
        index=index,
    )

    report = strategy_backtest.build_daily_report(data, topk=2, cost_rate=0.001)

    first = report.iloc[0]
    assert first["buys"] == 2
    assert first["sells"] == 0
    assert first["turnover"] == 1.0
    assert round(first["gross_return"], 6) == 0.015
    assert round(first["net_return"], 6) == 0.014
    assert round(first["equity"], 6) == 1.014

    second = report.iloc[1]
    assert second["buys"] == 1
    assert second["sells"] == 1
    assert second["turnover"] == 1.0
    assert round(second["gross_return"], 6) == 0.02
    assert round(second["net_return"], 6) == 0.019
    assert round(second["equity"], 6) == 1.033266


def test_build_daily_report_validates_controls():
    empty = pd.DataFrame(columns=["score", "label"])
    try:
        strategy_backtest.build_daily_report(empty, topk=0, cost_rate=0.001)
    except ValueError as exc:
        assert "topk" in str(exc)
    else:
        raise AssertionError("topk=0 should fail")
