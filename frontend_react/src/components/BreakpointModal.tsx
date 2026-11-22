import { useEffect, useState } from 'react';
import { useGraphStore } from '../stores/useGraphStore';
import { wsClient } from '../services/wsClient';

export function BreakpointModal() {
  const breakpoint = useGraphStore((s) => s.breakpoint);
  const [jsonText, setJsonText] = useState('');
  const [parseError, setParseError] = useState<string | null>(null);

  useEffect(() => {
    if (breakpoint) {
      setJsonText(JSON.stringify(breakpoint.payload, null, 2));
      setParseError(null);
    }
  }, [breakpoint]);

  if (!breakpoint) return null;

  const handleResume = async () => {
    try {
      const parsed = JSON.parse(jsonText);
      setParseError(null);
      await wsClient.resumeWorkflow(breakpoint.taskId, breakpoint.nodeId, parsed);
    } catch {
      setParseError('JSON 格式错误，请检查后再继续');
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.65)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div style={{ width: 560, background: '#1e293b', color: '#f8fafc', borderRadius: 10, padding: 20 }}>
        <h3 style={{ margin: '0 0 8px' }}>人工审批断点 · 节点 `{breakpoint.nodeId}`</h3>
        <p style={{ margin: '0 0 12px', fontSize: 12, color: '#94a3b8' }}>
          可直接微调下方 EnvelopePayload（如勾选 selected 资产或修正 State Diff），确认后恢复 DAG 执行。
        </p>

        <textarea
          value={jsonText}
          onChange={(e) => setJsonText(e.target.value)}
          rows={14}
          style={{
            width: '100%',
            background: '#0f172a',
            color: '#a5f3fc',
            border: '1px solid #334155',
            borderRadius: 6,
            padding: 10,
            fontFamily: 'monospace',
            fontSize: 12,
            boxSizing: 'border-box',
          }}
        />
        {parseError && <div style={{ color: '#f87171', fontSize: 12, marginTop: 6 }}>{parseError}</div>}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 14 }}>
          <button
            onClick={() => wsClient.cancelWorkflow(breakpoint.taskId)}
            style={{ padding: '6px 14px', background: '#991b1b', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}
          >
            中止任务 (/cancel)
          </button>
          <button
            onClick={handleResume}
            style={{ padding: '6px 14px', background: '#16a34a', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}
          >
            审批通过并继续 (/resume)
          </button>
        </div>
      </div>
    </div>
  );
}
