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
        return {"rank_ic_mean": 0.1 if "$close" in expression else -0.3,
                "sample": {"index_sha256": "same"}}

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


def test_batch_controls_fail_before_environment_initialization(monkeypatch, tmp_path, capsys):
    import pytest

    monkeypatch.setattr(batch, "init_qlib", lambda: pytest.fail("preflight must run first"))
    for overrides in (
        {"quantiles": 1},
        {"min_cross_section": 0},
        {"top_k": True},
        {"selection_period": {}, "test_period": {"start": "2020-10-01", "end": "2020-12-31"}},
        {"selection_period": {"start": "2020-01-01", "end": "2020-06-30"}},
        {"selection_period": {"start": "2020-01-01", "end": "2020-10-01"},
         "test_period": {"start": "2020-10-01", "end": "2020-12-31"}},
    ):
        value = {**config(), **overrides}
        path = tmp_path / "invalid.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        assert batch.main(["--input", str(path)]) == 2
        assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_batch_config"


def test_different_or_unknown_samples_cannot_be_ranked(monkeypatch):
    monkeypatch.setattr(batch, "evaluate_request", lambda expression, *args, **kwargs: {
        "rank_ic_mean": 0.3, "sample": {"index_sha256": expression},
    })
    payload = batch.evaluate_batch(config())
    assert payload["ranked_by_abs_rank_ic"] == []
    assert payload["comparison"]["comparable"] is False
    assert payload["comparison"]["reason"] == "different_or_unknown_rank_ic_samples"


def test_final_test_only_evaluates_selected_candidates_and_never_changes_ranking(monkeypatch):
    calls = []

    def evaluate(expression, *args, **kwargs):
        calls.append((expression, kwargs))
        score = 0.9 if expression == "$volume" else 0.2
        if kwargs.get("start_time") == "2020-10-01":
            score = -0.99
        return {"rank_ic_mean": score, "sample": {"index_sha256": "same"}}

    monkeypatch.setattr(batch, "evaluate_request", evaluate)
    value = config()
    value.update({
        "selection_period": {"start": "2020-01-01", "end": "2020-06-30"},
        "test_period": {"start": "2020-10-01", "end": "2020-12-31"},
        "top_k": 1,
    })
    payload = batch.evaluate_batch(value)
    assert [item["name"] for item in payload["selected_candidates"]] == ["also_good"]
    assert payload["ranked_by_abs_rank_ic"][0]["rank_ic_mean"] == 0.9
    assert payload["final_test"]["results"][0]["metrics"]["rank_ic_mean"] == -0.99
    assert len(calls) == 4
    assert calls[0][1]["label_end_time"] == "2020-06-30"
    assert calls[-1][1]["start_time"] == "2020-10-01"
    assert calls[-1][1]["label_end_time"] == "2020-12-31"


def test_final_test_failure_is_isolated_and_marks_batch_partial(monkeypatch):
    def evaluate(expression, *args, **kwargs):
        if kwargs.get("start_time") == "2020-10-01":
            raise ValueError("unavailable test data")
        return {"rank_ic_mean": 0.3, "sample": {"index_sha256": "same"}}

    monkeypatch.setattr(batch, "evaluate_request", evaluate)
    value = config()
    value.update({
        "selection_period": {"start": "2020-01-01", "end": "2020-06-30"},
        "test_period": {"start": "2020-10-01", "end": "2020-12-31"},
        "top_k": 1,
    })
    payload = batch.evaluate_batch(value)
    assert payload["status"] == "partial"
    assert payload["final_test"]["results"][0]["error"]["code"] == "evaluation_error"
    assert len(payload["ranked_by_abs_rank_ic"]) == 3


