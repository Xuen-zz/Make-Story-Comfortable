import asyncio
from typing import Dict
from app.core.registry import register_node
from app.schemas.payload import EnvelopePayload, PortType


@register_node("rag_retriever")
async def node_rag_retriever(params: dict, inputs: Dict[str, EnvelopePayload]) -> EnvelopePayload:
    """RAG 检索节点：输出带 selected 勾选开关与评分的资产包"""
    query = params.get("query", "")
    await asyncio.sleep(0.01)  # 异步检索
    return EnvelopePayload(
        port_type=PortType.ASSET_BUNDLE,
        meta={"active_scope": params.get("active_scope", ["global"])},
        payload={
            "source_node": "rag_retriever",
            "query": query,
            "lore_chunks": [
                {
                    "chunk_id": "lore_01",
                    "title": "中州拍卖行规则",
                    "content": "中州黑市拍卖行只认灵晶，严禁在场内动用神识探查...",
                    "relevance_score": 0.92,
                    "selected": True,
                }
            ],
        },
    )


@register_node("char_state_loader")
async def node_char_state_loader(params: dict, inputs: Dict[str, EnvelopePayload]) -> EnvelopePayload:
    """角色卡读取节点：支持无头 custom_fields 与 knowledge_boundary"""
    char_id = params.get("character_id", "char_linfeng")
    await asyncio.sleep(0.01)
    return EnvelopePayload(
        port_type=PortType.ASSET_BUNDLE,
        meta={"active_scope": params.get("active_scope", ["global"])},
        payload={
            "entities": [
                {
                    "entity_id": char_id,
                    "schema_type": "character",
                    "name": params.get("name", "林风"),
                    "priority": 100,
                    "selected": True,
                    "custom_fields": {
                        "realm": params.get("realm", "元婴初期"),
                        "injury": params.get("injury", "左臂经脉受损"),
                        "faction": params.get("faction", "青云宗"),
                    },
                    "knowledge_boundary": {
                        "known_secrets": ["secret_012_elder_betrayal"],
                        "unknown_secrets": ["secret_019_sword_spirit_awake"],
                    },
                }
            ]
        },
    )


@register_node("foreshadowing_loader")
async def node_foreshadowing_loader(params: dict, inputs: Dict[str, EnvelopePayload]) -> EnvelopePayload:
    """伏笔账本读取节点"""
    await asyncio.sleep(0.01)
    return EnvelopePayload(
        port_type=PortType.ASSET_BUNDLE,
        payload={
            "foreshadowing": [
                {
                    "hook_id": "hook_045",
                    "summary": "破庙捡到的生锈铜片，遇血会发烫",
                    "status": "unresolved",
                    "planted_chapter": 88,
                    "selected": True,
                }
            ]
        },
    )
