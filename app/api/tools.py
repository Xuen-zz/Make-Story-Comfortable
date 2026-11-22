from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.api.ws import ws_manager
from app.dependencies import get_model_router, get_project_bundle
from app.llm.router import ModelRouter
from app.services.inpainting import InpaintRequest, run_inpainting
from app.services.linter import NovelLinter, LintReport
from app.storage.project_bundle import ProjectBundle

tools_router = APIRouter(prefix="/api/tools", tags=["tools"])


class LintRequest(BaseModel):
    current_chapter: int = Field(..., ge=1)
    foreshadowing_list: List[Dict[str, Any]] = Field(default_factory=list)
    recent_summaries: List[Dict[str, Any]] = Field(default_factory=list)
    overdue_threshold: int = Field(default=100)


@tools_router.post("/inpaint", response_model=Dict[str, str])
async def api_inpaint(
    req: InpaintRequest,
    router: ModelRouter = Depends(get_model_router),
):
    """
    文字版 Inpainting 局部重写接口：
    配合前端划词，实时通过 WebSocket 推流并在后台完成自然拼合
    """
    async def emit_chunk(chunk: str):
        await ws_manager.send_event(req.client_id, "INPAINT_STREAM", {
            "node_id": req.node_id,
            "chunk": chunk,
        })

    result = await run_inpainting(req, router, emit_chunk=emit_chunk)
    return result


@tools_router.post("/lint", response_model=LintReport)
async def api_lint(
    req: LintRequest,
    bundle: ProjectBundle = Depends(get_project_bundle),
    router: ModelRouter = Depends(get_model_router),
):
    """
    全书长效体检接口：
    1. 零 Token 规则引擎检索超期伏笔
    2. 大模型长文本审计（若配置了有效客户端）
    """
    cfg = bundle.load_config()
    linter = NovelLinter(overdue_threshold=req.overdue_threshold)

    # 尝试使用 deepseek 客户端审计（若存在）
    client = router.clients.get("deepseek_chat")
    report = await linter.run_full_check(
        current_chapter=req.current_chapter,
        foreshadowing_list=req.foreshadowing_list,
        recent_summaries=req.recent_summaries,
        world_iron_rules=cfg.iron_rules,
        client=client,
        model="deepseek-chat",
    )
    return report
