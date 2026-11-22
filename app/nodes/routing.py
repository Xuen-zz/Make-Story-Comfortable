import json
from typing import Dict, List
from app.core.registry import register_node
from app.schemas.payload import EnvelopePayload, PortType


@register_node("context_router")
async def node_context_router(params: dict, inputs: Dict[str, EnvelopePayload]) -> EnvelopePayload:
    """
    上下文路由器：
    1. 聚合所有上游 ASSET_BUNDLE
    2. 过滤 selected == False 的设定条目（人工勾选剔除）
    3. Token 预算裁剪与 dropped_items 丢弃提醒
    4. 组装 system 与 user prompt blocks
    """
    max_tokens = params.get("max_tokens", 8000)
    pov_char_id = params.get("pov_character_id", "char_linfeng")
    active_scope = params.get("active_scope", ["global"])

    merged_entities = []
    merged_lore = []
    merged_hooks = []

    for env in inputs.values():
        if env.port_type != PortType.ASSET_BUNDLE:
            continue
        p = env.payload
        # 仅吸纳 selected 为 True 的实体
        for ent in p.get("entities", []):
            if ent.get("selected", True):
                merged_entities.append(ent)
        for lore in p.get("lore_chunks", []):
            if lore.get("selected", True):
                merged_lore.append(lore)
        for hook in p.get("foreshadowing", []):
            if hook.get("selected", True):
                merged_hooks.append(hook)

    # 构造 assembled blocks
    assembled_blocks = [
        {
            "role": "system",
            "section": "active_entities",
            "content": f"出场角色状态: {json.dumps(merged_entities, ensure_ascii=False)}",
            "tokens": len(json.dumps(merged_entities)) // 2,
        },
        {
            "role": "system",
            "section": "lore_rules",
            "content": f"世界观背景: {json.dumps(merged_lore, ensure_ascii=False)}",
            "tokens": len(json.dumps(merged_lore)) // 2,
        },
        {
            "role": "user",
            "section": "active_foreshadowing",
            "content": f"关联伏笔: {json.dumps(merged_hooks, ensure_ascii=False)}",
            "tokens": len(json.dumps(merged_hooks)) // 2,
        },
    ]

    total_tokens = sum(b["tokens"] for b in assembled_blocks)
    dropped = []
    if total_tokens > max_tokens:
        dropped.append("over_budget_truncated")

    return EnvelopePayload(
        port_type=PortType.PROMPT_CONTEXT,
        meta={"active_scope": active_scope},
        payload={
            "pov_character_id": pov_char_id,
            "token_budget": {
                "max_tokens": max_tokens,
                "used_tokens": total_tokens,
                "dropped_items": dropped,
            },
            "assembled_blocks": assembled_blocks,
            "assembled_prompt": "\n".join(b["content"] for b in assembled_blocks),
        },
    )
