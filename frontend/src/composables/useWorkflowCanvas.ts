import { ref, computed } from 'vue'
import { postSSE, workflowApi, stylesApi, type SSEHandle } from '@/api/client'
import { useProjectStore } from '@/stores/project'
import { useConfigStore } from '@/stores/config'

export interface PortSpec {
  id: string
  label: string
  type: string
}

export interface NodeCatalogItem {
  type: string
  title: string
  desc: string
  inputs: PortSpec[]
  outputs: PortSpec[]
  defaultParams: Record<string, unknown>
}

export interface NodeCatalogCategory {
  id: string
  label: string
  nodes: NodeCatalogItem[]
}

export interface WorkflowPreset {
  id: string
  name: string
  description: string
  builtin: boolean
  nodes: any[]
  edges: any[]
  updated_at?: string
}

export interface NodeRuntimeState {
  status: 'idle' | 'running' | 'completed' | 'waiting_gate' | 'bypassed' | 'cached' | 'error'
  progress: number
  elapsed_ms?: number
  message?: string
  outputs?: Record<string, any>
}

export interface PendingGatePayload {
  run_id: string
  node_id: string
  node_type: 'ab_selector' | 'human_gate'
  title: string
  branch_a?: string
  branch_b?: string
  checklist_a?: string
  checklist_b?: string
  text_in?: string
  draft_text?: string
  checklist?: string
  note?: string
}

// ── 全局单例状态，确保「节点画布」与「写书工单台」共享模板与执行引擎 ─────────────────────────
const catalogCategories = ref<NodeCatalogCategory[]>([])
const portTypes = ref<Record<string, { label: string; color: string }>>({})
const defaultPrompts = ref<Record<string, string>>({})
const styleChoices = ref<string[]>([])

const builtins = ref<WorkflowPreset[]>([])
const customs = ref<WorkflowPreset[]>([])
const defaultWorkflowId = ref('standard_zh')

const activeWorkflowId = ref('standard_zh')
const activeWorkflowName = ref('🔥 标准双模型写审链（推荐日常连载）')
const nodes = ref<any[]>([])
const edges = ref<any[]>([])

const nodeRuntime = ref<Record<string, NodeRuntimeState>>({})
const nodeOutputsCache = ref<Record<string, Record<string, any>>>({})

const isRunning = ref(false)
const activeRunId = ref('')
const runElapsed = ref(0)
const runLogs = ref<string[]>([])
const runError = ref('')
const pendingGate = ref<PendingGatePayload | null>(null)
const inspectedNodeId = ref<string | null>(null)

// 批量队列与章节设定
const canvasChapterNum = ref(1)
const canvasWordNumber = ref(2500)
const batchModeEnabled = ref(false)
const batchStart = ref(1)
const batchEnd = ref(10)
const batchGatePolicy = ref<'manual' | 'auto_pass' | 'always_pause'>('manual')
const batchCurrentChapter = ref(0)

let sseHandle: SSEHandle | null = null
let runTimer: ReturnType<typeof setInterval> | null = null
let batchStopFlag = false
let loadedOnce = false

function cloneDeep<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj))
}

function stopTimer() {
  if (runTimer) {
    clearInterval(runTimer)
    runTimer = null
  }
}

