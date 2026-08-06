import argparse
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "14-factor-evaluation-service" / "factor_evaluation_service.py"
SPEC = importlib.util.spec_from_file_location("factor_evaluation_service_under_test", MODULE_PATH)
service = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(service)


def args(**overrides):
    values = {
        "expression": "$close / Ref($close, 20) - 1",
        "label": "Ref($close, -5) / $close - 1",
        "quantiles": 3,
        "min_cross_section": 3,
        "output": "",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_validate_request_rejects_future_factor_data():
    try:
        service.validate_request("Ref(Mean($close, 5), -1)", "$close", 3, 3)
    except service.FutureDataLeakageError as exc:
        assert "future data" in str(exc)
    else:
        raise AssertionError("negative Ref offset in a factor should fail")


def test_run_returns_stable_success_payload(monkeypatch):
    monkeypatch.setattr(service, "init_qlib", lambda: None)
    monkeypatch.setattr(service, "evaluate_factor", lambda *args, **kwargs: {"ic_mean": 0.1})

    payload, exit_code = service.run(args())

    assert exit_code == 0
    assert payload == {
        "schema_version": "1.0",
        "status": "ok",
        "metrics": {"ic_mean": 0.1},
    }


def test_run_classifies_input_environment_and_evaluation_errors(monkeypatch):
    payload, exit_code = service.run(args(expression=" "))
    assert exit_code == 2
    assert payload["error"]["code"] == "invalid_input"

    monkeypatch.setattr(service, "init_qlib", lambda: (_ for _ in ()).throw(RuntimeError("missing")))
    payload, exit_code = service.run(args())
    assert exit_code == 1
    assert payload["error"]["code"] == "environment_error"

    monkeypatch.setattr(service, "init_qlib", lambda: None)
    monkeypatch.setattr(service, "evaluate_factor", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad expression")))
    payload, exit_code = service.run(args())
    assert exit_code == 1
    assert payload["error"]["code"] == "evaluation_error"


def test_main_writes_same_success_json_to_stdout_and_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(service, "init_qlib", lambda: None)
    monkeypatch.setattr(service, "evaluate_factor", lambda *args, **kwargs: {"ic_mean": 0.2})
    output = tmp_path / "metrics.json"

    exit_code = service.main(["--output", str(output)])
    stdout_payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert stdout_payload == json.loads(output.read_text(encoding="utf-8"))


def test_main_returns_json_for_argparse_errors(capsys):
    exit_code = service.main(["--quantiles", "not-an-int"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "invalid_input"
