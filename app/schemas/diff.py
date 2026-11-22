from typing import Any, List, Literal
from pydantic import BaseModel, Field, field_validator


class PatchItem(BaseModel):
    patch_id: str = Field(default="", description="变更补丁唯一 ID")
    target_type: Literal["entity", "foreshadowing", "world_state"]
    target_id: str = Field(..., min_length=1, description="实体或伏笔的唯一 ID")
    op: Literal["add", "replace", "remove"]
    path: str = Field(..., description="RFC 6902 路径，必须以 / 开头，例如 /custom_fields/injury")
    old_value: Any = None
    new_value: Any = None
    evidence_quote: str = Field(..., min_length=4, description="必须摘录本章正文原句作为修改依据（防幻觉）")
    approved: bool = True

    @field_validator("path")
    @classmethod
    def path_must_start_with_slash(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError(f"path '{v}' 必须以 '/' 开头（例如 '/custom_fields/realm'）")
        return v


class StateDiffOutput(BaseModel):
    base_snapshot_id: str = Field(default="", description="基准快照 ID")
    target_chapter: int = Field(default=1, description="目标章节序号")
    review_status: str = Field(default="pending", description="审批状态: pending | approved")
    chapter_summary: str = Field(..., min_length=10, max_length=1000, description="本章剧情核心摘要")
    patches: List[PatchItem] = Field(default_factory=list, description="状态变更列表")
