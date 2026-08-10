"""Agent 工作流共用的安全工具和统一结果协议。"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from pathlib import Path


SUPPORTED_SUFFIXES = {".csv", ".md"}


@dataclass(frozen=True)
class FileSample:
    """文件推荐 Agent 可见的受限样本，避免把完整大文件塞入 Prompt。"""

    name: str
    kind: str
    columns: list[str]
    sample: str
    size_bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind,
            "columns": self.columns,
            "sample": self.sample,
            "size_bytes": self.size_bytes,
        }


def tool_success(key: str, value: object) -> dict[str, object]:
    return {"status": "success", key: value}


def tool_error(message: str) -> dict[str, str]:
    return {"status": "error", "message": message}


def sample_file(name: str, content: bytes, max_chars: int = 1200) -> FileSample:
    """从内存内容生成 CSV 表头/样例行或 Markdown 摘要。"""
    safe_name = Path(name).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"不支持的文件类型：{suffix or '无扩展名'}")
    text = content.decode("utf-8-sig", errors="replace")
    columns: list[str] = []
    if suffix == ".csv":
        reader = csv.reader(StringIO(text))
        rows = []
        for index, row in enumerate(reader):
            if index == 0:
                columns = [item.strip() for item in row]
            rows.append(",".join(row))
            if index >= 3:
                break
        preview = "\n".join(rows)
    else:
        preview = text
    return FileSample(safe_name, suffix.removeprefix("."), columns, preview[:max_chars], len(content))
