# -*- mode: python ; coding: utf-8 -*-
"""
api/routers/assets.py
核心创作资产路由：
- 常驻铁律与绝对锚点管理
- 结构化角色与世界状态追踪 (world_state.json)
- 设定条目化向量库 (entity_catalog.json) 与废弃管理
- 章后状态差量 (State Delta) 提取与写入
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.app_state import get_web_app
from novel_generator.state_tracker import (
    load_world_state,
    save_world_state,
    get_mandatory_anchors,
    get_characters_snapshot,
    apply_state_delta,
    extract_chapter_delta_with_llm,
)
from novel_generator.vectorstore_utils import (
    load_entity_catalog,
    add_or_update_entity_item,
    deprecate_entity_item,
    query_active_entities,
)

router = APIRouter()


def _resolve_filepath(filepath: Optional[str] = None) -> str:
    app = get_web_app()
    if filepath and filepath.strip():
        return filepath.strip()
    active = app.config.get("active_project", "")
    if active:
        projects = app.projects
        if active in projects and projects[active].get("filepath"):
            return projects[active]["filepath"]
    return "./output"


class WorldStateUpdateReq(BaseModel):
    filepath: Optional[str] = None
    state: Dict[str, Any]


class EntityItemReq(BaseModel):
    filepath: Optional[str] = None
    item: Dict[str, Any]


class EntityDeprecateReq(BaseModel):
    filepath: Optional[str] = None
    entity_id: str
    chapter_num: int = 1


class ExtractDeltaReq(BaseModel):
    filepath: Optional[str] = None
    chapter_num: int = 1
    chapter_text: str
    character_names: Optional[List[str]] = None
    auto_apply: bool = False
    llm_config_name: Optional[str] = None


@router.get("/assets/world_state")
def get_world_state_api(filepath: Optional[str] = Query(None)):
    """获取当前书籍的完整结构化状态（含常驻绝对铁律与出场人物状态卡）。"""
    fp = _resolve_filepath(filepath)
    state = load_world_state(fp)
    return {
        "success": True,
        "filepath": fp,
        "state": state,
    }


@router.post("/assets/world_state")
def update_world_state_api(body: WorldStateUpdateReq):
    """保存或更新当前书籍的结构化状态。"""
    fp = _resolve_filepath(body.filepath)
    save_world_state(fp, body.state)
    return {
        "success": True,
        "filepath": fp,
        "message": "✅ 世界与人物结构化状态已保存",
    }


@router.get("/assets/entities")
def get_entities_api(filepath: Optional[str] = Query(None)):
    """获取当前书籍的设定实体条目清单。"""
    fp = _resolve_filepath(filepath)
    entities = load_entity_catalog(fp)
    return {
        "success": True,
        "filepath": fp,
        "entities": entities,
        "count": len(entities),
    }


@router.post("/assets/entities")
def add_or_update_entity_api(body: EntityItemReq):
    """按设定条目新增或修改一个实体 Chunk，并同步注入向量库。"""
    app = get_web_app()
    fp = _resolve_filepath(body.filepath)
    emb = getattr(app, "embedding_adapter", None)
    saved = add_or_update_entity_item(emb, fp, body.item)
    return {
        "success": True,
        "filepath": fp,
        "entity": saved,
        "message": f"✅ 实体设定「{saved.get('name')}」已入库",
    }


@router.post("/assets/entities/deprecate")
def deprecate_entity_api(body: EntityDeprecateReq):
    """将指定实体设定标记为废弃 (deprecated)，避免新旧冲突吃书。"""
    app = get_web_app()
    fp = _resolve_filepath(body.filepath)
    emb = getattr(app, "embedding_adapter", None)
    ok = deprecate_entity_item(emb, fp, body.entity_id, body.chapter_num)
    if not ok:
        raise HTTPException(status_code=404, detail=f"未找到实体 ID: {body.entity_id}")
    return {
        "success": True,
        "filepath": fp,
        "message": f"✅ 设定条目 {body.entity_id} 已在第 {body.chapter_num} 章被标记为废弃",
    }


@router.post("/assets/extract_delta")
def extract_state_delta_api(body: ExtractDeltaReq):
    """从正文中提取角色与世界状态差量 (Delta)。"""
    app = get_web_app()
    fp = _resolve_filepath(body.filepath)
    adapter = app.get_llm_adapter(body.llm_config_name) if hasattr(app, "get_llm_adapter") else None
    if not adapter:
        # 尝试默认适配器
        adapter = getattr(app, "llm_adapter", None)
    if not adapter:
        raise HTTPException(status_code=400, detail="未配置有效的 LLM 模型适配器")

    delta = extract_chapter_delta_with_llm(
        llm_adapter=adapter,
        filepath=fp,
        chapter_text=body.chapter_text,
        chapter_num=body.chapter_num,
        character_names=body.character_names,
    )

    applied_state = None
    if body.auto_apply and delta:
        applied_state = apply_state_delta(fp, delta, body.chapter_num)

    return {
        "success": True,
        "delta": delta,
        "applied": body.auto_apply,
        "current_state": applied_state,
        "message": "✅ 章节状态演进差量已提取",
    }
