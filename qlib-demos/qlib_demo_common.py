"""Qlib 教程示例共用的环境配置、数据加载和索引整理工具。"""

import os
from pathlib import Path
from typing import Sequence

import pandas as pd


# 未设置对应环境变量时使用的小型演示时间区间。
DEFAULT_START = "2020-01-01"
DEFAULT_END = "2020-12-31"
DEFAULT_TRAIN_END = "2020-06-30"
DEFAULT_TEST_START = "2020-07-01"


def require_provider_uri() -> str:
    """读取并规范化 Qlib 数据目录；未配置时给出可执行的错误提示。"""
    provider_uri = os.getenv("QLIB_PROVIDER_URI")
    if not provider_uri:
        raise RuntimeError(
            "QLIB_PROVIDER_URI is required. Prepare Qlib data first, then run for example:\n"
            "  QLIB_PROVIDER_URI=~/.qlib/qlib_data/cn_data python <demo>.py"
        )
    return str(Path(provider_uri).expanduser())


def import_qlib():
    """导入 Microsoft pyqlib，并排除同名但不兼容的 ``qlib`` 包。"""
    import qlib

    # pyqlib 的顶层模块提供 init；缺少它通常表示安装了错误的同名包。
    if not hasattr(qlib, "init"):
        location = getattr(qlib, "__file__", "<unknown>")
        raise RuntimeError(
            "Imported package 'qlib' is not Microsoft pyqlib. "
            f"Current module: {location}\n"
            "Remove the conflicting package named 'qlib' and install pyqlib."
        )
    return qlib


def init_qlib():
    """按照环境变量指定的数据目录和市场区域初始化 Qlib。"""
    qlib = import_qlib()
    from qlib.constant import REG_CN, REG_US

    # 教程仅区分中美市场；未显式指定时使用中国市场配置。
    region_name = os.getenv("QLIB_REGION", "cn").lower()
    region = REG_US if region_name == "us" else REG_CN
    provider_uri = require_provider_uri()
    qlib.init(provider_uri=provider_uri, region=region)
    return provider_uri


def instrument_pool() -> str:
    """返回 provider 中的标的池名称，默认读取 ``instruments/all.txt``。"""
    return os.getenv("QLIB_INSTRUMENT_POOL", "all")


def benchmark() -> str:
    """返回回测基准代码，默认使用沪深 300 ETF。"""
    return os.getenv("QLIB_BENCHMARK", "sh510300")


def instruments():
    """返回显式配置的标的列表，未配置时退回到市场股票池名称。"""
    configured = os.getenv("QLIB_INSTRUMENTS")
    if configured:
        # QLIB_INSTRUMENTS 使用逗号分隔，同时容忍空格和空项。
        return [item.strip() for item in configured.split(",") if item.strip()]
    return instrument_pool()


def start_time() -> str:
    """返回整个数据加载区间的开始日期。"""
    return os.getenv("QLIB_START_TIME", DEFAULT_START)


def end_time() -> str:
    """返回整个数据加载区间的结束日期。"""
    return os.getenv("QLIB_END_TIME", DEFAULT_END)


def train_end_time() -> str:
    """返回训练集结束日期。"""
    return os.getenv("QLIB_TRAIN_END_TIME", DEFAULT_TRAIN_END)


def test_start_time() -> str:
    """返回测试集开始日期。"""
    return os.getenv("QLIB_TEST_START_TIME", DEFAULT_TEST_START)


def load_features(fields: Sequence[str], names: Sequence[str] | None = None) -> pd.DataFrame:
    """按日频计算 Qlib 表达式，并可将结果列重命名为易读名称。"""
    init_qlib()
    from qlib.data import D

    # D.features 接受 Qlib 表达式字符串，并返回以标的和日期组织的数据。
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
    """将 MultiIndex 统一为 ``datetime, instrument`` 顺序并排序。"""
    if not isinstance(frame.index, pd.MultiIndex):
        return frame
    names = list(frame.index.names)
    if names == ["datetime", "instrument"]:
        return frame.sort_index()
    if "datetime" in names and "instrument" in names:
        return frame.reorder_levels(["datetime", "instrument"]).sort_index()
    return frame.sort_index()


def print_context(title: str) -> None:
    """打印当前示例实际使用的数据目录、标的和日期范围。"""
    print(title)
    print("provider_uri:", require_provider_uri())
    print("instrument pool:", instrument_pool())
    print("instruments:", instruments())
    print("date range:", start_time(), "to", end_time())
