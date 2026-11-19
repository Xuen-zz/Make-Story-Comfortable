<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { VueFlow, useVueFlow, type Connection, type NodeMouseEvent } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

import { generateApi } from '@/api/client'
import { useWorkflowCanvas } from '@/composables/useWorkflowCanvas'
import { useProjectStore } from '@/stores/project'
import WorkflowCustomNode from '@/components/workflow/WorkflowCustomNode.vue'
import WorkflowGroupNode from '@/components/workflow/WorkflowGroupNode.vue'
import DiffViewer from '@/components/workshop/DiffViewer.vue'

const route = useRoute()
const projectStore = useProjectStore()
const wf = useWorkflowCanvas()
const { fitView, screenToFlowCoordinate, addEdges } = useVueFlow()

const paletteOpen = ref(true)
const logsDrawerOpen = ref(false)
const saveModalOpen = ref(false)
const saveNameInput = ref('')
const toastMsg = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const inspectorFullscreen = ref(false)

// ── 双击画布模糊节点搜索浮窗 ────────────────────────────────────────────────────────
const quickSearch = ref<{
  x: number
  y: number
  flowPos: { x: number; y: number }
} | null>(null)
const quickSearchQuery = ref('')
const quickSearchIdx = ref(0)
const quickSearchInputRef = ref<HTMLInputElement | null>(null)

const allSearchableNodes = computed(() => {
  const list: Array<{ type: string; title: string; desc: string; catLabel: string }> = []
  for (const cat of wf.catalogCategories.value) {
    for (const n of cat.nodes) {
      list.push({ type: n.type, title: n.title, desc: n.desc, catLabel: cat.label })
    }
  }
  list.push({ type: 'group', title: '📦 Group 分组框', desc: '框选并整理画布节点群组', catLabel: '🗂️ 画布组织工具' })
  return list
})

const filteredSearchNodes = computed(() => {
  const q = quickSearchQuery.value.trim().toLowerCase()
  if (!q) return allSearchableNodes.value.slice(0, 14)
  return allSearchableNodes.value
    .filter(n =>
      n.title.toLowerCase().includes(q)
      || n.type.toLowerCase().includes(q)
      || n.desc.toLowerCase().includes(q)
      || n.catLabel.toLowerCase().includes(q),
    )
    .slice(0, 14)
})

function onPaneDblClick(ev: MouseEvent | { event: MouseEvent }) {
  const mouseEv = 'event' in ev ? ev.event : ev
  const x = Math.min(window.innerWidth - 310, Math.max(12, mouseEv.clientX))
  const y = Math.min(window.innerHeight - 360, Math.max(48, mouseEv.clientY))
  quickSearch.value = {
    x,
    y,
    flowPos: screenToFlowCoordinate({ x: mouseEv.clientX, y: mouseEv.clientY }),
  }
  quickSearchQuery.value = ''
  quickSearchIdx.value = 0
  nextTick(() => quickSearchInputRef.value?.focus())
}

function pickQuickSearchNode(nodeType: string) {
  if (!quickSearch.value) return
  wf.addNode(nodeType, quickSearch.value.flowPos)
  quickSearch.value = null
}

function onQuickSearchKeydown(ev: KeyboardEvent) {
  const items = filteredSearchNodes.value
  if (ev.key === 'Escape') {
    quickSearch.value = null
  } else if (ev.key === 'ArrowDown') {
    ev.preventDefault()
    if (items.length) quickSearchIdx.value = (quickSearchIdx.value + 1) % items.length
  } else if (ev.key === 'ArrowUp') {
    ev.preventDefault()
    if (items.length) quickSearchIdx.value = (quickSearchIdx.value - 1 + items.length) % items.length
  } else if (ev.key === 'Enter') {
    ev.preventDefault()
    const target = items[quickSearchIdx.value] || items[0]
    if (target) pickQuickSearchNode(target.type)
  }
}

// ── 侧滑快速抽屉：细纲目录 & 快速阅读 ──────────────────────────────────────────────
const sideDrawer = ref<'none' | 'outline' | 'reader'>('none')
const drawerLoading = ref(false)
const outlineChapters = ref<Array<{ num: number; title: string; has_final?: boolean; has_draft?: boolean; has_outline?: boolean; chars?: number }>>([])
const detailedOutlineText = ref('')
const readerChapterText = ref('')
const readerError = ref('')

async function openSideDrawer(kind: 'outline' | 'reader') {
  if (sideDrawer.value === kind) {
    sideDrawer.value = 'none'
    return
  }
  sideDrawer.value = kind
  const fp = projectStore.activeProjectData?.filepath || ''
  if (!fp) return
  drawerLoading.value = true
  readerError.value = ''
  try {
    if (kind === 'outline') {
      const [dashRes, outRes] = await Promise.all([
        generateApi.dashboard(fp).catch(() => ({ data: { chapters: [] } })),
        generateApi.getDetailedOutline(fp).catch(() => ({ data: { content: '' } })),
      ])
      outlineChapters.value = dashRes.data?.chapters || []
      detailedOutlineText.value = outRes.data?.content || ''
    } else {
      const res = await generateApi.getChapter(wf.canvasChapterNum.value, fp)
      readerChapterText.value = res.data?.content || ''
    }
  } catch (e: unknown) {
    readerError.value = `第 ${wf.canvasChapterNum.value} 章暂无成稿（${(e as Error).message}）`
    readerChapterText.value = ''
  } finally {
    drawerLoading.value = false
  }
}

async function jumpToChapterAndRead(num: number) {
  wf.canvasChapterNum.value = num
  if (sideDrawer.value === 'reader') {
    sideDrawer.value = 'none'
    await openSideDrawer('reader')
  }
}

// 右键上下文菜单
const contextMenu = ref<{
  x: number
  y: number
  flowPos: { x: number; y: number }
  nodeId?: string
} | null>(null)

// Gate / Diff 审核弹窗
const gateEditedText = ref('')
watch(
  () => wf.pendingGate.value,
  (g) => {
    if (g) {
      gateEditedText.value = g.text_in || g.branch_a || ''
    }
  },
)

function showToast(msg: string) {
  toastMsg.value = msg
  setTimeout(() => { toastMsg.value = '' }, 2600)
}

