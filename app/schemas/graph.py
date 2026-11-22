from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.schemas.payload import EnvelopePayload


class NodeDef(BaseModel):
    id: str
    type: str                                  # 节点类型，如 rag_retriever, llm_sampler
    params: Dict[str, Any] = Field(default_factory=dict)  # 节点面板参数
    is_breakpoint: bool = False                # 是否开启人工审批断点


class EdgeDef(BaseModel):
    source: str                                # 上游节点 ID
    target: str                                # 下游节点 ID


class GraphDef(BaseModel):
    nodes: List[NodeDef] = Field(default_factory=list)
    edges: List[EdgeDef] = Field(default_factory=list)


class RunState(BaseModel):
    run_id: str
    status: str = "PENDING"                    # PENDING | RUNNING | PAUSED | COMPLETED | FAILED | CANCELLED
    graph: GraphDef
    context: Dict[str, EnvelopePayload] = Field(default_factory=dict)
    paused_node_id: Optional[str] = None
    paused_inputs: Optional[Dict[str, EnvelopePayload]] = None


class StartRunRequest(BaseModel):
    client_id: str
    graph: GraphDef


class ResumeRunRequest(BaseModel):
    client_id: str
    modified_output: EnvelopePayload
