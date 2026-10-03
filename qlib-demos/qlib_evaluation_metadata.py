"""单因子和批量评估共享的可追溯运行信息。"""

from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import subprocess
import uuid

from qlib_demo_common import instrument_pool, instruments, normalized_region


def _files_sha256(root: Path, paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(root)).encode("utf-8") + b"\0")
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def evaluation_context(config: dict, selection: dict) -> dict:
    """记录实际源代码和 provider 内容版本；同路径替换数据也能被识别。"""
    root = Path(__file__).resolve().parent
    sources = [root / name for name in (
        "qlib_demo_common.py", "qlib_evaluation_metadata.py",
        "06-factor-evaluation/factor_evaluation.py",
        "14-factor-evaluation-service/factor_evaluation_service.py",
        "15-batch-factor-evaluation/batch_factor_evaluation.py",
    )]
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    uri = os.getenv("QLIB_PROVIDER_URI")
    provider = Path(uri).expanduser().resolve() if uri else None
    packages = {}
    for name in ("pyqlib", "pandas", "numpy", "scipy"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {
        "runtime": {"python": platform.python_version(), "packages": packages},
        "run_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selection_period": selection,
        "test_period": config.get("test_period"),
        "instruments": instruments(),
        "instrument_pool": instrument_pool(),
        "region": normalized_region(),
        "frequency": "day",
        "provider": {
            "uri": str(provider) if provider else None,
            "fingerprint_scope": "calendars/*.txt,instruments/*.txt,features/**/*.bin",
            "content_sha256": _files_sha256(provider, [p for pattern in ("calendars/*.txt", "instruments/*.txt", "features/**/*.bin")
                                                      for p in provider.glob(pattern) if p.is_file()])
            if provider and provider.is_dir() else None,
        },
        "code": {"git_revision": revision, "source_sha256": _files_sha256(root, sources)},
        "config_sha256": hashlib.sha256(
            json.dumps(config, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
    }
