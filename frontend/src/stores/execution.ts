import { defineStore } from 'pinia'
import { ref } from 'vue'

export type NodeExecutionStatus = 'IDLE' | 'RUNNING' | 'CACHED' | 'COMPLETED' | 'FAILED' | 'CANCELLED'

export interface BreakpointModalData {
  runId: string
  nodeId: string
  inputs: Record<string, any>
}

export const useExecutionStore = defineStore('execution', () => {
  // 节点高亮运行状态表：按 nodeId 细粒度隔离
  const nodeStatus = ref<Record<string, NodeExecutionStatus>>({})
  
  // 逐字打字机流式字符缓冲区：按 nodeId 细粒度隔离
  const nodeStreams = ref<Record<string, string>>({})
  
  // 当前处于 PAUSED 挂起态的人工审批弹窗数据
  const pausedModal = ref<BreakpointModalData | null>(null)
  
  // 当前运行 run_id
  const currentRunId = ref<string | null>(null)

  function setNodeStatus(nodeId: string, status: NodeExecutionStatus) {
    nodeStatus.value[nodeId] = status
  }

  function appendToken(nodeId: string, chunk: string) {
    nodeStreams.value[nodeId] = (nodeStreams.value[nodeId] || '') + chunk
  }

  function setPausedModal(modal: BreakpointModalData | null) {
    pausedModal.value = modal
  }

  function setCurrentRunId(runId: string | null) {
    currentRunId.value = runId
  }

  function resetRun() {
    nodeStatus.value = {}
    nodeStreams.value = {}
    pausedModal.value = null
    currentRunId.value = null
  }

  return {
    nodeStatus,
    nodeStreams,
    pausedModal,
    currentRunId,
    setNodeStatus,
    appendToken,
    setPausedModal,
    setCurrentRunId,
    resetRun,
  }
})
