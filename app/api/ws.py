from typing import Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

ws_router = APIRouter()


class ConnectionManager:
    """
    WebSocket 连接管理器：按 client_id 路由推流事件
    同时兼容 {"event": ...} 与 {"type": ...} 两种消息格式
    """
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)

    async def send_json(self, client_id: str, data: dict):
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                # 兼容性增强：若传了 type 没传 event，自动补齐 event；反之亦然
                payload = dict(data)
                if "type" in payload and "event" not in payload:
                    payload["event"] = payload["type"]
                elif "event" in payload and "type" not in payload:
                    payload["type"] = payload["event"]
                await ws.send_json(payload)
            except Exception:
                self.disconnect(client_id)

    async def send_event(self, client_id: str, event: str, data: dict):
        await self.send_json(client_id, {"event": event, "type": event, **data})


ws_manager = ConnectionManager()


@ws_router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(client_id, websocket)
    try:
        while True:
            # 接收前端 ping 心跳，保持长连接不断开
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
