from typing import Any, Dict, List
from pydantic import BaseModel
from app.schemas.graph import GraphDef, NodeDef, EdgeDef


class SubgraphTemplate(BaseModel):
    template_id: str                # 例如 "sub_standard_context_pack"
    name: str
    graph: GraphDef                 # 子图内部的节点与连线
    input_node_id: str              # 子图对外的统一入口节点 ID
    output_node_id: str             # 子图对外的统一出口节点 ID


def flatten_subgraphs(
    graph: GraphDef,
    templates: Dict[str, SubgraphTemplate],
) -> GraphDef:
    """
    将包含 subgraph 节点的画布递归扁平化为标准 DAG。
    子图节点的 type 约定为 "subgraph"，params 中包含 {"template_id": "..."}。
    """
    flat_nodes: List[NodeDef] = []
    flat_edges: List[EdgeDef] = []

    # 记录子图节点 ID -> (展开后的真实入口 ID, 展开后的真实出口 ID)
    subgraph_io_map: Dict[str, tuple[str, str]] = {}

    for node in graph.nodes:
        if node.type != "subgraph":
            flat_nodes.append(node)
            continue

        tpl_id = node.params.get("template_id")
        if not tpl_id or tpl_id not in templates:
            raise ValueError(f"未找到子图模板: {tpl_id}")

        # 递归展开嵌套子图
        tpl = templates[tpl_id]
        inner_graph = flatten_subgraphs(tpl.graph, templates)

        # 给内部节点加上父节点前缀防重名，例如 "sub1__node_rag"
        prefix = f"{node.id}__"
        for inner_node in inner_graph.nodes:
            cloned = inner_node.model_copy(deep=True)
            cloned.id = f"{prefix}{inner_node.id}"
            # 允许外部在子图面板上覆盖内部参数（如出场角色、细纲）
            overrides = node.params.get("overrides", {}).get(inner_node.id, {})
            cloned.params.update(overrides)
            flat_nodes.append(cloned)

        for inner_edge in inner_graph.edges:
            flat_edges.append(EdgeDef(
                source=f"{prefix}{inner_edge.source}",
                target=f"{prefix}{inner_edge.target}",
            ))

        subgraph_io_map[node.id] = (
            f"{prefix}{tpl.input_node_id}",
            f"{prefix}{tpl.output_node_id}",
        )

    # 重定向外部连线：原本连入子图的线改连到内部入口，连出子图的线改从内部出口连出
    for edge in graph.edges:
        new_source = subgraph_io_map[edge.source][1] if edge.source in subgraph_io_map else edge.source
        new_target = subgraph_io_map[edge.target][0] if edge.target in subgraph_io_map else edge.target
        flat_edges.append(EdgeDef(source=new_source, target=new_target))

    return GraphDef(nodes=flat_nodes, edges=flat_edges)
