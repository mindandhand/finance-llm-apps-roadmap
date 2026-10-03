import importlib.util
from pathlib import Path
import sys
import types
from contextlib import nullcontext


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "recorder_under_test", ROOT / "08-recorder-and-experiment/recorder_and_experiment.py"
)
recorder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recorder)


def test_recorder_omits_undefined_metrics_and_preserves_original_artifact(monkeypatch):
    metrics = {
        "coverage": 0.5, "ic_mean": None, "rank_ic_mean": None,
        "icir_daily": None, "rank_icir_daily": 0.0,
    }
    logged = {}
    saved = {}
    recording = types.SimpleNamespace(
        start=lambda **kwargs: nullcontext(),
        log_params=lambda **kwargs: None,
        log_metrics=lambda **kwargs: logged.update(kwargs),
        save_objects=lambda **kwargs: saved.update(kwargs),
    )
    monkeypatch.setitem(sys.modules, "qlib.workflow", types.SimpleNamespace(R=recording))
    monkeypatch.setattr(recorder, "init_qlib", lambda: None)
    monkeypatch.setattr(recorder, "print_context", lambda *args: None)
    monkeypatch.setattr(recorder, "evaluate_factor", lambda *args: metrics)

    recorder.main()

    assert logged == {"coverage": 0.5, "rank_icir_daily": 0.0}
    assert saved["metrics.pkl"] is metrics
    assert saved["metrics.pkl"]["icir_daily"] is None
