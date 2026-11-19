# api/routers/workflow.py
# -*- coding: utf-8 -*-
"""ComfyUI 风格节点工作流画布 API 与真 DAG 执行路由"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.app_state import get_web_app
from api.sse_utils import run_with_sse
from novel_generator.workflow_dag import (
    get_node_catalog,
    list_all_workflows,
    save_custom_workflow,
    delete_custom_workflow,
    set_default_workflow,
    execute_workflow_dag,
    get_run_session,
)

router = APIRouter(tags=["workflow"])


class SaveWorkflowRequest(BaseModel):
    id: Optional[str] = None
    name: str
    description: str = ""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class SetDefaultWorkflowRequest(BaseModel):
    workflow_id: str


class ExecuteWorkflowRequest(BaseModel):
    graph: Dict[str, Any]
    filepath: str = "./output"
    chapter_num: int = 1
    llm_config_name: str = ""
    emb_config_name: str = ""
    word_number: int = 2500
    run_id: str = ""
    start_from_node_id: str = ""
    initial_cache: Optional[Dict[str, Dict[str, Any]]] = None
    is_batch_mode: bool = False
    batch_gate_policy: str = "manual"


class GateDecisionRequest(BaseModel):
    action: str = "approve"  # approve | cancel
    selected_branch: Optional[str] = None
    edited_text: Optional[str] = None


@router.get("/workflow/catalog")
def workflow_catalog():
    return get_node_catalog()


@router.get("/workflow/list")
def workflow_list():
    return list_all_workflows()


@router.post("/workflow/save")
def workflow_save(body: SaveWorkflowRequest):
    saved = save_custom_workflow(body.model_dump())
    return {"success": True, "workflow": saved}


@router.delete("/workflow/{wf_id}")
def workflow_delete(wf_id: str):
    ok = delete_custom_workflow(wf_id)
    if not ok:
        raise HTTPException(status_code=404, detail="未找到可删除的自定义工作流（内置预设不可删除）")
    return {"success": True}


@router.post("/workflow/set_default")
def workflow_set_default(body: SetDefaultWorkflowRequest):
    set_default_workflow(body.workflow_id)
    return {"success": True, "default_workflow_id": body.workflow_id}


@router.post("/workflow/execute")
def workflow_execute(body: ExecuteWorkflowRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            execute_workflow_dag,
            app,
            body.graph,
            body.filepath,
            body.chapter_num,
            body.llm_config_name,
            body.emb_config_name,
            body.word_number,
            body.run_id,
            body.start_from_node_id,
            body.initial_cache,
            body.is_batch_mode,
            body.batch_gate_policy,
        ):
            yield chunk

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/workflow/gate/{run_id}")
def workflow_gate_decision(run_id: str, body: GateDecisionRequest):
    session = get_run_session(run_id)
    if not session:
        raise HTTPException(status_code=404, detail="工作流运行会话已结束或不存在")
    if body.action == "cancel":
        session.cancel()
    else:
        session.submit_gate(body.model_dump())
    return {"success": True}


@router.post("/workflow/cancel/{run_id}")
def workflow_cancel(run_id: str):
    session = get_run_session(run_id)
    if session:
        session.cancel()
        return {"success": True}
    return {"success": False}
