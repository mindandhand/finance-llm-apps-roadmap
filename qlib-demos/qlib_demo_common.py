import os
from pathlib import Path
from typing import Sequence

import pandas as pd


DEFAULT_START = "2020-01-01"
DEFAULT_END = "2020-12-31"
DEFAULT_TRAIN_END = "2020-06-30"
DEFAULT_VALID_START = "2020-07-01"
DEFAULT_VALID_END = "2020-09-30"
DEFAULT_TEST_START = "2020-10-01"


def require_provider_uri() -> str:
    """Return the configured provider path; never hide a missing provider."""
    provider_uri = os.getenv("QLIB_PROVIDER_URI")
    if not provider_uri:
        raise RuntimeError(
            "QLIB_PROVIDER_URI is required. Prepare Qlib data first, then run for example:\n"
            "  QLIB_PROVIDER_URI=~/.qlib/qlib_data/cn_data python <demo>.py"
        )
    return str(Path(provider_uri).expanduser())


def import_qlib():
    """Import Microsoft pyqlib and reject the unrelated package named qlib."""
    import qlib

    if not hasattr(qlib, "init"):
        location = getattr(qlib, "__file__", "<unknown>")
        raise RuntimeError(
            "Imported package 'qlib' is not Microsoft pyqlib. "
            f"Current module: {location}\n"
            "Remove the conflicting package named 'qlib' and install pyqlib."
        )
    return qlib


def init_qlib():
    """Initialize Qlib with the shared provider and region configuration."""
    qlib = import_qlib()
    from qlib.constant import REG_CN, REG_US

    region_name = os.getenv("QLIB_REGION", "cn").lower()
    region = REG_US if region_name == "us" else REG_CN
    provider_uri = require_provider_uri()
    qlib.init(provider_uri=provider_uri, region=region)
    return provider_uri


def market() -> str:
    return os.getenv("QLIB_MARKET", "csi300")


def benchmark() -> str:
    return os.getenv("QLIB_BENCHMARK", "sh510300")


def instruments():
    """Return explicit instruments or a Qlib market selector."""
    configured = os.getenv("QLIB_INSTRUMENTS")
    if configured:
        return [item.strip() for item in configured.split(",") if item.strip()]
    return market()


def start_time() -> str:
    return os.getenv("QLIB_START_TIME", DEFAULT_START)


def end_time() -> str:
    return os.getenv("QLIB_END_TIME", DEFAULT_END)


def train_end_time() -> str:
    return os.getenv("QLIB_TRAIN_END_TIME", DEFAULT_TRAIN_END)


def valid_start_time() -> str:
    return os.getenv("QLIB_VALID_START_TIME", DEFAULT_VALID_START)


def valid_end_time() -> str:
    return os.getenv("QLIB_VALID_END_TIME", DEFAULT_VALID_END)


def test_start_time() -> str:
    return os.getenv("QLIB_TEST_START_TIME", DEFAULT_TEST_START)


def load_features(fields: Sequence[str], names: Sequence[str] | None = None) -> pd.DataFrame:
    """Evaluate Qlib expressions and return a consistently sorted DataFrame."""
    init_qlib()
    from qlib.data import D

    data = D.features(
        instruments=instruments(),
        fields=list(fields),
        start_time=start_time(),
        end_time=end_time(),
        freq="day",
    )
    if names is not None:
        data.columns = list(names)
    return data.sort_index()


def with_datetime_instrument_index(frame: pd.DataFrame) -> pd.DataFrame:
    """Put datetime first so chronological slicing has clear semantics."""
    if not isinstance(frame.index, pd.MultiIndex):
        return frame
    names = list(frame.index.names)
    if names == ["datetime", "instrument"]:
        return frame.sort_index()
    if "datetime" in names and "instrument" in names:
        return frame.reorder_levels(["datetime", "instrument"]).sort_index()
    return frame.sort_index()


def print_context(title: str) -> None:
    print(title)
    print("provider_uri:", require_provider_uri())
    print("market:", market())
    print("instruments:", instruments())
    print("date range:", start_time(), "to", end_time())
