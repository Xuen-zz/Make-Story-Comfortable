import { create } from 'zustand';

interface StreamState {
  activeNodeId: string | null;
  buffers: Record<string, string>;
  setActiveNodeId: (nodeId: string | null) => void;
  appendChunk: (nodeId: string, chunk: string) => void;
  clearBuffers: () => void;
}

export const useStreamStore = create<StreamState>((set) => ({
  activeNodeId: null,
  buffers: {},

  setActiveNodeId: (nodeId) => set({ activeNodeId: nodeId }),

  appendChunk: (nodeId, chunk) =>
    set((s) => ({
      activeNodeId: s.activeNodeId ?? nodeId,
      buffers: {
        ...s.buffers,
        [nodeId]: (s.buffers[nodeId] ?? '') + chunk,
      },
    })),

  clearBuffers: () => set({ activeNodeId: null, buffers: {} }),
}));
