import time
from typing import Dict, List
from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    project_id: str
    title: str
    genre: str = "通用"
    iron_rules: List[str] = Field(default_factory=list)  # 全书绝对铁律（常驻 System Prompt）
    # 无头 Schema 模板：适配修仙/科幻/言情等全题材
    entity_schemas: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "character": ["realm", "injury", "faction", "location"],
            "item": ["grade", "owner", "effect"],
        }
    )
    created_at: int = Field(default_factory=lambda: int(time.time()))
