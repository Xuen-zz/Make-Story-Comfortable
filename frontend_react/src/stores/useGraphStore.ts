import { create } from 'zustand';
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from '@xyflow/react';
import type { NodeRunStatus, WorkflowNodeData } from '../types/protocol';

export type AppNode = Node<WorkflowNodeData, 'workflowNode'>;

export interface BreakpointState {
  taskId: string;
  nodeId: string;
  payload: Record<string, unknown>;
}

interface GraphState {
  nodes: AppNode[];
  edges: Edge[];
  workflowStatus: 'IDLE' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'CANCELLED' | 'ERROR';
  activeTaskId: string | null;
  breakpoint: BreakpointState | null;

  onNodesChange: (changes: NodeChange<AppNode>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;

  setNodeStatus: (nodeId: string, status: NodeRunStatus, errorMsg?: string) => void;
  resetAllNodeStatuses: () => void;
  setWorkflowStatus: (
    status: GraphState['workflowStatus'],
    taskId?: string,
    breakpoint?: BreakpointState | null
  ) => void;
}

const INITIAL_NODES: AppNode[] = [
  {
    id: 'node_asset',
    type: 'workflowNode',
    position: { x: 80, y: 140 },
    data: { label: '资产检索 (Asset Loader)', nodeType: 'asset_loader', outPort: 'ASSET_BUNDLE', status: 'idle' },
  },
  {
    id: 'node_prompt',
    type: 'workflowNode',
    position: { x: 380, y: 140 },
    data: {
      label: '上下文装配 (Prompt Builder)',
      nodeType: 'prompt_builder',
      inPort: 'ASSET_BUNDLE',
      outPort: 'PROMPT_CONTEXT',
      status: 'idle',
    },
  },
  {
    id: 'node_writer',
    type: 'workflowNode',
    position: { x: 700, y: 140 },
    data: {
      label: '正文生成 (Prose Writer)',
      nodeType: 'prose_writer',
      inPort: 'PROMPT_CONTEXT',
      outPort: 'PROSE_DRAFT',
      status: 'idle',
    },
  },
];

const INITIAL_EDGES: Edge[] = [
  { id: 'e1-2', source: 'node_asset', target: 'node_prompt', animated: false },
  { id: 'e2-3', source: 'node_prompt', target: 'node_writer', animated: false },
];

export const useGraphStore = create<GraphState>((set) => ({
  nodes: INITIAL_NODES,
  edges: INITIAL_EDGES,
  workflowStatus: 'IDLE',
  activeTaskId: null,
  breakpoint: null,

  onNodesChange: (changes) => set((s) => ({ nodes: applyNodeChanges(changes, s.nodes) })),
  onEdgesChange: (changes) => set((s) => ({ edges: applyEdgeChanges(changes, s.edges) })),
  onConnect: (connection) => set((s) => ({ edges: addEdge(connection, s.edges) })),

  setNodeStatus: (nodeId, status, errorMsg) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, status, errorMsg } } : n
      ),
      edges: s.edges.map((e) =>
        e.target === nodeId ? { ...e, animated: status === 'running' } : e
      ),
    })),

  resetAllNodeStatuses: () =>
    set((s) => ({
      nodes: s.nodes.map((n) => ({ ...n, data: { ...n.data, status: 'idle', errorMsg: undefined } })),
      edges: s.edges.map((e) => ({ ...e, animated: false })),
      breakpoint: null,
    })),

  setWorkflowStatus: (workflowStatus, taskId, breakpoint = null) =>
    set((s) => ({
      workflowStatus,
      activeTaskId: taskId ?? s.activeTaskId,
      breakpoint: workflowStatus === 'PAUSED' ? breakpoint : null,
    })),
}));
