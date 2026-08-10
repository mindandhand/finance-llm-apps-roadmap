"""根据研究目标和文件内容样本推荐数据文件。"""

from __future__ import annotations

from pathlib import Path

from tools import FileSample, SUPPORTED_SUFFIXES, sample_file


def build_file_catalog(root: str | Path) -> dict[str, FileSample]:
    """只读取指定目录直属的 CSV/Markdown，形成可审阅目录。"""
    directory = Path(root)
    return {
        path.name: sample_file(path.name, path.read_bytes())
        for path in sorted(directory.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    }


def build_catalog_from_payloads(payloads: dict[str, bytes]) -> dict[str, FileSample]:
    return {Path(name).name: sample_file(name, content) for name, content in payloads.items()}


def build_file_suggestion_prompt(goal: str, catalog: dict[str, FileSample]) -> str:
    """文件名和内容样本共同进入 Prompt，保留原版内容分析能力。"""
    samples = [item.as_dict() for item in catalog.values()]
    return f"""你是金融知识图谱数据文件推荐 Agent。
已批准的研究目标：{goal}
候选文件样本：{samples}

请选择回答研究目标所必需的文件。需要时同时覆盖结构化关系和非结构化证据；
不得推荐目录之外的文件。只返回 JSON：
{{"selected_files": ["文件名"], "reasoning": "逐个说明文件与研究目标的关系"}}
"""


def validate_suggestion(value: dict[str, object], catalog: dict[str, FileSample]) -> dict[str, object]:
    allowed = set(catalog)
    selected = [str(item) for item in value.get("selected_files", []) if str(item) in allowed]
    return {"selected_files": selected, "reasoning": str(value.get("reasoning", "")).strip()}
