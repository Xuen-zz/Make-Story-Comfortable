from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.dependencies import get_project_bundle
from app.schemas.project import ProjectConfig
from app.storage.project_bundle import ProjectBundle
from app.storage.rollback_manager import NovelStateManager
from app.storage.vector_adapter import VectorStoreAdapter

projects_router = APIRouter(prefix="/api/projects", tags=["projects"])


class RollbackRequest(BaseModel):
    target_chapter: int = Field(..., ge=1, description="回滚至目标章节序号")


class ChapterCommitRequest(BaseModel):
    chapter_index: int
    diff_patches: List[Dict[str, Any]]
    full_state: Optional[Dict[str, Any]] = None
    is_full_snapshot: bool = False


@projects_router.get("/config", response_model=ProjectConfig)
async def get_config(bundle: ProjectBundle = Depends(get_project_bundle)):
    """获取当前小说工程元数据与自定义 Schema"""
    return bundle.load_config()


@projects_router.post("/config", response_model=ProjectConfig)
async def update_config(config: ProjectConfig, bundle: ProjectBundle = Depends(get_project_bundle)):
    """更新工程铁律与 Schema 模板"""
    bundle.save_config(config)
    return config


@projects_router.post("/commit", response_model=Dict[str, Any])
async def commit_chapter(
    req: ChapterCommitRequest,
    bundle: ProjectBundle = Depends(get_project_bundle),
):
    """人工审批通过后，正式 Commit 本章状态变更"""
    state_mgr = NovelStateManager(bundle)
    commit_id = state_mgr.commit_chapter(
        chapter_index=req.chapter_index,
        diff_patches=req.diff_patches,
        full_state=req.full_state,
        is_full_snapshot=req.is_full_snapshot,
    )
    return {"status": "COMMITTED", "commit_id": commit_id, "chapter_index": req.chapter_index}


@projects_router.post("/rollback", response_model=Dict[str, Any])
async def rollback_chapter(
    req: RollbackRequest,
    bundle: ProjectBundle = Depends(get_project_bundle),
):
    """执行结构化库与向量库双库时空倒流回滚"""
    state_mgr = NovelStateManager(bundle)
    result = state_mgr.rollback_to_chapter(req.target_chapter)
    return result


@projects_router.post("/export", response_model=Dict[str, str])
async def export_full_book(
    output_filename: str = "full_novel_export.txt",
    bundle: ProjectBundle = Depends(get_project_bundle),
):
    """一键合并全书所有分卷与章节 Markdown 为完整 TXT"""
    out_path = bundle.root / output_filename
    res = bundle.export_full_txt(str(out_path))
    return {"status": "EXPORTED", "file_path": str(res)}
