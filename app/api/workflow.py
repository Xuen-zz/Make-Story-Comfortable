import asyncio
import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.api.ws import ws_manager

workflow_router = APIRouter(prefix="/api/workflow", tags=["workflow"])

# 运行中任务表 & 断点挂起信号表
ACTIVE_TASKS: Dict[str, asyncio.Task] = {}
PAUSE_EVENTS: Dict[str, asyncio.Event] = {}
RESUME_OVERRIDES: Dict[str, Dict[str, Any]] = {}


class RunRequest(BaseModel):
    client_id: str
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []


class ResumeRequest(BaseModel):
    client_id: str
    task_id: str
    node_id: str
    override_payload: Dict[str, Any]


class CancelRequest(BaseModel):
    client_id: str
    task_id: str


async def _run_mock_dag(task_id: str, client_id: str) -> None:
    try:
        await ws_manager.send_json(
            client_id,
            {"type": "WORKFLOW_STATUS", "status": "RUNNING", "task_id": task_id},
        )

        # --- 节点 1：资产检索 (node_asset) ---
        await ws_manager.send_json(
            client_id, {"type": "NODE_STATUS", "node_id": "node_asset", "status": "running"}
        )
        await asyncio.sleep(0.8)
        await ws_manager.send_json(
            client_id, {"type": "NODE_STATUS", "node_id": "node_asset", "status": "completed"}
        )

        # --- 节点 2：上下文装配 (node_prompt) -> 触发人工断点 ---
        await ws_manager.send_json(
            client_id, {"type": "NODE_STATUS", "node_id": "node_prompt", "status": "running"}
        )
        await asyncio.sleep(0.6)

        mock_envelope = {
            "port_type": "PROMPT_CONTEXT",
            "active_scope": "vol_1/northern_border",
            "selected_assets": [
                {"id": "char_01", "name": "林渊", "selected": True},
                {"id": "foreshadow_07", "desc": "断剑内的残魂", "selected": True},
            ],
            "instruction": "保持冷峻克制的文风，突出风雪夜的压迫感。",
        }

        # 挂起等待前端 /resume
        pause_event = asyncio.Event()
        PAUSE_EVENTS[task_id] = pause_event

        await ws_manager.send_json(
            client_id, {"type": "NODE_STATUS", "node_id": "node_prompt", "status": "paused"}
        )
        await ws_manager.send_json(
            client_id,
            {
                "type": "WORKFLOW_STATUS",
                "status": "PAUSED",
                "task_id": task_id,
                "paused_node_id": "node_prompt",
                "payload": mock_envelope,
            },
        )

        # 阻塞在此处，直到 /resume 触发 set() 或 /cancel 抛出 CancelledError
        await pause_event.wait()

        # 恢复执行，读取人工微调后的 payload
        final_payload = RESUME_OVERRIDES.pop(task_id, mock_envelope)
        await ws_manager.send_json(
            client_id,
            {"type": "WORKFLOW_STATUS", "status": "RUNNING", "task_id": task_id},
        )
        await ws_manager.send_json(
            client_id, {"type": "NODE_STATUS", "node_id": "node_prompt", "status": "completed"}
        )

        # --- 节点 3：正文生成 (node_writer) -> 模拟流式吐字 ---
        await ws_manager.send_json(
            client_id, {"type": "NODE_STATUS", "node_id": "node_writer", "status": "running"}
        )

        instruction = final_payload.get("instruction", "")
        mock_prose = (
            f"【已应用审批指令：{instruction}】\n\n"
            "风雪在亥时骤然收紧，北境残垣上的积雪被卷成细碎的冰针，拍打在林渊的玄铁护腕上。"
            "他没有回头，只是指腹轻轻摩挲着腰间那柄断剑的缺口——剑脊深处传来一声极轻的嗡鸣，"
            "像是某种沉睡了百年的意志，正隔着寒夜嗅到了熟悉的血气。\n\n"
            "“你终究还是来了。”风声里夹杂着一句低语，分不清是来自暗处，还是来自他自己的识海。"
        )

        # 逐字/逐块推流，测试前端 Zustand 隔离防掉帧
        for i in range(0, len(mock_prose), 3):
            chunk = mock_prose[i : i + 3]
            await ws_manager.send_json(
                client_id,
                {"type": "TOKEN_STREAM", "node_id": "node_writer", "chunk": chunk},
            )
            await asyncio.sleep(0.04)

        await ws_manager.send_json(
            client_id, {"type": "NODE_STATUS", "node_id": "node_writer", "status": "completed"}
        )
        await ws_manager.send_json(
            client_id,
            {"type": "WORKFLOW_STATUS", "status": "COMPLETED", "task_id": task_id},
        )

    except asyncio.CancelledError:
        await ws_manager.send_json(
            client_id,
            {"type": "WORKFLOW_STATUS", "status": "CANCELLED", "task_id": task_id},
        )
        raise
    finally:
        ACTIVE_TASKS.pop(task_id, None)
        PAUSE_EVENTS.pop(task_id, None)
        RESUME_OVERRIDES.pop(task_id, None)


@workflow_router.post("/run")
async def run_workflow(req: RunRequest) -> Dict[str, str]:
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    task = asyncio.create_task(_run_mock_dag(task_id, req.client_id))
    ACTIVE_TASKS[task_id] = task
    return {"task_id": task_id, "status": "started"}


@workflow_router.post("/resume")
async def resume_workflow(req: ResumeRequest) -> Dict[str, str]:
    event = PAUSE_EVENTS.get(req.task_id)
    if event is None:
        raise HTTPException(status_code=404, detail="未找到对应的挂起任务")
    RESUME_OVERRIDES[req.task_id] = req.override_payload
    event.set()
    return {"task_id": req.task_id, "status": "resumed"}


@workflow_router.post("/cancel")
async def cancel_workflow(req: CancelRequest) -> Dict[str, str]:
    task = ACTIVE_TASKS.get(req.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="未找到对应运行中任务或任务已结束")
    task.cancel()
    return {"task_id": req.task_id, "status": "cancelling"}
