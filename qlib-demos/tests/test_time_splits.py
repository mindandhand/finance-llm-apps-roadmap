import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import qlib_demo_common as common


@pytest.fixture
def calendar(monkeypatch):
    dates = pd.to_datetime([
        '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05',
        '2024-01-08', '2024-01-09', '2024-01-10', '2024-01-11',
        '2024-01-12', '2024-01-15', '2024-01-16', '2024-01-17',
    ])
    for key, value in {
        'START_TIME': '2024-01-02', 'TRAIN_END_TIME': '2024-01-07',
        'VALID_START_TIME': '2024-01-08', 'VALID_END_TIME': '2024-01-11',
        'TEST_START_TIME': '2024-01-12', 'END_TIME': '2024-01-17',
    }.items():
        monkeypatch.setenv('QLIB_' + key, value)
    return dates


def test_labels_stay_inside_segments_using_actual_calendar(calendar):
    assert hasattr(common, 'chronological_segments'), 'Missing horizon-aware time split'
    result = common.chronological_segments(label_horizon=2, calendar=calendar)
    assert result == {
        'train': ('2024-01-02', '2024-01-03'),
        'valid': ('2024-01-08', '2024-01-09'),
        'test': ('2024-01-12', '2024-01-15'),
    }


def test_existing_gap_is_not_purged_twice(calendar, monkeypatch):
    monkeypatch.setenv('QLIB_TRAIN_END_TIME', '2024-01-03')
    assert common.chronological_segments(2, calendar)['train'][1] == '2024-01-03'


def test_rejects_overlapping_or_empty_splits(calendar, monkeypatch):
    monkeypatch.setenv('QLIB_TRAIN_END_TIME', '2024-01-08')
    with pytest.raises(ValueError, match='chronological'):
        common.chronological_segments(2, calendar)
    monkeypatch.setenv('QLIB_TRAIN_END_TIME', '2024-01-07')
    with pytest.raises(ValueError, match='empty'):
        common.chronological_segments(5, calendar)


def test_exchange_holiday_is_not_counted_as_a_trading_day(calendar):
    holiday_calendar = calendar[calendar != pd.Timestamp('2024-01-04')]
    assert common.chronological_segments(2, holiday_calendar)['train'][1] == '2024-01-02'
