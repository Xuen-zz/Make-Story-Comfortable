import { useEffect, useState, useCallback } from 'react';
import { Background, Controls, MiniMap, ReactFlow, type Connection, type Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { useGraphStore } from './stores/useGraphStore';
import { wsClient } from './services/wsClient';
import { WorkflowNode } from './components/WorkflowNode';
import { StreamPanel } from './components/StreamPanel';
import { BreakpointModal } from './components/BreakpointModal';

// 必须在组件外定义，防止 React Flow 每次渲染卸载重建节点
const nodeTypes = { workflowNode: WorkflowNode };

export default function App() {
  const [connected, setConnected] = useState(false);

  const nodes = useGraphStore((s) => s.nodes);
  const edges = useGraphStore((s) => s.edges);
  const workflowStatus = useGraphStore((s) => s.workflowStatus);
  const activeTaskId = useGraphStore((s) => s.activeTaskId);
  const onNodesChange = useGraphStore((s) => s.onNodesChange);
  const onEdgesChange = useGraphStore((s) => s.onEdgesChange);
  const onConnect = useGraphStore((s) => s.onConnect);

  // 强化补全：port_type 连线防呆校验（阻止非匹配类型连线与自身成环）
  const isValidConnection = useCallback(
    (connection: Edge | Connection) => {
      if (connection.source === connection.target) return false;
      const src = nodes.find((n) => n.id === connection.source);
      const tgt = nodes.find((n) => n.id === connection.target);
      return Boolean(src?.data.outPort && src.data.outPort === tgt?.data.inPort);
    },
    [nodes]
  );

  useEffect(() => {
    wsClient.connect(setConnected);
    return () => wsClient.disconnect();
  }, []);

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', background: '#020617' }}>
      {/* 顶部联调控制栏 */}
      <header
        style={{
          height: 50,
          padding: '0 16px',
          background: '#0f172a',
          borderBottom: '1px solid #334155',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: '#f8fafc',
          fontSize: 13,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <strong>Novel DAG Studio</strong>
          <span style={{ color: connected ? '#4ade80' : '#f87171', fontSize: 12 }}>
            ● WS {connected ? `已连接 (${wsClient.clientId})` : '断开重连中...'}
          </span>
          <span style={{ color: '#94a3b8', fontSize: 12 }}>状态: {workflowStatus}</span>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button
            disabled={!connected || workflowStatus === 'RUNNING'}
            onClick={() => wsClient.runWorkflow()}
            style={{
              padding: '6px 14px',
              background: workflowStatus === 'RUNNING' ? '#475569' : '#2563eb',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              cursor: workflowStatus === 'RUNNING' ? 'not-allowed' : 'pointer',
              fontWeight: 600,
            }}
          >
            运行 DAG
          </button>
          <button
            disabled={!activeTaskId || (workflowStatus !== 'RUNNING' && workflowStatus !== 'PAUSED')}
            onClick={() => activeTaskId && wsClient.cancelWorkflow(activeTaskId)}
            style={{
              padding: '6px 14px',
              background: !activeTaskId || (workflowStatus !== 'RUNNING' && workflowStatus !== 'PAUSED') ? '#475569' : '#dc2626',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              cursor: !activeTaskId ? 'not-allowed' : 'pointer',
              fontWeight: 600,
            }}
          >
            一键中止 (/cancel)
          </button>
        </div>
      </header>

      {/* 主体：左侧画布 + 右侧隔离流式面板 */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <div style={{ flex: 1 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            isValidConnection={isValidConnection}
            fitView
            colorMode="dark"
          >
            <Background color="#334155" gap={20} />
            <Controls />
            <MiniMap nodeColor="#334155" maskColor="rgba(15, 23, 42, 0.7)" />
          </ReactFlow>
        </div>

        <StreamPanel />
      </div>

      <BreakpointModal />
    </div>
  );
}
