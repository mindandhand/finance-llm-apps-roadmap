"""根据研究目标和文件内容样本推荐数据文件。"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field

from tools import FileSample, SUPPORTED_SUFFIXES, sample_file


def build_file_catalog(root: str | Path) -> dict[str, FileSample]:
    """扫描支持的本地文件，并为 Agent 建立有限内容目录。"""
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
    """拒绝模型虚构的文件名，确保建议严格落在可见目录内。"""
    allowed = set(catalog)
    selected = [str(item) for item in value.get("selected_files", []) if str(item) in allowed]
    return {"selected_files": selected, "reasoning": str(value.get("reasoning", "")).strip()}


@dataclass
class FileSuggestionSession:
    """文件 Agent 的工具状态，支持按需采样以及拒绝后的重新推荐。"""

    payloads: dict[str, bytes]
    suggested_files: list[str] = field(default_factory=list)
    approved_files: list[str] = field(default_factory=list)
    feedback: list[str] = field(default_factory=list)
    sampled_files: list[str] = field(default_factory=list)
    approved_by: str | None = None
    phase: str = "discovering"

    def list_available_files(self) -> list[str]:
        return sorted(self.payloads)

    def sample_file(self, file_name: str) -> FileSample:
        # 记录采样轨迹，便于审计 Agent 是否在未查看内容时仅凭文件名猜测。
        if Path(file_name).is_absolute() or Path(file_name).name != file_name:
            raise ValueError("文件必须来自候选目录，且只能使用相对文件名。")
        if file_name not in self.payloads:
            raise ValueError(f"候选目录中不存在文件：{file_name}")
        if file_name not in self.sampled_files:
            self.sampled_files.append(file_name)
        return sample_file(file_name, self.payloads[file_name])

    def set_suggested_files(self, files: list[str]) -> list[str]:
        unknown = set(files) - set(self.payloads)
        if unknown:
            raise ValueError(f"推荐包含目录外文件：{', '.join(sorted(unknown))}")
        self.suggested_files = list(dict.fromkeys(files))
        self.approved_files = []
        self.approved_by = None
        self.phase = "awaiting_file_approval"
        return self.suggested_files

    def reject(self, feedback: str) -> None:
        # 驳回后保留候选目录与采样记录，只清除批准状态并等待重提。
        text = feedback.strip()
        if not text:
            raise ValueError("拒绝文件建议时必须提供反馈。")
        self.feedback.append(text)
        self.phase = "discovering"

    def approve(self, reviewer: str) -> list[str]:
        if not self.suggested_files:
            raise ValueError("请先设置建议文件。")
        name = reviewer.strip()
        if not name:
            raise ValueError("文件审批人不能为空。")
        self.approved_files = list(self.suggested_files)
        self.approved_by = name
        self.phase = "approved"
        return self.approved_files