onMounted(async () => {
  await wf.init()
  const qCh = Number(route.query.chapter)
  if (qCh >= 1) wf.canvasChapterNum.value = qCh
  const activeProj = projectStore.activeProjectData
  if (activeProj?.word_number) wf.canvasWordNumber.value = activeProj.word_number
  nextTick(() => fitView({ padding: 0.16 }))
})

watch(
  () => route.query.chapter,
  (val) => {
    const ch = Number(val)
    if (ch >= 1) wf.canvasChapterNum.value = ch
  },
)

const isCurrentDefault = computed(() => wf.defaultWorkflowId.value === wf.activeWorkflowId.value)
const isCurrentBuiltin = computed(() => wf.builtins.value.some(b => b.id === wf.activeWorkflowId.value))

function onSelectPreset(id: string) {
  const found = wf.allWorkflows.value.find(w => w.id === id)
  if (found) {
    wf.loadWorkflowIntoCanvas(found)
    nextTick(() => fitView({ padding: 0.16 }))
  }
}

function resolvePortInfo(nodeId: string, handleId: string | null | undefined, direction: 'in' | 'out') {
  const n = wf.nodes.value.find(x => x.id === nodeId)
  const meta = n ? wf.nodeMetaMap.value[n.data?.nodeType] : null
  if (!meta) return null
  const list = direction === 'out' ? meta.outputs : meta.inputs
  return list.find(p => p.id === handleId) || null
}

function isValidConnection(conn: Connection): boolean {
  if (!conn.source || !conn.target || conn.source === conn.target) return false
  const srcPort = resolvePortInfo(conn.source, conn.sourceHandle, 'out')
  const tgtPort = resolvePortInfo(conn.target, conn.targetHandle, 'in')
  if (!srcPort || !tgtPort) return false
  return srcPort.type === tgtPort.type
}

function handleConnect(conn: Connection) {
  if (!conn.source || !conn.target) return
  if (conn.source === conn.target) {
    showToast('⚠️ 不能把节点自己连给自己')
    return
  }
  const srcPort = resolvePortInfo(conn.source, conn.sourceHandle, 'out')
  const tgtPort = resolvePortInfo(conn.target, conn.targetHandle, 'in')
  if (srcPort && tgtPort && srcPort.type !== tgtPort.type) {
    const srcLabel = wf.portTypes.value[srcPort.type]?.label || srcPort.type
    const tgtLabel = wf.portTypes.value[tgtPort.type]?.label || tgtPort.type
    showToast(`❌ 端口类型不匹配：无法将「${srcLabel}」接入「${tgtLabel}」`)
    return
  }
  const color = srcPort ? (wf.portTypes.value[srcPort.type]?.color || '#94a3b8') : '#94a3b8'

  addEdges([{
    id: `e_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 5)}`,
    source: conn.source,
    sourceHandle: conn.sourceHandle || undefined,
    target: conn.target,
    targetHandle: conn.targetHandle || undefined,
    type: 'smoothstep',
    animated: false,
    style: { stroke: color, strokeWidth: 2.2 },
  }])
}

function onDragStartPalette(ev: DragEvent, nodeType: string) {
  if (ev.dataTransfer) {
    ev.dataTransfer.setData('application/novel-node-type', nodeType)
    ev.dataTransfer.effectAllowed = 'move'
  }
}

function loadJsonWorkflowFile(file: File) {
  const reader = new FileReader()
  reader.onload = () => {
    try {
      const parsed = JSON.parse(String(reader.result || '{}'))
      if (Array.isArray(parsed.nodes) && Array.isArray(parsed.edges)) {
        wf.loadWorkflowIntoCanvas({
          id: `custom_${Date.now().toString(36)}`,
          name: parsed.name || file.name.replace(/\.json$/i, ''),
          description: '导入的 JSON 工作流',
          builtin: false,
          nodes: parsed.nodes,
          edges: parsed.edges,
        })
        nextTick(() => fitView({ padding: 0.16 }))
        showToast('✅ 工作流 JSON 已拖入画布')
      } else {
        showToast('❌ JSON 格式不正确，缺少 nodes 或 edges 字段')
      }
    } catch (err) {
      showToast(`❌ 导入失败: ${(err as Error).message}`)
    }
  }
  reader.readAsText(file)
}

function onDropCanvas(ev: DragEvent) {
  const files = ev.dataTransfer?.files
  if (files && files.length > 0) {
    const jsonFile = Array.from(files).find(f => f.name.toLowerCase().endsWith('.json'))
    if (jsonFile) {
      ev.preventDefault()
      loadJsonWorkflowFile(jsonFile)
      return
    }
  }
  const nodeType = ev.dataTransfer?.getData('application/novel-node-type')
  if (!nodeType) return
  const pos = screenToFlowCoordinate({ x: ev.clientX, y: ev.clientY })
  wf.addNode(nodeType, pos)
}

function onPaneContextMenu(ev: MouseEvent) {
  ev.preventDefault()
  contextMenu.value = {
    x: ev.clientX,
    y: ev.clientY,
    flowPos: screenToFlowCoordinate({ x: ev.clientX, y: ev.clientY }),
  }
}

function onNodeContextMenu(ev: NodeMouseEvent) {
  ev.event.preventDefault()
  const raw = ev.event as MouseEvent | TouchEvent
  const pt = 'touches' in raw && raw.touches.length ? raw.touches[0] : (raw as MouseEvent)
  contextMenu.value = {
    x: pt.clientX ?? 200,
    y: pt.clientY ?? 200,
    flowPos: ev.node.position,
    nodeId: ev.node.id,
  }
}

function closeContextMenu() {
  contextMenu.value = null
  quickSearch.value = null
}

function handleAutoLayout() {
  wf.autoLayout()
  nextTick(() => fitView({ padding: 0.16 }))
}

function openSaveModal() {
  saveNameInput.value = isCurrentBuiltin.value
    ? `${wf.activeWorkflowName.value.replace(/^[^\u4e00-\u9fa5A-Za-z0-9]+/, '')} · 我的改版`
    : wf.activeWorkflowName.value
  saveModalOpen.value = true
}

async function confirmSaveWorkflow() {
  const saved = await wf.saveWorkflow(saveNameInput.value)
  saveModalOpen.value = false
  showToast(`✅ 已保存工作流「${saved.name}」`)
}

