import { useEffect, useRef } from 'react';
import { useStreamStore } from '../stores/useStreamStore';

export function StreamPanel() {
  const activeNodeId = useStreamStore((s) => s.activeNodeId);
  const buffers = useStreamStore((s) => s.buffers);
  const setActiveNodeId = useStreamStore((s) => s.setActiveNodeId);
  const preRef = useRef<HTMLPreElement | null>(null);

  const nodeIds = Object.keys(buffers);
  const currentText = activeNodeId ? buffers[activeNodeId] ?? '' : '';

  // 强化补全：流式吐字时自动平滑滚动触底
  useEffect(() => {
    if (preRef.current) {
      preRef.current.scrollTop = preRef.current.scrollHeight;
    }
  }, [currentText]);

  return (
    <aside
      style={{
        width: 380,
        background: '#0f172a',
        color: '#e2e8f0',
        borderLeft: '1px solid #334155',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #334155', fontSize: 13, fontWeight: 600 }}>
        实时推流输出 {activeNodeId ? `· [${activeNodeId}]` : ''}
      </div>

      {/* 强化补全：Kahn 拓扑并发推流适配 Tab，支持切换查看不同并发节点的正文缓冲区 */}
      {nodeIds.length > 0 && (
        <div style={{ display: 'flex', gap: 6, padding: '8px 12px', borderBottom: '1px solid #1e293b', overflowX: 'auto' }}>
          {nodeIds.map((id) => (
            <button
              key={id}
              onClick={() => setActiveNodeId(id)}
              style={{
                padding: '3px 8px',
                fontSize: 11,
                borderRadius: 4,
                border: 'none',
                cursor: 'pointer',
                background: id === activeNodeId ? '#2563eb' : '#1e293b',
                color: id === activeNodeId ? '#ffffff' : '#94a3b8',
              }}
            >
              {id}
            </button>
          ))}
        </div>
      )}

      <pre
        ref={preRef}
        style={{
          flex: 1,
          margin: 0,
          padding: 16,
          overflowY: 'auto',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
          fontSize: 13,
          lineHeight: 1.7,
        }}
      >
        {currentText || '等待 TOKEN_STREAM 推流...'}
      </pre>
    </aside>
  );
}