def test_context_records_dates_universe_and_content_versions(monkeypatch, tmp_path):
    provider = tmp_path / "provider"
    (provider / "features" / "sh510300").mkdir(parents=True)
    data = provider / "features" / "sh510300" / "close.day.bin"
    data.write_bytes(b"version one")
    monkeypatch.setenv("QLIB_PROVIDER_URI", str(provider))
    monkeypatch.setenv("QLIB_INSTRUMENTS", "sh510300,sh510500")
    monkeypatch.setenv("QLIB_START_TIME", "2020-02-01")
    monkeypatch.setenv("QLIB_END_TIME", "2020-11-30")
    monkeypatch.setattr(batch, "evaluate_request", lambda *args, **kwargs: {
        "rank_ic_mean": 0.2, "sample": {"index_sha256": "same"},
    })
    first = batch.evaluate_batch(config())["evaluation_context"]
    assert first["selection_period"] == {"start": "2020-02-01", "end": "2020-11-30"}
    assert first["instruments"] == ["sh510300", "sh510500"]
    assert first["provider"]["uri"] == str(provider)
    assert len(first["provider"]["content_sha256"]) == 64
    assert len(first["code"]["source_sha256"]) == 64
    data.write_bytes(b"version two")
    second = batch.evaluate_batch(config())["evaluation_context"]
    assert first["provider"]["content_sha256"] != second["provider"]["content_sha256"]


