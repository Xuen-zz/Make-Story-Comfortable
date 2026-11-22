import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PortType(str, Enum):
    ASSET_BUNDLE = "ASSET_BUNDLE"              # 蓝色：资产与知识库
    PROMPT_CONTEXT = "PROMPT_CONTEXT"          # 紫色：裁剪与装配好的上下文
    CHAPTER_TEXT = "CHAPTER_TEXT"              # 绿色：正文流与润色输出
    STATE_DIFF_PROPOSAL = "STATE_DIFF_PROPOSAL"  # 橙色：RFC 6902 状态变更建议


class EnvelopeMeta(BaseModel):
    chapter_index: int = 1
    active_scope: List[str] = Field(default_factory=lambda: ["global"])
    timestamp: int = Field(default_factory=lambda: int(time.time()))


class EnvelopePayload(BaseModel):
    protocol_version: str = "1.0"
    port_type: str  # PortType or string
    trace_id: str = Field(default_factory=lambda: f"trace_{uuid.uuid4().hex[:12]}")
    meta: Dict[str, Any] = Field(default_factory=dict)
    payload: Dict[str, Any] = Field(default_factory=dict)
