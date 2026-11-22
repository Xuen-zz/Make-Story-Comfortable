import asyncio
import copy
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.dag_engine import execute_dag
from app.schemas.graph import GraphDef, RunState
from app.storage.project_bundle import ProjectBundle


class BatchVariant(BaseModel):
    variant_name: str               # 例如 "冷冽克制版 (temp=0.6)"
    target_node_id: str             # 要修改参数的采样器节点 ID
    param_overrides: Dict[str, Any] = Field(default_factory=dict)


class BatchRunRequest(BaseModel):
    client_id: str
    base_graph: GraphDef
    variants: List[BatchVariant]
    max_concurrency: int = 3


async def run_batch_drafts(
    req: BatchRunRequest,
    bundle: Optional[ProjectBundle] = None,
) -> List[Dict[str, Any]]:
    """
    并发生成多版正文草稿：
    1. 先跑第一个变体预热上游资产缓存（RAG/角色卡）
    2. 其余变体并发执行，直接复用缓存，只重跑采样器
    """
    semaphore = asyncio.Semaphore(req.max_concurrency)

    async def _run_one(variant: BatchVariant) -> Dict[str, Any]:
        async with semaphore:
            graph_copy = copy.deepcopy(req.base_graph)
            for node in graph_copy.nodes:
                if node.id == variant.target_node_id:
                    node.params.update(variant.param_overrides)
                    # 强制关闭草稿阶段的下游断点
                    node.is_breakpoint = False

            run_id = f"batch_{uuid.uuid4().hex[:8]}"
            run_state = RunState(run_id=run_id, graph=graph_copy)
            await execute_dag(run_state, client_id=req.client_id, bundle=bundle)

            draft_output = run_state.context.get(variant.target_node_id)
            return {
                "run_id": run_id,
                "variant_name": variant.variant_name,
                "status": run_state.status,
                "draft_text": draft_output.payload.get("text", "") if draft_output else "",
            }

    if not req.variants:
        return []

    # 先跑第 1 组预热上游节点缓存
    first_result = await _run_one(req.variants[0])
    if len(req.variants) == 1:
        return [first_result]

    # 剩余变体并发抽卡
    rest_tasks = [_run_one(v) for v in req.variants[1:]]
    rest_results = await asyncio.gather(*rest_tasks)
    return [first_result, *rest_results]
