from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import qlib_demo_common as common
from qlib_evaluation_metadata import evaluation_context


@pytest.mark.parametrize("region", ["uk", "invalid", ""])
def test_unknown_region_fails_before_qlib_initialization(monkeypatch, region):
    monkeypatch.setenv("QLIB_REGION", region)
    monkeypatch.setattr(common, "import_qlib", lambda: pytest.fail("unknown region must fail before import/init"))
    with pytest.raises(ValueError, match="QLIB_REGION"):
        common.init_qlib()
    with pytest.raises(ValueError, match="QLIB_REGION"):
        evaluation_context({}, {})


@pytest.mark.parametrize("configured, expected", [("CN", "cn"), ("US", "us"), ("cn", "cn"), ("us", "us")])
def test_runtime_and_metadata_use_the_same_normalized_region(monkeypatch, configured, expected):
    calls = []
    monkeypatch.setenv("QLIB_REGION", configured)
    monkeypatch.setenv("QLIB_PROVIDER_URI", "/private/tmp/region-test-provider")
    monkeypatch.setattr(common, "import_qlib", lambda: SimpleNamespace(init=lambda **kwargs: calls.append(kwargs)))
    common.init_qlib()
    assert calls[0]["region"] == expected
    assert evaluation_context({}, {})["region"] == expected
