export type NodeRunStatus = 'idle' | 'queued' | 'running' | 'cached' | 'paused' | 'completed' | 'error';

export type PortType = 'ASSET_BUNDLE' | 'PROMPT_CONTEXT' | 'PROSE_DRAFT' | 'STATE_DIFF_PROPOSAL';

export interface WorkflowNodeData extends Record<string, unknown> {
  label: string;
  nodeType: string;
  inPort?: PortType;
  outPort?: PortType;
  status: NodeRunStatus;
  errorMsg?: string;
}

export type WsMessage =
  | {
      type: 'NODE_STATUS';
      node_id: string;
      status: NodeRunStatus;
      error?: string;
    }
  | {
      type: 'TOKEN_STREAM';
      node_id: string;
      chunk: string;
      done?: boolean;
    }
  | {
      type: 'WORKFLOW_STATUS';
      status: 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'CANCELLED' | 'ERROR';
      task_id?: string;
      paused_node_id?: string;
      payload?: Record<string, unknown>; // 断点待审批的 EnvelopePayload
    };
