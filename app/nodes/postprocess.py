from typing import Dict
from app.core.registry import register_node
from app.schemas.payload import EnvelopePayload, PortType


@register_node("state_diff_extractor")
async def node_state_diff_extractor(
    params: dict,
    inputs: Dict[str, EnvelopePayload],
) -> EnvelopePayload:
    """
    状态差分提取节点：
    对比上游资产旧状态与最新正文，生成 RFC 6902 补丁列表，带 evidence_quote
    """
    chapter_text = ""
    for env in inputs.values():
        if env.port_type == PortType.CHAPTER_TEXT:
            chapter_text = env.payload.get("text", "")

    # 模拟提取出的 Diff 提案
    summary = f"林风潜入拍卖行，暗中观察局势，压制左臂伤势。（根据正文: {chapter_text[:20]}... 提取）"
    patches = [
        {
            "patch_id": "patch_001",
            "target_type": "entity",
            "target_id": "char_linfeng",
            "op": "replace",
            "path": "/custom_fields/injury",
            "old_value": "左臂经脉受损",
            "new_value": "左臂伤势稳定，暂未恶化",
            "evidence_quote": "林风暗运灵力稳住左臂伤势，低调走向后排角落",
            "approved": True,
        }
    ]

    return EnvelopePayload(
        port_type=PortType.STATE_DIFF_PROPOSAL,
        payload={
            "chapter_summary": summary,
            "patches": patches,
        },
    )
