import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "15-batch-factor-evaluation" / "batch_factor_evaluation.py"
SPEC = importlib.util.spec_from_file_location("batch_factor_evaluation_under_test", MODULE_PATH)
batch = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(batch)


def config():
    return {
        "schema_version": "1.0",
        "label": "Ref($close, -5) / $close - 1",
        "quantiles": 3,
        "min_cross_section": 3,
        "candidates": [
            {"name": "good", "expression": "$close / Ref($close, 20) - 1"},
            {"name": "bad", "expression": "Ref($close, -1)"},
            {"name": "also_good", "expression": "$volume"},
        ],
    }


def test_load_config_rejects_duplicate_names(tmp_path):
    value = config()
    value["candidates"][1]["name"] = "good"
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    try:
        batch.load_config(str(path))
    except batch.BatchConfigError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate candidate names should fail")


def test_evaluate_batch_continues_after_candidate_failure(monkeypatch):
    def evaluate(expression, *args, **kwargs):
        if "-1" in expression:
            raise batch.InputValidationError("future data")
        return {"rank_ic_mean": 0.1 if "$close" in expression else -0.3}

    monkeypatch.setattr(batch, "evaluate_request", evaluate)

    payload = batch.evaluate_batch(config())

    assert payload["status"] == "partial"
    assert payload["summary"] == {"total": 3, "succeeded": 2, "failed": 1}
    assert [item["status"] for item in payload["results"]] == ["ok", "error", "ok"]
    assert payload["results"][1]["error"]["code"] == "invalid_input"
    assert [item["name"] for item in payload["ranked_by_abs_rank_ic"]] == [
        "also_good",
        "good",
    ]


def test_main_writes_summary_and_returns_partial_exit_code(monkeypatch, tmp_path, capsys):
    input_path = tmp_path / "candidates.json"
    output_path = tmp_path / "summary.json"
    input_path.write_text(json.dumps(config()), encoding="utf-8")
    monkeypatch.setattr(batch, "init_qlib", lambda: None)
    monkeypatch.setattr(
        batch,
        "evaluate_request",
        lambda expression, *args, **kwargs: (_ for _ in ()).throw(ValueError("bad"))
        if "-1" in expression
        else {"rank_ic_mean": 0.1},
    )

    exit_code = batch.main(["--input", str(input_path), "--output", str(output_path)])
    stdout_payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert stdout_payload == json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout_payload["status"] == "partial"
