import asyncio
import hashlib
import inspect
import json
from typing import Any, Callable, Dict, List, Optional
from app.core.registry import get_node_handler
from app.schemas.graph import GraphDef, NodeDef, RunState
from app.schemas.payload import EnvelopePayload
from app.storage.project_bundle import ProjectBundle


def compute_cache_key(node: NodeDef, inputs: Dict[str, EnvelopePayload]) -> str:
    """
    ComfyUI 式脏检查缓存指纹：
    hash(node.type + node.params + sorted(upstream_inputs))
    """
    raw = {
        "type": node.type,
        "params": node.params,
        "inputs": {k: v.model_dump() for k, v in sorted(inputs.items())},
    }
    encoded = json.dumps(raw, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def run_single_node(
    run_id: str,
    client_id: str,
    node: NodeDef,
    inputs: Dict[str, EnvelopePayload],
    bundle: Optional[ProjectBundle] = None,
    ws_emitter: Optional[Callable[[str, str, dict], Any]] = None,
) -> EnvelopePayload:
    """执行单个节点：包含脏检查缓存、推流通知、自愈及取消处理"""
    cache_key = compute_cache_key(node, inputs)

    # 1. 脏检查缓存命中
    if bundle:
        cached_dict = bundle.get_cache(cache_key)
        if cached_dict:
            payload = EnvelopePayload.model_validate(cached_dict)
            if ws_emitter:
                await ws_emitter(client_id, "NODE_STATUS", {
                    "run_id": run_id, "node_id": node.id, "status": "CACHED"
                })
            return payload

    # 2. 开始运行通知
    if ws_emitter:
        await ws_emitter(client_id, "NODE_STATUS", {
            "run_id": run_id, "node_id": node.id, "status": "RUNNING"
        })

    handler = get_node_handler(node.type)

    # 3. 构造打字机流式回调
    async def emit_token(chunk: str):
        if ws_emitter:
            await ws_emitter(client_id, "TOKEN_STREAM", {
                "run_id": run_id, "node_id": node.id, "chunk": chunk
            })

    try:
        # 支持普通节点（2 参数）与流式节点（3 参数）
        sig = inspect.signature(handler)
        if len(sig.parameters) >= 3:
            output: EnvelopePayload = await handler(node.params, inputs, emit_token)
        else:
            output: EnvelopePayload = await handler(node.params, inputs)

    except asyncio.CancelledError:
        # 核心：被取消时绝不写入缓存，推送 CANCELLED 并向上穿透
        if ws_emitter:
            await ws_emitter(client_id, "NODE_STATUS", {
                "run_id": run_id, "node_id": node.id, "status": "CANCELLED"
            })
        raise
    except Exception as e:
        if ws_emitter:
            await ws_emitter(client_id, "NODE_STATUS", {
                "run_id": run_id, "node_id": node.id, "status": "FAILED", "error": str(e)
            })
        raise

    # 4. 写入缓存并通知完成
    if bundle:
        bundle.set_cache(cache_key, node.type, output.model_dump())

    if ws_emitter:
        await ws_emitter(client_id, "NODE_STATUS", {
            "run_id": run_id, "node_id": node.id, "status": "COMPLETED"
        })
    return output


async def execute_dag(
    run_state: RunState,
    client_id: str = "default",
    bundle: Optional[ProjectBundle] = None,
    ws_emitter: Optional[Callable[[str, str, dict], Any]] = None,
):
    """
    Kahn 算法异步并发 DAG 调度器：
    1. 动态入度自愈计算，断点恢复零冗余执行
    2. 无状态断点挂起（持久化后释放协程）
    3. 全流程 CancelledError 透明拦截与安全退出
    """
    run_state.status = "RUNNING"
    if bundle:
        bundle.save_run(run_state.model_dump())

    nodes_map = {n.id: n for n in run_state.graph.nodes}
    children_map: Dict[str, List[str]] = {n.id: [] for n in run_state.graph.nodes}
    parents_map: Dict[str, List[str]] = {n.id: [] for n in run_state.graph.nodes}

    for edge in run_state.graph.edges:
        if edge.source in children_map and edge.target in parents_map:
            children_map[edge.source].append(edge.target)
            parents_map[edge.target].append(edge.source)

    # 计算剩余入度：已存在于 context 中的节点视为已完成
    in_degree: Dict[str, int] = {}
    for nid in nodes_map:
        if nid in run_state.context:
            in_degree[nid] = -1
        else:
            pending_parents = [p for p in parents_map[nid] if p not in run_state.context]
            in_degree[nid] = len(pending_parents)

    ready_queue = [nid for nid, deg in in_degree.items() if deg == 0]

    try:
        while ready_queue:
            # 1. 优先检查是否存在人工断点
            for nid in ready_queue:
                node = nodes_map[nid]
                if node.is_breakpoint:
                    upstream_inputs = {p: run_state.context[p] for p in parents_map[nid]}
                    run_state.status = "PAUSED"
                    run_state.paused_node_id = nid
                    run_state.paused_inputs = upstream_inputs
                    if bundle:
                        bundle.save_run(run_state.model_dump())
                    if ws_emitter:
                        await ws_emitter(client_id, "WORKFLOW_STATUS", {
                            "run_id": run_state.run_id,
                            "status": "PAUSED",
                            "paused_node_id": nid,
                            "paused_inputs": {k: v.model_dump() for k, v in upstream_inputs.items()},
                        })
                    return

            # 2. 并发执行就绪节点
            tasks = [
                run_single_node(
                    run_state.run_id,
                    client_id,
                    nodes_map[nid],
                    {p: run_state.context[p] for p in parents_map[nid]},
                    bundle=bundle,
                    ws_emitter=ws_emitter,
                )
                for nid in ready_queue
            ]
            results = await asyncio.gather(*tasks)

            # 3. 收集产出并释放下游节点依赖
            next_ready = []
            for nid, output_payload in zip(ready_queue, results):
                run_state.context[nid] = output_payload
                in_degree[nid] = -1
                for child_id in children_map[nid]:
                    if in_degree[child_id] > 0:
                        in_degree[child_id] -= 1
                        if in_degree[child_id] == 0:
                            next_ready.append(child_id)

            ready_queue = next_ready

        # 4. 环路/死锁校验
        if len(run_state.context) != len(nodes_map):
            raise RuntimeError("DAG 检测到环路死锁或存在孤立不可达节点")

        run_state.status = "COMPLETED"
        if bundle:
            bundle.save_run(run_state.model_dump())
        if ws_emitter:
            await ws_emitter(client_id, "WORKFLOW_STATUS", {
                "run_id": run_state.run_id,
                "status": "COMPLETED",
            })

    except asyncio.CancelledError:
        run_state.status = "CANCELLED"
        if bundle:
            bundle.save_run(run_state.model_dump())
        if ws_emitter:
            await ws_emitter(client_id, "WORKFLOW_STATUS", {
                "run_id": run_state.run_id,
                "status": "CANCELLED",
            })
        raise
    except Exception as e:
        run_state.status = "FAILED"
        if bundle:
            bundle.save_run(run_state.model_dump())
        if ws_emitter:
            await ws_emitter(client_id, "WORKFLOW_STATUS", {
                "run_id": run_state.run_id,
                "status": "FAILED",
                "error": str(e),
            })
        raise
