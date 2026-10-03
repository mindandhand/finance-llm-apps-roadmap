import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('native_demo', Path(__file__).resolve().parents[1] / '12-native-backtest-architecture/native_backtest_architecture.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def test_small_universe_defaults(monkeypatch):
    monkeypatch.delenv('QLIB_TOPK', raising=False)
    monkeypatch.delenv('QLIB_N_DROP', raising=False)
    kwargs = native.build_port_analysis_config(None, None)['strategy']['kwargs']
    assert (kwargs['topk'], kwargs['n_drop']) == (2, 1)


@pytest.mark.parametrize('topk,n_drop', [('0', '1'), ('2', '-1'), ('2', '3')])
def test_invalid_strategy_controls(monkeypatch, topk, n_drop):
    monkeypatch.setenv('QLIB_TOPK', topk)
    monkeypatch.setenv('QLIB_N_DROP', n_drop)
    with pytest.raises(ValueError, match='topk|n_drop'):
        native.build_port_analysis_config(None, None)


@pytest.fixture
def signal_dataset(monkeypatch):
    import pandas as pd
    from qlib.data.dataset.handler import DataHandlerLP
    from qlib.data.dataset.loader import StaticDataLoader
    import qlib.contrib.data.handler

    dates = pd.bdate_range('2024-01-02', '2024-01-19')
    index = pd.MultiIndex.from_product([dates, ['A', 'B']], names=['datetime', 'instrument'])
    data = pd.DataFrame(
        {'feature': range(len(index)), 'label': 0.01}, index=index,
    )
    data.columns = pd.MultiIndex.from_tuples([('feature', 'F'), ('label', 'LABEL0')])
    # 最后两个日期故意提供超截止日标签，确保记录器确实隔离而非依赖缺失值。
    data.loc[dates[-2]:, ('label', 'LABEL0')] = 999.0
    handler = DataHandlerLP(data_loader=StaticDataLoader(data))
    monkeypatch.setattr(qlib.contrib.data.handler, 'Alpha158', lambda **kwargs: handler)
    monkeypatch.setattr(native, 'chronological_segments', lambda **kwargs: {
        'train': ('2024-01-02', '2024-01-04'),
        'valid': ('2024-01-09', '2024-01-10'),
        'test': ('2024-01-15', '2024-01-17'),
    })
    monkeypatch.setenv('QLIB_START_TIME', '2024-01-02')
    monkeypatch.setenv('QLIB_TEST_START_TIME', '2024-01-15')
    monkeypatch.setenv('QLIB_END_TIME', '2024-01-19')
    return native.build_dataset()


class FeatureScoreModel:
    def predict(self, dataset):
        return dataset.prepare('test', col_set='feature').iloc[:, 0]


def test_native_strategy_keeps_last_two_prediction_days(signal_dataset):
    import pandas as pd
    from qlib.contrib.strategy import TopkDropoutStrategy
    from qlib.backtest.signal import SignalWCache

    strategy = TopkDropoutStrategy(signal=(FeatureScoreModel(), signal_dataset), topk=2, n_drop=1)
    assert isinstance(strategy.signal, SignalWCache)
    for date in ['2024-01-18', '2024-01-19']:
        score = strategy.signal.get_signal(pd.Timestamp(date), pd.Timestamp(date))
        assert score is not None and len(score) == 2


def test_signal_record_separates_prediction_and_safe_labels(signal_dataset):
    import pandas as pd
    from types import SimpleNamespace

    artifacts = {}
    recorder = SimpleNamespace(
        experiment_id='test', save_objects=lambda artifact_path=None, **objects: artifacts.update(objects),
    )
    native.BacktestSignalRecord(FeatureScoreModel(), signal_dataset, recorder).generate()
    assert artifacts['pred.pkl'].index.get_level_values('datetime').max() == pd.Timestamp('2024-01-19')
    assert artifacts['label.pkl'].index.get_level_values('datetime').max() == pd.Timestamp('2024-01-17')
    assert artifacts['label.pkl'].iloc[:, 0].eq(0.01).all()
    assert signal_dataset.segments['train'][1] == '2024-01-04'
    assert signal_dataset.segments['valid'][1] == '2024-01-10'
