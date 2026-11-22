import asyncio
import uuid
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException
from app.api.ws import ws_manager
from app.core.dag_engine import execute_dag
from app.dependencies import get_project_bundle
from app.schemas.graph import RunState, StartRunRequest, ResumeRunRequest
from app.storage.project_bundle import ProjectBundle

runs_router = APIRouter(prefix="/api/runs", tags=["runs"])

# 活跃协程任务注册表: {run_id: asyncio.Task}
ACTIVE_TASKS: Dict[str, asyncio.Task] = {}


def launch_dag_task(run_state: RunState, client_id: str, bundle: ProjectBundle) -> asyncio.Task:
    """统一后台调度并管理 Task 生命周期"""
    async def _runner():
        await execute_dag(
            run_state=run_state,
            client_id=client_id,
            bundle=bundle,
            ws_emitter=ws_manager.send_event,
        )

    task = asyncio.create_task(_runner())
    ACTIVE_TASKS[run_state.run_id] = task
    task.add_done_callback(lambda _: ACTIVE_TASKS.pop(run_state.run_id, None))
    return task


@runs_router.post("", response_model=Dict[str, str])
async def start_workflow(
    req: StartRunRequest,
    bundle: ProjectBundle = Depends(get_project_bundle),
):
    """提交画布连线并后台异步运行"""
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    run_state = RunState(run_id=run_id, graph=req.graph)
    bundle.save_run(run_state.model_dump())

    launch_dag_task(run_state, req.client_id, bundle)
    return {"run_id": run_id, "status": "STARTED"}


@runs_router.get("/{run_id}", response_model=Dict)
async def get_run_status(
    run_id: str,
    bundle: ProjectBundle = Depends(get_project_bundle),
):
    """查询运行快照及断点待审批输入"""
    data = bundle.load_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="未找到该工作流运行记录")
    return data


@runs_router.post("/{run_id}/resume", response_model=Dict[str, str])
async def resume_workflow(
    run_id: str,
    req: ResumeRunRequest,
    bundle: ProjectBundle = Depends(get_project_bundle),
):
    """从断点注入修改后的 Payload 原地续跑"""
    raw_run = bundle.load_run(run_id)
    if not raw_run:
        raise HTTPException(status_code=404, detail="未找到该工作流记录")

    run_state = RunState.model_validate(raw_run)
    if run_state.status != "PAUSED" or not run_state.paused_node_id:
        raise HTTPException(status_code=400, detail="当前工作流未处于 PAUSED 挂起状态")

    paused_id = run_state.paused_node_id
    run_state.context[paused_id] = req.modified_output
    run_state.paused_node_id = None
    run_state.paused_inputs = None

    # 通知前端断点节点已转为完成
    await ws_manager.send_event(req.client_id, "NODE_STATUS", {
        "run_id": run_id, "node_id": paused_id, "status": "COMPLETED"
    })

    # 继续后台调度下游节点
    launch_dag_task(run_state, req.client_id, bundle)
    return {"run_id": run_id, "status": "RESUMED"}


@runs_router.post("/{run_id}/cancel", response_model=Dict[str, str])
async def cancel_workflow(
    run_id: str,
    client_id: str,
    bundle: ProjectBundle = Depends(get_project_bundle),
):
    """
    一键中止工作流：
    1. 正在运行态：取消 asyncio.Task，触发 CancelledError 级联中断
    2. 断点挂起态：直接修改状态为 CANCELLED，通知前端关闭弹窗
    """
    raw_run = bundle.load_run(run_id)
    if not raw_run:
        raise HTTPException(status_code=404, detail="未找到该工作流记录")

    # 情况 A：后台正在并发运行
    task = ACTIVE_TASKS.get(run_id)
    if task and not task.done():
        task.cancel()
        return {"run_id": run_id, "status": "CANCELLING"}

    # 情况 B：正处于断点暂停无活跃协程
    if raw_run["status"] == "PAUSED":
        raw_run["status"] = "CANCELLED"
        raw_run["paused_node_id"] = None
        raw_run["paused_inputs"] = None
        bundle.save_run(raw_run)
        await ws_manager.send_event(client_id, "WORKFLOW_STATUS", {
            "run_id": run_id, "status": "CANCELLED"
        })
        return {"run_id": run_id, "status": "CANCELLED"}

    return {"run_id": run_id, "status": raw_run["status"]}
