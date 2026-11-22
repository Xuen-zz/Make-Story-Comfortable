from typing import Callable, Dict

NODE_REGISTRY: Dict[str, Callable] = {}


def register_node(node_type: str):
    """
    节点注册装饰器：
    解耦 DAG 引擎与具体节点实现，支持插件式热插拔扩展
    """
    def decorator(func: Callable):
        NODE_REGISTRY[node_type] = func
        return func
    return decorator


def get_node_handler(node_type: str) -> Callable:
    handler = NODE_REGISTRY.get(node_type)
    if not handler:
        raise ValueError(f"未注册的节点类型: {node_type}，请检查是否已在 app.nodes 中注册")
    return handler
