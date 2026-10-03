from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import qlib_demo_common as common


def test_recorder_default_uri_is_absolute_and_independent_of_cwd(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(common, 'import_qlib', lambda: SimpleNamespace(init=lambda **kwargs: captured.update(kwargs)))
    monkeypatch.setenv('QLIB_PROVIDER_URI', str(tmp_path / 'data'))
    monkeypatch.delenv('QLIB_EXP_URI', raising=False)
    monkeypatch.chdir(tmp_path)
    common.init_qlib()
    expected = str(Path(common.__file__).resolve().parent / 'mlruns')
    assert captured.get('exp_manager', {}).get('kwargs', {}).get('uri') == expected


@pytest.mark.parametrize('kind', ['file', 'path', 'remote'])
def test_recorder_uri_can_be_overridden(monkeypatch, tmp_path, kind):
    captured = {}
    monkeypatch.setattr(common, 'import_qlib', lambda: SimpleNamespace(init=lambda **kwargs: captured.update(kwargs)))
    monkeypatch.setenv('QLIB_PROVIDER_URI', str(tmp_path / 'data'))
    directory = tmp_path / 'my mlruns'
    uri = directory.as_uri() if kind == 'file' else str(directory)
    if kind == 'remote':
        uri = 'https://tracking.example.test'
    monkeypatch.setenv('QLIB_EXP_URI', uri)
    common.init_qlib()
    expected = uri if kind == 'remote' else str(directory)
    assert captured.get('exp_manager', {}).get('kwargs', {}).get('uri') == expected


def test_same_registered_configuration_does_not_reinitialize(monkeypatch, tmp_path):
    from qlib.config import C
    from unittest.mock import Mock

    provider = str(tmp_path / 'data')
    uri = str(tmp_path / 'mlruns')
    monkeypatch.setenv('QLIB_PROVIDER_URI', provider)
    monkeypatch.setenv('QLIB_EXP_URI', uri)
    monkeypatch.setenv('QLIB_REGION', 'cn')
    monkeypatch.setitem(C.__dict__['_config'], '_registered', True)
    monkeypatch.setitem(C.__dict__['_config'], 'provider_uri', {C.DEFAULT_FREQ: provider})
    monkeypatch.setitem(C.__dict__['_config'], 'region', 'cn')
    monkeypatch.setitem(C.__dict__['_config'], 'exp_manager', {
        'class': 'MLflowExpManager', 'module_path': 'qlib.workflow.expm',
        'kwargs': {'uri': uri, 'default_exp_name': 'Experiment'},
    })
    initialize = Mock()
    monkeypatch.setattr(common, 'import_qlib', lambda: SimpleNamespace(init=initialize))
    common.init_qlib()
    initialize.assert_not_called()


def test_configuration_changed_outside_helper_is_not_reused(monkeypatch, tmp_path):
    from qlib.config import C
    from unittest.mock import Mock

    provider = str(tmp_path / 'data')
    uri = str(tmp_path / 'mlruns')
    monkeypatch.setenv('QLIB_PROVIDER_URI', provider)
    monkeypatch.setenv('QLIB_EXP_URI', uri)
    monkeypatch.setenv('QLIB_REGION', 'cn')
    monkeypatch.setitem(C.__dict__['_config'], '_registered', True)
    monkeypatch.setitem(C.__dict__['_config'], 'provider_uri', {C.DEFAULT_FREQ: str(tmp_path / 'other-data')})
    monkeypatch.setitem(C.__dict__['_config'], 'region', 'cn')
    monkeypatch.setitem(C.__dict__['_config'], 'exp_manager', {
        'class': 'MLflowExpManager', 'module_path': 'qlib.workflow.expm',
        'kwargs': {'uri': uri, 'default_exp_name': 'Experiment'},
    })
    initialize = Mock()
    monkeypatch.setattr(common, 'import_qlib', lambda: SimpleNamespace(init=initialize))
    common.init_qlib()
    initialize.assert_called_once()
