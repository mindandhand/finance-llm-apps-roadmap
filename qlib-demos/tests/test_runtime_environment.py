"""启动脚本应允许调用方选择解释器和研究区间。"""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_run_script_preserves_runtime_overrides(tmp_path):
    interpreter = tmp_path / "python with spaces"
    interpreter.write_text('#!/bin/bash\nprintf "%s\\n" "$QLIB_PROVIDER_URI" "$QLIB_REGION" "$QLIB_START_TIME" "$QLIB_END_TIME" "$1"\n')
    interpreter.chmod(0o755)
    environment = {
        **os.environ,
        "QLIB_PYTHON": str(interpreter),
        "QLIB_PROVIDER_URI": str(tmp_path / "provider"),
        "QLIB_REGION": "us",
        "QLIB_START_TIME": "2021-01-04",
        "QLIB_END_TIME": "2021-01-08",
    }
    result = subprocess.run(["bash", str(ROOT / "script/run_01.sh")], env=environment,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[:4] == [environment[key] for key in (
        "QLIB_PROVIDER_URI", "QLIB_REGION", "QLIB_START_TIME", "QLIB_END_TIME")]
    assert result.stdout.splitlines()[4].endswith("environment_and_data.py")


def test_local_venv_is_selected_without_python_command():
    environment = {**os.environ}
    environment.pop("QLIB_PYTHON", None)
    result = subprocess.run(["bash", "-c", 'source "$1"; printf "%s" "$QLIB_PYTHON"',
                             "bash", str(ROOT / "qlib_env.sh")], env=environment,
                            capture_output=True, text=True, check=True)
    assert result.stdout == str(ROOT / ".venv/bin/python")
