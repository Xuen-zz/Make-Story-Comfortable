import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { AppNode } from '../stores/useGraphStore';
import type { NodeRunStatus } from '../types/protocol';

const STATUS_STYLE: Record<NodeRunStatus, { border: string; badgeBg: string; label: string }> = {
  idle: { border: '#475569', badgeBg: '#334155', label: 'IDLE' },
  queued: { border: '#64748b', badgeBg: '#475569', label: 'QUEUED' },
  running: { border: '#3b82f6', badgeBg: '#1d4ed8', label: 'RUNNING' },
  cached: { border: '#14b8a6', badgeBg: '#0f766e', label: 'CACHED' },
  paused: { border: '#f59e0b', badgeBg: '#b45309', label: 'PAUSED' },
  completed: { border: '#22c55e', badgeBg: '#15803d', label: 'DONE' },
  error: { border: '#ef4444', badgeBg: '#b91c1c', label: 'ERROR' },
};

export const WorkflowNode = memo(({ data }: NodeProps<AppNode>) => {
  const style = STATUS_STYLE[data.status] || STATUS_STYLE.idle;

  return (
    <div
      style={{
        minWidth: 210,
        background: '#1e293b',
        color: '#f8fafc',
        border: `2px solid ${style.border}`,
        borderRadius: 8,
        padding: '10px 12px',
        boxShadow: data.status === 'running' ? '0 0 14px rgba(59,130,246,0.5)' : '0 4px 10px rgba(0,0,0,0.3)',
        fontSize: 13,
      }}
    >
      {data.inPort && (
        <Handle type="target" position={Position.Left} style={{ background: '#94a3b8', width: 10, height: 10 }} />
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <strong style={{ fontSize: 13 }}>{data.label}</strong>
        <span
          style={{
            fontSize: 10,
            padding: '2px 6px',
            borderRadius: 4,
            background: style.badgeBg,
            fontWeight: 600,
          }}
        >
          {style.label}
        </span>
      </div>

      <div style={{ fontSize: 11, color: '#94a3b8', display: 'flex', justifyContent: 'space-between' }}>
        <span>{data.inPort ? `IN: ${data.inPort}` : 'ENTRY'}</span>
        <span>{data.outPort ? `OUT: ${data.outPort}` : 'END'}</span>
      </div>

      {data.errorMsg && (
        <div style={{ marginTop: 6, fontSize: 11, color: '#fca5a5' }}>{data.errorMsg}</div>
      )}

      {data.outPort && (
        <Handle type="source" position={Position.Right} style={{ background: '#38bdf8', width: 10, height: 10 }} />
      )}
    </div>
  );
});