def test_metadata_read_failure_returns_structured_error(monkeypatch, tmp_path, capsys):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config()), encoding="utf-8")
    monkeypatch.setattr(batch, "init_qlib", lambda: None)
    monkeypatch.setattr(batch, "evaluation_context", lambda *args: (_ for _ in ()).throw(OSError("unreadable provider")))
    assert batch.main(["--input", str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "evaluation_error"


def test_requested_test_is_explicitly_skipped_for_incomparable_samples(monkeypatch):
    monkeypatch.setattr(batch, "evaluate_request", lambda expression, *args, **kwargs: {
        "rank_ic_mean": 0.2, "sample": {"index_sha256": expression},
    })
    value = config()
    value.update({
        "selection_period": {"start": "2020-01-01", "end": "2020-06-30"},
        "test_period": {"start": "2020-10-01", "end": "2020-12-31"},
    })
    payload = batch.evaluate_batch(value)
    assert payload["status"] == "partial"
    assert payload["final_test"]["status"] == "skipped"
    assert payload["final_test"]["reason"] == "no_comparable_selection"


def test_cli_argument_errors_are_json(capsys):
    assert batch.main([]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_batch_config"


def test_provider_cache_files_do_not_change_dataset_version(monkeypatch, tmp_path):
    provider = tmp_path / "provider"
    (provider / "features" / "sh510300").mkdir(parents=True)
    (provider / "features" / "sh510300" / "close.day.bin").write_bytes(b"data")
    monkeypatch.setenv("QLIB_PROVIDER_URI", str(provider))
    before = batch.evaluation_context(config(), {})["provider"]["content_sha256"]
    (provider / "cache.lock").write_text("cached expression", encoding="utf-8")
    after = batch.evaluation_context(config(), {})["provider"]["content_sha256"]
    assert before == after


def test_selection_shortfall_is_partial(monkeypatch):
    monkeypatch.setattr(batch, "evaluate_request", lambda expression, *args, **kwargs: {
        "rank_ic_mean": 0.2 if expression == "$volume" else None,
        "sample": {"index_sha256": "same"},
    })
    value = config()
    value.update({
        "selection_period": {"start": "2020-01-01", "end": "2020-06-30"},
        "test_period": {"start": "2020-10-01", "end": "2020-12-31"}, "top_k": 2,
    })
    payload = batch.evaluate_batch(value)
    assert payload["status"] == "partial"
    assert payload["final_test"]["reason"] == "insufficient_selected_candidates"
    assert len(payload["selected_candidates"]) == 1


def test_final_test_without_valid_rank_ic_is_not_success(monkeypatch):
    monkeypatch.setattr(batch, "evaluate_request", lambda expression, *args, **kwargs: {
        "rank_ic_mean": None if kwargs.get("start_time") == "2020-10-01" else 0.2,
        "sample": {"index_sha256": "same"},
    })
    value = config()
    value.update({
        "selection_period": {"start": "2020-01-01", "end": "2020-06-30"},
        "test_period": {"start": "2020-10-01", "end": "2020-12-31"},
    })
    payload = batch.evaluate_batch(value)
    assert payload["status"] == "partial"
    assert payload["final_test"]["summary"]["failed"] == 1
    assert payload["final_test"]["results"][0]["error"]["code"] == "insufficient_test_data"


def test_full_request_and_actual_runtime_versions_are_recorded(monkeypatch):
    import platform
    from importlib.metadata import version

    monkeypatch.setattr(batch, "evaluate_request", lambda *args, **kwargs: {
        "rank_ic_mean": 0.2, "sample": {"index_sha256": "same"},
    })
    value = config()
    value["top_k"] = 2
    payload = batch.evaluate_batch(value)
    assert payload["request"] == {
        **value, "evaluation_period": {"start": batch.start_time(), "end": batch.end_time()},
    }
    runtime = payload["evaluation_context"]["runtime"]
    assert runtime["python"] == platform.python_version()
    assert runtime["packages"]["pandas"] == version("pandas")
    assert set(runtime["packages"]) == {"pyqlib", "pandas", "numpy", "scipy"}


def test_runtime_records_missing_dependency_as_null(monkeypatch):
    import qlib_evaluation_metadata as metadata
    from importlib.metadata import PackageNotFoundError

    def missing_version(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "version", missing_version, raising=False)
    context = metadata.evaluation_context(config(), {})
    assert context["runtime"]["packages"] == dict.fromkeys(("pyqlib", "pandas", "numpy", "scipy"))


def test_diagnostic_request_replays_frozen_dates_after_environment_changes(monkeypatch):
    calls = []

    def evaluate(*args, **kwargs):
        calls.append((kwargs["start_time"], kwargs["end_time"]))
        return {"rank_ic_mean": 0.2, "sample": {"index_sha256": "same"}}

    monkeypatch.setattr(batch, "evaluate_request", evaluate)
    monkeypatch.setenv("QLIB_START_TIME", "2020-01-01")
    monkeypatch.setenv("QLIB_END_TIME", "2020-12-31")
    first = batch.evaluate_batch(config())
    assert first["request"]["evaluation_period"] == {"start": "2020-01-01", "end": "2020-12-31"}
    monkeypatch.setenv("QLIB_START_TIME", "2021-01-01")
    monkeypatch.setenv("QLIB_END_TIME", "2021-12-31")
    replay = batch.evaluate_batch(first["request"])
    assert set(calls) == {("2020-01-01", "2020-12-31")}
    assert replay["evaluation_context"]["config_sha256"] == first["evaluation_context"]["config_sha256"]
    assert replay["final_test"]["status"] == "not_requested"


def test_diagnostic_period_cannot_be_combined_with_selection_and_test():
    import pytest

    value = config()
    value.update({
        "evaluation_period": {"start": "2019-01-01", "end": "2019-12-31"},
        "selection_period": {"start": "2020-01-01", "end": "2020-06-30"},
        "test_period": {"start": "2020-10-01", "end": "2020-12-31"},
    })
    with pytest.raises(batch.BatchConfigError, match="evaluation_period"):
        batch.validate_config(value)


def test_explicit_diagnostic_period_rejects_null_empty_and_mixed_fields():
    import pytest

    for overrides in (
        {"evaluation_period": None},
        {"evaluation_period": {}},
        {"evaluation_period": {"start": "2020-01-01", "end": "2020-12-31"}, "selection_period": None},
        {"evaluation_period": {"start": "2020-01-01", "end": "2020-12-31"}, "test_period": None},
    ):
        with pytest.raises(batch.BatchConfigError, match="evaluation_period"):
            batch.validate_config({**config(), **overrides})
