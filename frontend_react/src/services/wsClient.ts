import { useGraphStore } from '../stores/useGraphStore';
import { useStreamStore } from '../stores/useStreamStore';
import type { WsMessage } from '../types/protocol';

const API_BASE = 'http://127.0.0.1:8000';
const WS_BASE = 'ws://127.0.0.1:8000';

class WorkflowWsClient {
  private ws: WebSocket | null = null;
  public readonly clientId: string;
  private reconnectTimer: number | null = null;
  private onConnectionChange?: (connected: boolean) => void;
  // 必须修的 Bug：解决 React 18 StrictMode 双重挂载导致的幽灵重连
  private manualClose = false;

  constructor() {
    this.clientId = `client_${Math.random().toString(36).slice(2, 10)}`;
  }

  connect(onConnectionChange?: (connected: boolean) => void) {
    this.onConnectionChange = onConnectionChange;
    this.manualClose = false;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

    this.ws = new WebSocket(`${WS_BASE}/ws/${this.clientId}`);

    this.ws.onopen = () => {
      this.onConnectionChange?.(true);
    };

    this.ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        this.dispatch(msg);
      } catch (err) {
        console.error('[WS] Failed to parse message:', err);
      }
    };

    this.ws.onclose = () => {
      this.onConnectionChange?.(false);
      // 只有在非人为主动关闭时才触发重连
      if (!this.manualClose) {
        this.reconnectTimer = window.setTimeout(() => this.connect(this.onConnectionChange), 2000);
      }
    };
  }

  disconnect() {
    this.manualClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }

  private dispatch(msg: WsMessage) {
    switch (msg.type) {
      case 'TOKEN_STREAM':
        // 仅触碰 StreamStore，画布零重渲染
        useStreamStore.getState().appendChunk(msg.node_id, msg.chunk);
        break;

      case 'NODE_STATUS':
        useGraphStore.getState().setNodeStatus(msg.node_id, msg.status, msg.error);
        break;

      case 'WORKFLOW_STATUS':
        useGraphStore.getState().setWorkflowStatus(
          msg.status,
          msg.task_id,
          msg.status === 'PAUSED' && msg.paused_node_id
            ? {
                taskId: msg.task_id ?? '',
                nodeId: msg.paused_node_id,
                payload: msg.payload ?? {},
              }
            : null
        );
        break;
    }
  }

  // --- REST 控制指令 ---

  async runWorkflow() {
    const { nodes, edges, resetAllNodeStatuses } = useGraphStore.getState();
    resetAllNodeStatuses();
    useStreamStore.getState().clearBuffers();

    const res = await fetch(`${API_BASE}/api/workflow/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: this.clientId,
        nodes: nodes.map((n) => ({ id: n.id, type: n.data.nodeType })),
        edges: edges.map((e) => ({ source: e.source, target: e.target })),
      }),
    });
    const data = await res.json();
    // 强化补全：拿到 task_id 后立刻同步状态，消除一键中止 /cancel 按钮的不可用盲区
    if (data.task_id) {
      useGraphStore.getState().setWorkflowStatus('RUNNING', data.task_id);
    }
    return data;
  }

  async resumeWorkflow(taskId: string, nodeId: string, modifiedPayload: Record<string, unknown>) {
    const res = await fetch(`${API_BASE}/api/workflow/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: this.clientId,
        task_id: taskId,
        node_id: nodeId,
        override_payload: modifiedPayload,
      }),
    });
    return res.json();
  }

  async cancelWorkflow(taskId: string) {
    const res = await fetch(`${API_BASE}/api/workflow/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_id: this.clientId, task_id: taskId }),
    });
    return res.json();
  }
}

export const wsClient = new WorkflowWsClient();
