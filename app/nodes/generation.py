import asyncio
from typing import Callable, Dict, Optional
from app.core.registry import register_node
from app.schemas.payload import EnvelopePayload, PortType


@register_node("llm_sampler")
async def node_llm_sampler(
    params: dict,
    inputs: Dict[str, EnvelopePayload],
    emit_token: Optional[Callable[[str], asyncio.Future]] = None,
) -> EnvelopePayload:
    """
    大模型生成采样器：
    支持逐字打字机推流回调 emit_token
    """
    mock_text = params.get(
        "mock_text",
        "夜色如墨，中州拍卖行内人声鼎沸。林风暗运灵力稳住左臂伤势，低调走向后排角落...",
    )
    full_text = ""

    for char in mock_text:
        await asyncio.sleep(0.005)
        full_text += char
        if emit_token:
            res = emit_token(char)
            if asyncio.iscoroutine(res):
                await res

    return EnvelopePayload(
        port_type=PortType.CHAPTER_TEXT,
        meta={"chapter_index": params.get("chapter_index", 1)},
        payload={"text": full_text},
    )