async function handleSetDefault() {
  if (isCurrentBuiltin.value && wf.activeWorkflowId.value !== 'standard_zh') {
    await wf.setAsDefaultWorkflow(wf.activeWorkflowId.value)
  } else if (!isCurrentBuiltin.value) {
    await wf.saveWorkflow()
    await wf.setAsDefaultWorkflow(wf.activeWorkflowId.value)
  } else {
    await wf.setAsDefaultWorkflow(wf.activeWorkflowId.value)
  }
  showToast('📌 已设为工单台默认执行链！')
}

function handleExportJson() {
  const payload = {
    name: wf.activeWorkflowName.value,
    nodes: wf.nodes.value,
    edges: wf.edges.value,
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${wf.activeWorkflowName.value.replace(/[^\u4e00-\u9fa5A-Za-z0-9_-]/g, '_')}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function handleImportJson(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0]
  if (!file) return
  loadJsonWorkflowFile(file)
}

// 节点全屏查看模态
const inspectedNode = computed(() =>
  wf.inspectedNodeId.value ? wf.nodes.value.find(n => n.id === wf.inspectedNodeId.value) : null,
)
const inspectedOutputs = computed(() =>
  wf.inspectedNodeId.value ? wf.nodeRuntime.value[wf.inspectedNodeId.value]?.outputs || {} : {},
)
</script>

<template>
  <div class="h-full flex flex-col bg-[#090a0d] text-zinc-200 overflow-hidden" @click="closeContextMenu">
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- 顶部极简暗黑工具栏                                                  -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <header class="shrink-0 bg-[#0e1014] border-b border-[#23262f] px-3 py-2 flex items-center justify-between flex-wrap gap-2 z-20">
      <!-- 左：模板切换与工作流管理 -->
      <div class="flex items-center gap-2 flex-wrap">
        <button
          @click="paletteOpen = !paletteOpen"
          type="button"
          class="px-2.5 py-1.5 rounded-lg bg-[#1b1e25] hover:bg-[#252934] border border-[#2c303b] text-xs font-semibold text-zinc-200 cursor-pointer"
        >
          {{ paletteOpen ? '◧ 收起节点库' : '◨ 打开节点库' }}
        </button>

        <select
          :value="wf.activeWorkflowId.value"
          @change="onSelectPreset(($event.target as HTMLSelectElement).value)"
          class="px-2.5 py-1.5 rounded-lg bg-[#090a0d] border border-[#2c303b] text-xs font-semibold text-zinc-100 max-w-[260px]"
        >
          <optgroup label="📦 官方预设模板">
            <option v-for="b in wf.builtins.value" :key="b.id" :value="b.id">{{ b.name }}</option>
          </optgroup>
          <optgroup v-if="wf.customs.value.length" label="⭐ 我的自定义工作流">
            <option v-for="c in wf.customs.value" :key="c.id" :value="c.id">★ {{ c.name }}</option>
          </optgroup>
        </select>

        <button
          @click="openSaveModal"
          type="button"
          class="px-2.5 py-1.5 rounded-lg bg-[#1b1e25] hover:bg-[#252934] border border-[#2c303b] text-xs font-medium text-zinc-200 cursor-pointer"
        >
          💾 保存
        </button>
        <button
          v-if="!isCurrentBuiltin"
          @click="wf.deleteCustom(wf.activeWorkflowId.value)"
          type="button"
          class="px-2 py-1.5 rounded-lg bg-red-950/50 hover:bg-red-900/60 border border-red-800/50 text-red-300 text-xs cursor-pointer"
        >
          🗑️
        </button>

        <button
          @click="handleSetDefault"
          type="button"
          class="px-2.5 py-1.5 rounded-lg border text-xs font-semibold cursor-pointer transition-colors"
          :class="isCurrentDefault
            ? 'bg-emerald-500/15 border-emerald-500/60 text-emerald-300'
            : 'bg-[#1b1e25] hover:bg-[#252934] border-[#2c303b] text-zinc-200'"
          title="设为此书籍写书工单台的默认执行工作流"
        >
          {{ isCurrentDefault ? '📌 已设为工单台默认' : '📌 设为工单台默认' }}
        </button>

        <button
          @click="handleAutoLayout"
          type="button"
          class="px-2.5 py-1.5 rounded-lg bg-[#1b1e25] hover:bg-[#252934] border border-[#2c303b] text-xs cursor-pointer"
        >
          🧹 自动排版
        </button>
        <button
          @click="fitView({ padding: 0.16 })"
          type="button"
          class="px-2.5 py-1.5 rounded-lg bg-[#1b1e25] hover:bg-[#252934] border border-[#2c303b] text-xs cursor-pointer"
        >
          ⌖ 居中
        </button>
        <button @click="handleExportJson" type="button" class="px-2 py-1.5 rounded-lg bg-[#1b1e25] hover:bg-[#252934] text-xs cursor-pointer" title="导出工作流 JSON">
          📤
        </button>
        <button @click="fileInputRef?.click()" type="button" class="px-2 py-1.5 rounded-lg bg-[#1b1e25] hover:bg-[#252934] text-xs cursor-pointer" title="导入或拖入工作流 JSON">
          📥
        </button>
        <input ref="fileInputRef" type="file" accept=".json" class="hidden" @change="handleImportJson" />
        <button
          @click="openSideDrawer('outline')"
          type="button"
          class="px-2.5 py-1.5 rounded-lg border text-xs font-medium cursor-pointer transition-colors"
          :class="sideDrawer === 'outline' ? 'bg-zinc-100 text-zinc-950 border-white font-bold' : 'bg-[#1b1e25] hover:bg-[#252934] border-[#2c303b] text-zinc-200'"
        >
          📑 细纲目录
        </button>
        <button
          @click="openSideDrawer('reader')"
          type="button"
          class="px-2.5 py-1.5 rounded-lg border text-xs font-medium cursor-pointer transition-colors"
          :class="sideDrawer === 'reader' ? 'bg-zinc-100 text-zinc-950 border-white font-bold' : 'bg-[#1b1e25] hover:bg-[#252934] border-[#2c303b] text-zinc-200'"
        >
          📖 快速阅读
        </button>
      </div>

      <!-- 右：章号 / 批量区间 / Queue Prompt 执行按钮 -->
      <div class="flex items-center gap-2 flex-wrap">
        <div class="flex items-center gap-1.5 bg-[#090a0d] border border-[#2c303b] rounded-lg px-2 py-1 text-xs">
          <span class="text-zinc-400">单章</span>
          <input
            v-model.number="wf.canvasChapterNum.value"
            type="number"
            min="1"
            class="w-12 !bg-transparent !border-0 text-center font-mono text-zinc-100 focus:outline-none"
          />
          <span class="text-zinc-700">|</span>
          <span class="text-zinc-400">批跑</span>
          <input v-model.number="wf.batchStart.value" type="number" min="1" class="w-11 !bg-transparent !border-0 text-center font-mono text-zinc-100 focus:outline-none" />
          <span class="text-zinc-500">-</span>
          <input v-model.number="wf.batchEnd.value" type="number" min="1" class="w-11 !bg-transparent !border-0 text-center font-mono text-zinc-100 focus:outline-none" />
        </div>

        <select
          v-model="wf.batchGatePolicy.value"
          class="px-2 py-1.5 rounded-lg bg-[#090a0d] border border-[#2c303b] text-[11px] text-zinc-200"
          title="批量跑多章时遇到「人工卡点 / A-B分支」的处理策略"
        >
          <option value="manual">卡点：单章必停 · 批量遇分支停</option>
          <option value="always_pause">卡点：批量也每章暂停等放行</option>
          <option value="auto_pass">卡点：批量自动放行（夜跑）</option>
        </select>

        <template v-if="!wf.isRunning.value">
          <button
            @click="wf.executeSingleChapter({ chapterNum: wf.canvasChapterNum.value })"
            type="button"
            class="px-3.5 py-1.5 rounded-lg bg-zinc-100 hover:bg-white text-zinc-950 text-xs font-bold border border-white cursor-pointer"
          >
            ▶ Queue Prompt (第 {{ wf.canvasChapterNum.value }} 章)
          </button>
          <button
            @click="wf.runBatchChapters(wf.batchStart.value, wf.batchEnd.value)"
            type="button"
            class="px-3 py-1.5 rounded-lg bg-[#242833] hover:bg-[#313645] border border-[#3a4052] text-zinc-100 text-xs font-bold cursor-pointer"
          >
            ⚡ 批量跑 {{ wf.batchStart.value }}-{{ wf.batchEnd.value }} 章
          </button>
        </template>
        <button
          v-else
          @click="wf.cancelActiveRun()"
          type="button"
          class="px-3.5 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-bold cursor-pointer animate-pulse"
        >
          ⏹️ 停止运行 ({{ wf.runElapsed.value }}s)
        </button>
      </div>
    </header>

    <!-- 提示与错误条 -->
    <div v-if="toastMsg" class="px-4 py-1.5 bg-emerald-950/70 border-b border-emerald-700/60 text-emerald-300 text-xs font-medium">
      {{ toastMsg }}
    </div>
    <div v-if="wf.runError.value" class="px-4 py-1.5 bg-red-950/70 border-b border-red-700/60 text-red-300 text-xs flex justify-between">
      <span>❌ {{ wf.runError.value }}</span>
      <button @click="wf.runError.value = ''" type="button" class="underline cursor-pointer">关闭</button>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- 主体：左侧节点组件库 + 中央 VueFlow 无限画布                         -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div class="flex-1 min-h-0 flex relative">
      <!-- 左：暗黑节点组件库 -->
      <aside
        v-if="paletteOpen"
        class="w-[248px] shrink-0 bg-[#0e1014] border-r border-[#23262f] overflow-y-auto p-3 space-y-4 select-none z-10"
      >
        <div class="text-[11px] text-zinc-400 leading-relaxed">
          点击或拖拽节点到右侧画布，再拖出彩色端口即可连线组装自定义生产链。
        </div>

        <div v-for="cat in wf.catalogCategories.value" :key="cat.id" class="space-y-1.5">
          <div class="text-xs font-bold text-zinc-200 px-1">{{ cat.label }}</div>
          <div
            v-for="item in cat.nodes"
            :key="item.type"
            draggable="true"
            @dragstart="onDragStartPalette($event, item.type)"
            @click="wf.addNode(item.type)"
            class="rounded-lg border border-[#262932] bg-[#15171c] hover:border-zinc-400 hover:bg-[#1c1f27] p-2 cursor-pointer transition-all"
          >
            <div class="text-xs font-bold text-zinc-100">{{ item.title }}</div>
            <div class="text-[10px] text-zinc-400 mt-0.5 line-clamp-2">{{ item.desc }}</div>
          </div>
        </div>

        <div class="space-y-1.5 pt-1 border-t border-[#23262f]">
          <div class="text-xs font-bold text-zinc-200 px-1">🗂️ 画布组织工具</div>
          <div
            draggable="true"
            @dragstart="onDragStartPalette($event, 'group')"
            @click="wf.addNode('group')"
            class="rounded-lg border border-dashed border-zinc-600 bg-zinc-800/30 hover:bg-zinc-800/60 p-2 cursor-pointer text-xs font-bold text-zinc-200"
          >
            📦 添加 Group 分组框
          </div>
        </div>

        <!-- 端口颜色图例 -->
        <div class="pt-2 border-t border-[#23262f] space-y-1">
          <div class="text-[11px] font-bold text-zinc-400">端口数据色标</div>
          <div class="grid grid-cols-2 gap-1 text-[10px] text-zinc-200">
            <div v-for="(pt, key) in wf.portTypes.value" :key="key" class="flex items-center gap-1.5">
              <span class="w-2.5 h-2.5 rounded-full shrink-0" :style="{ backgroundColor: pt.color }" />
              <span>{{ pt.label }}</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- 中央无限点阵画布（极简炭黑点阵 · 支持双击空白搜索节点 & 拖入 JSON） -->
      <div
        class="flex-1 min-w-0 h-full relative"
        @dragover.prevent
        @drop="onDropCanvas"
        @dblclick="(ev) => { if (!(ev.target as HTMLElement)?.closest('.vue-flow__node, .vue-flow__controls, .vue-flow__minimap, .quick-search-popup')) onPaneDblClick(ev) }"
      >
        <VueFlow
          v-model:nodes="wf.nodes.value"
          v-model:edges="wf.edges.value"
          :min-zoom="0.2"
          :max-zoom="2"
          :default-viewport="{ zoom: 0.85, x: 40, y: 40 }"
          :is-valid-connection="isValidConnection"
          @connect="handleConnect"
          @pane-context-menu="onPaneContextMenu"
          @node-context-menu="onNodeContextMenu"
          class="h-full w-full"
        >
          <Background variant="dots" :gap="22" :size="1.35" pattern-color="#22252e" />
          <Controls position="bottom-left" class="!bg-[#15171c] !border-[#262932]" />
          <MiniMap
            position="bottom-right"
            node-color="#323643"
            mask-color="rgba(8, 9, 11, 0.78)"
            class="!bg-[#0e1014] !border !border-[#262932] !rounded-xl"
          />

          <template #node-workflowNode="nodeProps">
            <WorkflowCustomNode :id="nodeProps.id" :data="nodeProps.data" />
          </template>

          <template #node-groupNode="nodeProps">
            <WorkflowGroupNode :id="nodeProps.id" :data="nodeProps.data" />
          </template>
        </VueFlow>

        <!-- 等待人工审核 / A-B 选择的画布浮层提醒条 -->
        <div
          v-if="wf.pendingGate.value"
          class="absolute top-3 left-1/2 -translate-x-1/2 z-30 px-4 py-2.5 rounded-xl bg-[#15171c]/95 border border-amber-500/70 shadow-2xl flex items-center gap-3 text-xs"
        >
          <span class="w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping" />
          <span class="font-bold text-zinc-100">
            {{ wf.pendingGate.value.node_type === 'ab_selector' ? '⚖️ 已暂停：等待 A/B 双分支对比择优' : '✋ 已暂停：等待人工审核放行卡点' }}
          </span>
          <button
            @click="wf.inspectedNodeId.value = wf.pendingGate.value.node_id"
            type="button"
            class="px-3 py-1 rounded-lg bg-zinc-100 hover:bg-white text-zinc-950 font-bold cursor-pointer"
          >
            立即审核对比
          </button>
        </div>

        <!-- 右键快捷菜单 -->
        <div
          v-if="contextMenu"
          :style="{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }"
          class="fixed z-50 w-52 rounded-xl border border-[#2c303b] bg-[#15171c] shadow-2xl py-1.5 text-xs text-zinc-200"
          @click.stop
        >
          <template v-if="contextMenu.nodeId">
            <button
              @click="wf.executeSingleChapter({ chapterNum: wf.canvasChapterNum.value, startFromNodeId: contextMenu.nodeId }); closeContextMenu()"
              type="button"
              class="w-full text-left px-3 py-1.5 hover:bg-emerald-500/20 text-emerald-300 cursor-pointer"
            >
              ▶ 从此节点重跑下游
            </button>
            <button
              @click="wf.toggleNodeBypass(contextMenu.nodeId); closeContextMenu()"
              type="button"
              class="w-full text-left px-3 py-1.5 hover:bg-[#1f222a] cursor-pointer"
            >
              ⏭️ 切换 Bypass 旁路
            </button>
            <button
              @click="wf.duplicateNode(contextMenu.nodeId); closeContextMenu()"
              type="button"
              class="w-full text-left px-3 py-1.5 hover:bg-[#1f222a] cursor-pointer"
            >
              📄 复制节点
            </button>
            <button
              @click="wf.deleteNode(contextMenu.nodeId); closeContextMenu()"
              type="button"
              class="w-full text-left px-3 py-1.5 hover:bg-red-500/20 text-red-300 cursor-pointer"
            >
              🗑️ 删除节点
            </button>
          </template>
          <template v-else>
            <div class="px-3 py-1 text-[10px] font-bold text-zinc-400 uppercase">在此处添加节点</div>
            <button
              v-for="quick in [
                ['character_profile', '🎭 人物关系与人设'],
                ['prev_excerpt_loader', '📖 前章尾段衔接'],
                ['rag_retriever', '🔍 RAG 知识库检索'],
                ['context_combiner', '🔀 上下文合流拼装'],
                ['pre_write_gate', '🚦 写前防吃书预检'],
                ['draft_writer', '✍️ AI 起草节点'],
                ['script_audit', '🧪 脚本去AI与字数质检'],
                ['deai_reviewer', '🛡️ 去AI味审校节点'],
                ['ending_hook_rewriter', '✂️ 章末断章钩子精修'],
                ['ab_selector', '🔀 A/B 双分支择优'],
                ['human_gate', '✋ 人工放行卡点'],
                ['group', '📦 Group 分组框'],
              ]"
              :key="quick[0]"
              @click="wf.addNode(quick[0], contextMenu.flowPos); closeContextMenu()"
              type="button"
              class="w-full text-left px-3 py-1.5 hover:bg-[#1f222a] cursor-pointer"
            >
              {{ quick[1] }}
            </button>
          </template>
        </div>

        <!-- 双击画布模糊搜索浮窗（ComfyUI Search Box） -->
        <div
          v-if="quickSearch"
          :style="{ left: `${quickSearch.x}px`, top: `${quickSearch.y}px` }"
          class="quick-search-popup fixed z-50 w-72 rounded-xl border border-zinc-600 bg-[#14161c] shadow-2xl overflow-hidden"
          @click.stop
        >
          <div class="p-2 border-b border-[#23262f] bg-[#0e1014]">
            <input
              ref="quickSearchInputRef"
              v-model="quickSearchQuery"
              @keydown="onQuickSearchKeydown"
              type="text"
              placeholder="🔍 输入节点名称 / 英文ID…"
              class="w-full px-2.5 py-1.5 rounded-lg bg-[#15171c] border border-[#2c303b] text-xs text-zinc-100 focus:outline-none focus:border-zinc-400"
            />
          </div>
          <div class="max-h-72 overflow-y-auto divide-y divide-[#1f222a]">
            <button
              v-for="(item, idx) in filteredSearchNodes"
              :key="item.type"
              @click="pickQuickSearchNode(item.type)"
              @mouseenter="quickSearchIdx = idx"
              type="button"
              class="w-full text-left px-3 py-2 text-xs cursor-pointer transition-colors"
              :class="idx === quickSearchIdx ? 'bg-[#232732] text-white' : 'text-zinc-300 hover:bg-[#1a1d24]'"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="font-bold">{{ item.title }}</span>
                <span class="text-[10px] font-mono text-zinc-500">{{ item.type }}</span>
              </div>
              <div class="text-[10px] text-zinc-400 truncate mt-0.5">{{ item.desc }}</div>
            </button>
            <div v-if="filteredSearchNodes.length === 0" class="px-3 py-4 text-center text-xs text-zinc-500">
              未找到匹配节点
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧停靠栏：细纲目录 / 快速阅读 侧滑抽屉 -->
      <aside
        v-if="sideDrawer !== 'none'"
        class="w-[380px] xl:w-[440px] shrink-0 bg-[#0e1014] border-l border-[#23262f] flex flex-col overflow-hidden z-20"
      >
        <div class="px-3.5 py-2.5 bg-[#15171c] border-b border-[#23262f] flex items-center justify-between">
          <div class="text-xs font-bold text-zinc-100">
            {{ sideDrawer === 'outline' ? '📑 章节目录与细纲（点击跳转目标章）' : `📖 第 ${wf.canvasChapterNum.value} 章快速阅读` }}
          </div>
          <button @click="sideDrawer = 'none'" type="button" class="text-xs text-zinc-400 hover:text-white cursor-pointer">
            收起 ✕
          </button>
        </div>

        <div v-if="drawerLoading" class="p-6 text-center text-xs text-zinc-400">正在加载…</div>

        <div v-else-if="sideDrawer === 'outline'" class="flex-1 overflow-y-auto p-3 space-y-3 text-xs">
          <div class="space-y-1">
            <div class="text-[11px] font-bold text-zinc-400 mb-1">全书章节工单列表（{{ outlineChapters.length }} 章）</div>
            <button
              v-for="ch in outlineChapters"
              :key="ch.num"
              @click="jumpToChapterAndRead(ch.num)"
              type="button"
              class="w-full text-left px-2.5 py-1.5 rounded-lg border transition-colors flex items-center justify-between gap-2 cursor-pointer"
              :class="wf.canvasChapterNum.value === ch.num
                ? 'bg-[#1f232c] border-zinc-400 text-zinc-100'
                : 'bg-[#15171c] border-[#23262f] text-zinc-300 hover:border-zinc-600'"
            >
              <span class="truncate">第{{ ch.num }}章 · {{ ch.title }}</span>
              <span
                class="text-[10px] shrink-0 px-1.5 py-0.5 rounded"
                :class="ch.has_final ? 'bg-emerald-500/20 text-emerald-300' : ch.has_draft ? 'bg-zinc-700 text-zinc-200' : 'bg-[#0e1014] text-zinc-500'"
              >
                {{ ch.has_final ? '定稿' : ch.has_draft ? '初稿' : '待写' }}
              </span>
            </button>
          </div>
          <div v-if="detailedOutlineText" class="pt-2 border-t border-[#23262f] space-y-1">
            <div class="text-[11px] font-bold text-zinc-400">全局细纲快照</div>
            <pre class="rounded-lg bg-[#131417] border border-[#23262f] p-2.5 text-[11px] whitespace-pre-wrap leading-relaxed text-[#d4d4d8]">{{ detailedOutlineText }}</pre>
          </div>
        </div>

        <div v-else class="flex-1 overflow-y-auto p-3.5 space-y-2">
          <div class="flex items-center justify-between text-[11px] text-zinc-400">
            <span>当前章节：第 {{ wf.canvasChapterNum.value }} 章</span>
            <div class="flex gap-1.5">
              <button
                @click="wf.canvasChapterNum.value = Math.max(1, wf.canvasChapterNum.value - 1); sideDrawer = 'none'; openSideDrawer('reader')"
                type="button"
                class="px-2 py-0.5 rounded bg-[#15171c] border border-[#262932] hover:border-zinc-500 cursor-pointer"
              >
                上一章
              </button>
              <button
                @click="wf.canvasChapterNum.value += 1; sideDrawer = 'none'; openSideDrawer('reader')"
                type="button"
                class="px-2 py-0.5 rounded bg-[#15171c] border border-[#262932] hover:border-zinc-500 cursor-pointer"
              >
                下一章
              </button>
            </div>
          </div>
          <div v-if="readerError" class="rounded-xl bg-[#15171c] border border-[#23262f] p-4 text-xs text-zinc-400">
            {{ readerError }}
          </div>
          <pre v-else class="rounded-xl border border-[#272a34] bg-[#131417] p-4 text-sm whitespace-pre-wrap leading-loose font-novel-prose text-[#d4d4d8]">{{ readerChapterText || '（暂无章节正文内容）' }}</pre>
        </div>
      </aside>

      <!-- 右侧停靠 Inspector（当未全屏放大时，停靠画布右侧实时验收） -->
      <aside
        v-if="inspectedNode && !inspectorFullscreen"
        class="w-[420px] xl:w-[460px] shrink-0 bg-[#15171c] border-l border-[#2c303b] flex flex-col overflow-hidden z-20"
      >
        <div class="px-3.5 py-2.5 bg-[#1b1e25] border-b border-[#272a34] flex items-center justify-between gap-2">
          <div class="font-bold text-xs text-zinc-100 truncate">
            🔍 {{ inspectedNode.data.label }}
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            <button
              @click="inspectorFullscreen = true"
              type="button"
              class="px-2 py-1 rounded bg-[#0e1014] border border-[#2c303b] text-[11px] text-zinc-200 cursor-pointer"
              title="放大为全屏 Diff 弹窗"
            >
              ⛶ 放大
            </button>
            <button
              @click="wf.inspectedNodeId.value = null; inspectorFullscreen = false"
              type="button"
              class="px-2 py-1 rounded bg-[#0e1014] border border-[#2c303b] text-[11px] text-zinc-300 cursor-pointer"
            >
              ✕
            </button>
          </div>
        </div>

        <div class="flex-1 overflow-y-auto p-3.5 space-y-3">
          <template v-if="inspectedNode.data.nodeType === 'ab_selector'">
            <DiffViewer
              :old-text="(wf.pendingGate.value?.branch_a || inspectedOutputs.branch_a || '')"
              :new-text="(wf.pendingGate.value?.branch_b || inspectedOutputs.branch_b || '')"
              old-label="🅰️ 分支 A"
              new-label="🅱️ 分支 B"
            />
            <div v-if="wf.pendingGate.value?.node_id === inspectedNode.id" class="flex flex-wrap justify-end gap-2 pt-2 border-t border-[#272a34]">
              <button @click="wf.submitGate({ action: 'cancel' }); wf.inspectedNodeId.value = null" type="button" class="px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-bold cursor-pointer">🛑 中止</button>
              <button @click="wf.submitGate({ action: 'approve', selected_branch: 'A' }); wf.inspectedNodeId.value = null" type="button" class="px-3 py-1.5 rounded-lg bg-zinc-100 text-zinc-950 text-xs font-bold cursor-pointer">🅰️ 选分支 A</button>
              <button @click="wf.submitGate({ action: 'approve', selected_branch: 'B' }); wf.inspectedNodeId.value = null" type="button" class="px-3 py-1.5 rounded-lg bg-emerald-500 text-zinc-950 text-xs font-bold cursor-pointer">🅱️ 选分支 B</button>
            </div>
          </template>

          <template v-else-if="inspectedNode.data.nodeType === 'human_gate'">
            <DiffViewer
              v-if="wf.pendingGate.value?.draft_text || inspectedOutputs.draft_text"
              :old-text="wf.pendingGate.value?.draft_text || inspectedOutputs.draft_text || ''"
              :new-text="wf.pendingGate.value?.text_in || inspectedOutputs.text_in || ''"
              :checklist="wf.pendingGate.value?.checklist || inspectedOutputs.checklist || ''"
            />
            <div v-if="wf.pendingGate.value?.node_id === inspectedNode.id" class="space-y-2.5 pt-2 border-t border-[#272a34]">
              <div class="text-xs font-bold text-zinc-200">微调后放行：</div>
              <textarea
                v-model="gateEditedText"
                rows="8"
                class="w-full rounded-xl border border-[#272a34] !bg-[#131417] p-2.5 text-xs leading-relaxed font-novel-prose !text-[#d4d4d8]"
              />
              <div class="flex justify-end gap-2">
                <button @click="wf.submitGate({ action: 'cancel' }); wf.inspectedNodeId.value = null" type="button" class="px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-bold cursor-pointer">🛑 拒绝</button>
                <button @click="wf.submitGate({ action: 'approve', edited_text: gateEditedText }); wf.inspectedNodeId.value = null" type="button" class="px-4 py-1.5 rounded-lg bg-emerald-500 text-zinc-950 text-xs font-bold cursor-pointer">✅ 确认放行</button>
              </div>
            </div>
          </template>

          <template v-else-if="inspectedOutputs.raw_input_text || (inspectedOutputs.text_a && inspectedOutputs.text_b)">
            <DiffViewer
              :old-text="inspectedOutputs.raw_input_text || inspectedOutputs.text_a || ''"
              :new-text="inspectedOutputs.polished_text || inspectedOutputs.text_out || inspectedOutputs.text_b || ''"
              :checklist="inspectedOutputs.checklist || ''"
            />
          </template>

          <template v-else>
            <pre class="rounded-xl border border-[#272a34] bg-[#131417] p-3.5 text-xs whitespace-pre-wrap leading-loose font-novel-prose text-[#d4d4d8]">{{
              inspectedOutputs.draft_text
              || inspectedOutputs.polished_text
              || inspectedOutputs.text_out
              || inspectedOutputs.final_text
              || inspectedOutputs.arch_text
              || inspectedOutputs.directory_text
              || inspectedOutputs.outline
              || inspectedOutputs.handoff
              || inspectedOutputs.context_bundle?.text
              || JSON.stringify(inspectedOutputs, null, 2)
            }}</pre>
          </template>
        </div>
      </aside>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- 底部可折叠运行控制台                                                -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <footer class="shrink-0 bg-[#0e1014] border-t border-[#23262f] text-xs z-20">
      <div class="px-3 py-1.5 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <button
            @click="logsDrawerOpen = !logsDrawerOpen"
            type="button"
            class="font-semibold text-zinc-200 hover:text-white cursor-pointer"
          >
            {{ logsDrawerOpen ? '▾ 收起执行控制台' : `▸ 执行控制台 (${wf.runLogs.value.length} 条日志)` }}
          </button>
          <span v-if="wf.isRunning.value" class="text-emerald-400 font-mono">
            ⚡ 正在执行第 {{ wf.canvasChapterNum.value }} 章 · {{ wf.runElapsed.value }}s
          </span>
          <span v-else-if="wf.runLogs.value.length" class="text-zinc-400 truncate max-w-xl">
            {{ wf.runLogs.value[wf.runLogs.value.length - 1] }}
          </span>
        </div>
        <span class="text-[11px] text-zinc-500">双击空白快速搜节点 · 拖入 .json 载入链 · 右键快捷菜单 · 点击端口拖线</span>
      </div>

      <div
        v-if="logsDrawerOpen"
        class="h-40 overflow-y-auto px-3 pb-2 font-mono text-[11px] text-zinc-300 bg-[#090a0d] border-t border-[#23262f] space-y-0.5"
      >
        <div v-for="(line, i) in wf.runLogs.value" :key="i">{{ line }}</div>
      </div>
    </footer>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- 保存自定义工作流弹窗                                                 -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div
      v-if="saveModalOpen"
      class="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4"
      @click.self="saveModalOpen = false"
    >
      <div class="w-full max-w-md rounded-2xl border border-[#2c303b] bg-[#15171c] p-5 space-y-4 shadow-2xl">
        <div class="text-base font-bold text-zinc-100">💾 保存自定义节点工作流</div>
        <input
          v-model="saveNameInput"
          type="text"
          placeholder="输入工作流名称…"
          class="w-full px-3 py-2 rounded-xl bg-[#090a0d] border border-[#2c303b] text-sm text-zinc-100"
        />
        <div class="flex justify-end gap-2">
          <button @click="saveModalOpen = false" type="button" class="px-3.5 py-1.5 rounded-lg bg-[#1d2028] border border-[#2c303b] text-xs text-zinc-200 cursor-pointer">
            取消
          </button>
          <button @click="confirmSaveWorkflow" type="button" class="px-4 py-1.5 rounded-lg bg-zinc-100 hover:bg-white text-zinc-950 text-xs font-bold cursor-pointer">
            确认保存
          </button>
        </div>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- 节点全屏预览 / Red-Green Diff / A-B 择优 / 人工放行弹窗              -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div
      v-if="inspectedNode && inspectorFullscreen"
      class="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
      @click.self="inspectorFullscreen = false"
    >
      <div class="w-full max-w-6xl max-h-[88vh] rounded-2xl border border-[#2c303b] bg-[#15171c] text-zinc-200 shadow-2xl flex flex-col overflow-hidden">
        <div class="px-4 py-3 bg-[#1b1e25] border-b border-[#272a34] flex items-center justify-between gap-3">
          <div class="font-bold text-sm text-zinc-100">
            🔍 {{ inspectedNode.data.label }} · 产出预览与交互验收
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="inspectorFullscreen = false"
              type="button"
              class="px-3 py-1 rounded-lg bg-[#0e1014] border border-[#272a34] text-xs font-semibold text-zinc-200 cursor-pointer"
            >
              ⊟ 停靠右侧
            </button>
            <button
              @click="wf.inspectedNodeId.value = null; inspectorFullscreen = false"
              type="button"
              class="px-3 py-1 rounded-lg bg-[#0e1014] border border-[#272a34] text-xs font-semibold text-zinc-200 cursor-pointer"
            >
              关闭 ✕
            </button>
          </div>
        </div>

        <div class="flex-1 overflow-y-auto p-4 space-y-4">
          <!-- 情况 A：A/B 对比择优节点（支持暂停交互决策） -->
          <template v-if="inspectedNode.data.nodeType === 'ab_selector'">
            <DiffViewer
              :old-text="(wf.pendingGate.value?.branch_a || inspectedOutputs.branch_a || '')"
              :new-text="(wf.pendingGate.value?.branch_b || inspectedOutputs.branch_b || '')"
              old-label="🅰️ 分支 A 正文"
              new-label="🅱️ 分支 B 正文"
            />
            <div v-if="wf.pendingGate.value?.node_id === inspectedNode.id" class="flex items-center justify-end gap-3 pt-2 border-t border-[#272a34]">
              <button
                @click="wf.submitGate({ action: 'cancel' }); wf.inspectedNodeId.value = null"
                type="button"
                class="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-bold cursor-pointer"
              >
                🛑 中止运行
              </button>
              <button
                @click="wf.submitGate({ action: 'approve', selected_branch: 'A' }); wf.inspectedNodeId.value = null"
                type="button"
                class="px-4 py-2 rounded-xl bg-zinc-100 hover:bg-white text-zinc-950 text-xs font-bold cursor-pointer"
              >
                🅰️ 采纳分支 A 并继续下游
              </button>
              <button
                @click="wf.submitGate({ action: 'approve', selected_branch: 'B' }); wf.inspectedNodeId.value = null"
                type="button"
                class="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 text-xs font-bold cursor-pointer"
              >
                🅱️ 采纳分支 B 并继续下游
              </button>
            </div>
          </template>

          <!-- 情况 B：人工审核放行卡点 -->
          <template v-else-if="inspectedNode.data.nodeType === 'human_gate'">
            <DiffViewer
              v-if="wf.pendingGate.value?.draft_text || inspectedOutputs.draft_text"
              :old-text="wf.pendingGate.value?.draft_text || inspectedOutputs.draft_text || ''"
              :new-text="wf.pendingGate.value?.text_in || inspectedOutputs.text_in || ''"
              :checklist="wf.pendingGate.value?.checklist || inspectedOutputs.checklist || ''"
            />
            <div v-if="wf.pendingGate.value?.node_id === inspectedNode.id" class="space-y-3 pt-2 border-t border-[#272a34]">
              <div class="text-xs font-bold text-zinc-200">可直接微调定稿后放行：</div>
              <textarea
                v-model="gateEditedText"
                rows="10"
                class="w-full rounded-xl border border-[#272a34] !bg-[#131417] p-3 text-sm leading-relaxed font-novel-prose !text-[#d4d4d8]"
              />
              <div class="flex justify-end gap-2">
                <button
                  @click="wf.submitGate({ action: 'cancel' }); wf.inspectedNodeId.value = null"
                  type="button"
                  class="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-bold cursor-pointer"
                >
                  🛑 拒绝放行（不写入记忆）
                </button>
                <button
                  @click="wf.submitGate({ action: 'approve', edited_text: gateEditedText }); wf.inspectedNodeId.value = null"
                  type="button"
                  class="px-5 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-zinc-950 text-xs font-bold cursor-pointer"
                >
                  ✅ 确认放行，继续保存与归档
                </button>
              </div>
            </div>
          </template>

          <!-- 情况 C：去AI审校 / 自定义改写 / Diff 对比节点 -->
          <template v-else-if="inspectedOutputs.raw_input_text || (inspectedOutputs.text_a && inspectedOutputs.text_b)">
            <DiffViewer
              :old-text="inspectedOutputs.raw_input_text || inspectedOutputs.text_a || ''"
              :new-text="inspectedOutputs.polished_text || inspectedOutputs.text_out || inspectedOutputs.text_b || ''"
              :checklist="inspectedOutputs.checklist || ''"
            />
          </template>

          <!-- 情况 D：通用纯文本产出展示 -->
          <template v-else>
            <pre class="rounded-xl border border-[#272a34] bg-[#131417] p-4 text-sm whitespace-pre-wrap leading-loose font-novel-prose text-[#d4d4d8]">{{
              inspectedOutputs.draft_text
              || inspectedOutputs.polished_text
              || inspectedOutputs.text_out
              || inspectedOutputs.final_text
              || inspectedOutputs.arch_text
              || inspectedOutputs.directory_text
              || inspectedOutputs.outline
              || inspectedOutputs.handoff
              || inspectedOutputs.context_bundle?.text
              || JSON.stringify(inspectedOutputs, null, 2)
            }}</pre>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