export function useWorkflowCanvas() {
  const projectStore = useProjectStore()
  const configStore = useConfigStore()

  const allWorkflows = computed(() => [...builtins.value, ...customs.value])
  const nodeMetaMap = computed(() => {
    const map: Record<string, NodeCatalogItem> = {}
    for (const cat of catalogCategories.value) {
      for (const n of cat.nodes) map[n.type] = n
    }
    return map
  })

  const defaultWorkflow = computed(() =>
    allWorkflows.value.find(w => w.id === defaultWorkflowId.value) || builtins.value[0] || null,
  )

  async function init(forceReload = false) {
    if (loadedOnce && !forceReload && nodes.value.length > 0) return
    try {
      const [catRes, listRes, stRes] = await Promise.all([
        workflowApi.catalog(),
        workflowApi.list(),
        stylesApi.list().catch(() => ({ data: { styles: [] } })),
      ])
      catalogCategories.value = catRes.data.categories || []
      portTypes.value = catRes.data.port_types || {}
      defaultPrompts.value = catRes.data.default_prompts || {}

      builtins.value = listRes.data.builtins || []
      customs.value = listRes.data.customs || []
      defaultWorkflowId.value = listRes.data.default_workflow_id || 'standard_zh'

      const rawStyles = stRes.data?.styles || stRes.data || []
      styleChoices.value = Array.isArray(rawStyles)
        ? rawStyles.map((s: any) => (typeof s === 'string' ? s : s.name)).filter(Boolean)
        : []

      if (nodes.value.length === 0) {
        const target = allWorkflows.value.find(w => w.id === defaultWorkflowId.value) || builtins.value[0]
        if (target) loadWorkflowIntoCanvas(target)
      }
      loadedOnce = true
    } catch (e) {
      console.error('初始化节点工作流失败:', e)
    }
  }

  function loadWorkflowIntoCanvas(wf: WorkflowPreset) {
    activeWorkflowId.value = wf.id
    activeWorkflowName.value = wf.name
    nodes.value = cloneDeep(wf.nodes || [])
    edges.value = cloneDeep(wf.edges || [])
    resetRuntimeVisuals(true)
  }

  function resetRuntimeVisuals(clearCache = false) {
    const next: Record<string, NodeRuntimeState> = {}
    for (const n of nodes.value) {
      next[n.id] = { status: 'idle', progress: 0 }
    }
    nodeRuntime.value = next
    if (clearCache) nodeOutputsCache.value = {}
  }

  function updateNodeParam(nodeId: string, key: string, value: unknown) {
    const node = nodes.value.find(n => n.id === nodeId)
    if (!node) return
    if (!node.data.params) node.data.params = {}
    node.data.params[key] = value
  }

  function toggleNodeBypass(nodeId: string) {
    const node = nodes.value.find(n => n.id === nodeId)
    if (!node) return
    node.data.bypass = !node.data.bypass
  }

  function toggleNodeCollapsed(nodeId: string) {
    const node = nodes.value.find(n => n.id === nodeId)
    if (!node) return
    node.data.collapsed = !node.data.collapsed
  }

  function deleteNode(nodeId: string) {
    nodes.value = nodes.value.filter(n => n.id !== nodeId)
    edges.value = edges.value.filter(e => e.source !== nodeId && e.target !== nodeId)
  }

  function duplicateNode(nodeId: string) {
    const src = nodes.value.find(n => n.id === nodeId)
    if (!src) return
    const copy = cloneDeep(src)
    copy.id = `n_${Date.now().toString(36)}`
    copy.position = { x: (src.position?.x || 0) + 40, y: (src.position?.y || 0) + 40 }
    delete copy.parentNode
    delete copy.extent
    nodes.value = [...nodes.value, copy]
  }

  function addNode(nodeType: string, pos?: { x: number; y: number }) {
    if (nodeType === 'group') {
      const gid = `grp_${Date.now().toString(36)}`
      nodes.value = [
        {
          id: gid,
          type: 'groupNode',
          position: pos || { x: 260, y: 80 },
          style: { width: '420px', height: '380px' },
          data: { nodeType: 'group', label: '自定义工作流分组框', color: '#8b5cf6' },
        },
        ...nodes.value,
      ]
      return
    }
    const meta = nodeMetaMap.value[nodeType]
    if (!meta) return
    const nid = `n_${nodeType}_${Date.now().toString(36)}`
    nodes.value = [
      ...nodes.value,
      {
        id: nid,
        type: 'workflowNode',
        position: pos || { x: 280 + Math.random() * 140, y: 140 + Math.random() * 120 },
        data: {
          nodeType,
          label: meta.title,
          params: cloneDeep(meta.defaultParams || {}),
          bypass: false,
          collapsed: false,
        },
      },
    ]
    nodeRuntime.value = { ...nodeRuntime.value, [nid]: { status: 'idle', progress: 0 } }
  }

  function autoLayout() {
    // 基于拓扑层级排列 X，同层节点纵向错开 Y，清晰呈现 ComfyUI 从左向右流向
    const active = nodes.value.filter(n => n.type !== 'groupNode' && !n.parentNode)
    const ids = new Set(active.map(n => n.id))
    const inDeg: Record<string, number> = {}
    const adj: Record<string, string[]> = {}
    for (const id of ids) {
      inDeg[id] = 0
      adj[id] = []
    }
    for (const e of edges.value) {
      if (ids.has(e.source) && ids.has(e.target) && e.source !== e.target) {
        adj[e.source].push(e.target)
        inDeg[e.target]++
      }
    }
    const level: Record<string, number> = {}
    const q = Array.from(ids).filter(id => inDeg[id] === 0)
    for (const id of q) level[id] = 0
    while (q.length) {
      const cur = q.shift()!
      for (const nxt of adj[cur]) {
        level[nxt] = Math.max(level[nxt] ?? 0, (level[cur] ?? 0) + 1)
        inDeg[nxt]--
        if (inDeg[nxt] === 0) q.push(nxt)
      }
    }
    const byCol: Record<number, any[]> = {}
    for (const n of active) {
      const col = level[n.id] ?? 0
      if (!byCol[col]) byCol[col] = []
      byCol[col].push(n)
    }
    for (const colStr of Object.keys(byCol)) {
      const col = Number(colStr)
      const list = byCol[col]
      list.sort((a, b) => (a.position?.y || 0) - (b.position?.y || 0))
      list.forEach((n, rowIdx) => {
        n.position = { x: 60 + col * 350, y: 80 + rowIdx * 280 }
      })
    }
    nodes.value = [...nodes.value]
  }

  async function saveWorkflow(customName?: string) {
    const name = (customName ?? activeWorkflowName.value).trim() || '自定义写书工作流'
    const res = await workflowApi.save({
      id: builtins.value.some(b => b.id === activeWorkflowId.value) ? undefined : activeWorkflowId.value,
      name,
      description: `节点 ${nodes.value.length} 个 · 连线 ${edges.value.length} 条`,
      nodes: nodes.value,
      edges: edges.value,
    })
    const saved = res.data.workflow as WorkflowPreset
    activeWorkflowId.value = saved.id
    activeWorkflowName.value = saved.name
    await refreshWorkflowList()
    return saved
  }

  async function refreshWorkflowList() {
    const res = await workflowApi.list()
    builtins.value = res.data.builtins || []
    customs.value = res.data.customs || []
    defaultWorkflowId.value = res.data.default_workflow_id || 'standard_zh'
  }

  async function setAsDefaultWorkflow(wfId?: string) {
    const targetId = wfId || activeWorkflowId.value
    await workflowApi.setDefault(targetId)
    defaultWorkflowId.value = targetId
  }

  async function deleteCustom(wfId: string) {
    await workflowApi.remove(wfId)
    await refreshWorkflowList()
    if (activeWorkflowId.value === wfId && builtins.value[0]) {
      loadWorkflowIntoCanvas(builtins.value[0])
    }
  }

  // ── 真实 DAG 执行引擎对接 ──────────────────────────────────────────────────────
  function executeSingleChapter(opts: {
    chapterNum: number
    startFromNodeId?: string
    graphOverride?: { nodes: any[]; edges: any[] }
    isBatch?: boolean
    onEventLog?: (msg: string) => void
  }): Promise<boolean> {
    if (isRunning.value) return Promise.resolve(false)

    const targetGraph = opts.graphOverride || { nodes: nodes.value, edges: edges.value }
    const fp = projectStore.activeProjectData?.filepath || './output'
    const llmDefault = configStore.llmChoices[0] || ''
    const embDefault = configStore.embeddingChoices[0] || ''
    const rid = `run_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`

    activeRunId.value = rid
    isRunning.value = true
    runElapsed.value = 0
    runError.value = ''
    pendingGate.value = null
    if (!opts.startFromNodeId) {
      resetRuntimeVisuals(false)
      runLogs.value = []
    }
    stopTimer()
    runTimer = setInterval(() => { runElapsed.value++ }, 1000)

    return new Promise<boolean>((resolve) => {
      let succeeded = false

      const payload = {
        graph: targetGraph,
        filepath: fp,
        chapter_num: opts.chapterNum,
        llm_config_name: llmDefault,
        emb_config_name: embDefault,
        word_number: canvasWordNumber.value || 2500,
        run_id: rid,
        start_from_node_id: opts.startFromNodeId || '',
        initial_cache: opts.startFromNodeId ? cloneDeep(nodeOutputsCache.value) : null,
        is_batch_mode: Boolean(opts.isBatch),
        batch_gate_policy: batchGatePolicy.value,
      }

      sseHandle = postSSE(
        workflowApi.executeUrl(),
        payload,
        (msg, _val, content) => {
          if (msg) {
            const line = `[${new Date().toLocaleTimeString()}] ${msg}`
            runLogs.value.push(line)
            opts.onEventLog?.(line)
          }
          if (content) {
            try {
              const ev = JSON.parse(content)
              if (ev.workflow_event === 'node_status') {
                const nid = ev.node_id as string
                nodeRuntime.value = {
                  ...nodeRuntime.value,
                  [nid]: {
                    status: ev.status,
                    progress: ev.progress ?? (ev.status === 'completed' ? 100 : 20),
                    elapsed_ms: ev.elapsed_ms,
                    message: ev.message,
                    outputs: ev.outputs || nodeRuntime.value[nid]?.outputs,
                  },
                }
                if (ev.outputs) {
                  nodeOutputsCache.value = { ...nodeOutputsCache.value, [nid]: ev.outputs }
                }
                // 动态让正在跑的节点输出边亮起流动虚线
                edges.value = edges.value.map(e => ({
                  ...e,
                  animated: ev.status === 'running' ? e.target === nid || e.source === nid : false,
                }))
              } else if (ev.workflow_event === 'gate_waiting') {
                const nid = ev.node_id as string
                nodeRuntime.value = {
                  ...nodeRuntime.value,
                  [nid]: { status: 'waiting_gate', progress: 50, message: '等待人工确认…' },
                }
                pendingGate.value = {
                  run_id: ev.run_id || rid,
                  node_id: nid,
                  node_type: ev.node_type,
                  title: ev.title,
                  branch_a: ev.branch_a,
                  branch_b: ev.branch_b,
                  checklist_a: ev.checklist_a,
                  checklist_b: ev.checklist_b,
                  text_in: ev.text_in,
                  draft_text: ev.draft_text,
                  checklist: ev.checklist,
                  note: ev.note,
                }
              } else if (ev.workflow_event === 'run_completed') {
                succeeded = true
                edges.value = edges.value.map(e => ({ ...e, animated: false }))
              } else if (ev.workflow_event === 'run_error') {
                runError.value = ev.error || '执行异常'
                edges.value = edges.value.map(e => ({ ...e, animated: false }))
              }
            } catch { /* ignore non-json */ }
          }
        },
        (resStr) => {
          try {
            const parsed = JSON.parse(resStr)
            if (parsed.success) succeeded = true
            else if (parsed.error) runError.value = parsed.error
            if (parsed.outputs) nodeOutputsCache.value = { ...nodeOutputsCache.value, ...parsed.outputs }
          } catch { /* ignore */ }
        },
        (err) => {
          runError.value = err
          runLogs.value.push(`[${new Date().toLocaleTimeString()}] ❌ 异常: ${err}`)
          isRunning.value = false
          stopTimer()
          edges.value = edges.value.map(e => ({ ...e, animated: false }))
          resolve(false)
        },
        () => {
          isRunning.value = false
          stopTimer()
          pendingGate.value = null
          edges.value = edges.value.map(e => ({ ...e, animated: false }))
          resolve(succeeded)
        },
      )
    })
  }

  async function runBatchChapters(start?: number, end?: number) {
    const s = Math.max(1, start ?? batchStart.value)
    const e = Math.max(s, end ?? batchEnd.value)
    batchStopFlag = false
    batchModeEnabled.value = true
    for (let ch = s; ch <= e; ch++) {
      if (batchStopFlag) break
      batchCurrentChapter.value = ch
      canvasChapterNum.value = ch
      const ok = await executeSingleChapter({ chapterNum: ch, isBatch: true })
      if (!ok) break
    }
    batchModeEnabled.value = false
  }

  async function cancelActiveRun() {
    batchStopFlag = true
    if (activeRunId.value) {
      await workflowApi.cancel(activeRunId.value).catch(() => {})
    }
    if (sseHandle) {
      sseHandle.abort()
      sseHandle = null
    }
    pendingGate.value = null
    isRunning.value = false
    stopTimer()
    edges.value = edges.value.map(e => ({ ...e, animated: false }))
  }

  async function submitGate(decision: { action: 'approve' | 'cancel'; selected_branch?: string; edited_text?: string }) {
    if (!pendingGate.value) return
    const rid = pendingGate.value.run_id
    pendingGate.value = null
    await workflowApi.gateDecision(rid, decision)
  }

  return {
    catalogCategories,
    portTypes,
    defaultPrompts,
    styleChoices,
    builtins,
    customs,
    allWorkflows,
    defaultWorkflowId,
    defaultWorkflow,
    activeWorkflowId,
    activeWorkflowName,
    nodes,
    edges,
    nodeMetaMap,
    nodeRuntime,
    nodeOutputsCache,
    isRunning,
    activeRunId,
    runElapsed,
    runLogs,
    runError,
    pendingGate,
    inspectedNodeId,
    canvasChapterNum,
    canvasWordNumber,
    batchModeEnabled,
    batchStart,
    batchEnd,
    batchGatePolicy,
    batchCurrentChapter,
    init,
    loadWorkflowIntoCanvas,
    resetRuntimeVisuals,
    updateNodeParam,
    toggleNodeBypass,
    toggleNodeCollapsed,
    deleteNode,
    duplicateNode,
    addNode,
    autoLayout,
    saveWorkflow,
    refreshWorkflowList,
    setAsDefaultWorkflow,
    deleteCustom,
    executeSingleChapter,
    runBatchChapters,
    cancelActiveRun,
    submitGate,
  }
}
