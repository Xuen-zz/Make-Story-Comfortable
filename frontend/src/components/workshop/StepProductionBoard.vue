<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { generateApi } from '@/api/client'
import type { useWorkshopState } from '@/composables/useWorkshopState'
import { useWorkflowCanvas } from '@/composables/useWorkflowCanvas'
import type { DashboardChapterItem, WorkshopStage } from '@/components/workshop/WorkflowStepper.vue'
import DiffViewer from '@/components/workshop/DiffViewer.vue'

const props = defineProps<{
  state: ReturnType<typeof useWorkshopState>
  chapters: DashboardChapterItem[]
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'go-stage', stage: WorkshopStage): void
}>()

const router = useRouter()
const wf = useWorkflowCanvas()
const engineMode = ref<'standard' | 'canvas_default'>('standard')

// ── 强制当前工作台保持纯中文 4 步出稿流水线，并同步节点画布默认链 ────────────────────────
onMounted(async () => {
  if (props.state.pipelineMode.value !== 'fast_zh') {
    props.state.setPipelineMode('fast_zh')
  }
  await wf.init()
  if (wf.defaultWorkflowId.value && wf.defaultWorkflowId.value !== 'standard_zh') {
    engineMode.value = 'canvas_default'
  }
  loadChapterBundle(props.state.chapterNum.value)
})

// ── 批量队列参数 ────────────────────────────────────────────────────────────────
const overwriteCompleted = ref(false)
const listFilter = ref<'batch' | 'all' | 'done' | 'todo'>('batch')
const searchQuery = ref('')
const showDirectingOptions = ref(false)
const showLogsDrawer = ref(false)

// ── 选中工单的透明输入预览 & 产物缓存 ────────────────────────────────────────────
interface PreviewItem {
  label: string
  exists: boolean
  chars: number
  content: string
  data?: Record<string, unknown> | null
}

const contextLoading = ref(false)
const contextItems = ref<Record<string, PreviewItem>>({})
const blueprintInfo = ref<Record<string, string>>({})
const previewModal = ref<{ title: string; content: string } | null>(null)

const artifactsLoading = ref(false)
const artifactsData = ref({
  draft: '',
  polished: '',
  checklist: '',
  summary: '',
  character_state: '',
  has_draft: false,
  has_polished: false,
})
const editableFinal = ref('')
const savingFinal = ref(false)
const copiedTip = ref(false)
const outputTab = ref<'diff' | 'final' | 'draft' | 'memory'>('diff')

const selectedChapterNum = computed(() => props.state.chapterNum.value || 1)
const selectedChapterMeta = computed(() =>
  props.chapters.find(c => c.num === selectedChapterNum.value) || {
    num: selectedChapterNum.value,
    title: blueprintInfo.value?.chapter_title || `第 ${selectedChapterNum.value} 章`,
    has_draft: false,
    chars: 0,
    has_final: false,
    has_en: false,
    en_words: 0,
    has_outline: false,
  },
)

// 当前工单是否在流水线实时生产中
const isRunningThisChapter = computed(
  () => props.state.pipelineRunning.value && props.state.pipelineTargetChapter.value === selectedChapterNum.value,
)

// 如果正在运行本章，优先展示实时流式结果，否则展示磁盘持久化产物
const displayDraft = computed(() => {
  if (isRunningThisChapter.value && props.state.pipelineData.value.draft) {
    return props.state.pipelineData.value.draft
  }
  return artifactsData.value.draft || ''
})

const displayFinal = computed(() => {
  if (isRunningThisChapter.value && props.state.pipelineData.value.polished) {
    return props.state.pipelineData.value.polished
  }
  return artifactsData.value.polished || ''
})

const displayChecklist = computed(() => {
  if (isRunningThisChapter.value && props.state.pipelineData.value.checklist) {
    return props.state.pipelineData.value.checklist
  }
  return artifactsData.value.checklist || ''
})

watch(displayFinal, (val) => {
  editableFinal.value = val || ''
}, { immediate: true })

async function loadChapterBundle(chNum: number) {
  const fp = props.state.filepath.value
  if (!fp || !chNum) return
  contextLoading.value = true
  artifactsLoading.value = true
  try {
    const [ctxRes, artRes] = await Promise.all([
      generateApi.contextPreview(chNum, fp).catch(() => null),
      generateApi.getChapterArtifacts(chNum, fp).catch(() => null),
    ])
    if (ctxRes?.data) {
      contextItems.value = ctxRes.data.items || {}
      blueprintInfo.value = ctxRes.data.blueprint_info || {}
    }
    if (artRes?.data) {
      artifactsData.value = {
        draft: artRes.data.draft || '',
        polished: artRes.data.polished || '',
        checklist: artRes.data.checklist || '',
        summary: artRes.data.summary || '',
        character_state: artRes.data.character_state || '',
        has_draft: Boolean(artRes.data.has_draft),
        has_polished: Boolean(artRes.data.has_polished),
      }
      editableFinal.value = artRes.data.polished || ''
    }
    props.state.loadHandoff(chNum)
  } finally {
    contextLoading.value = false
    artifactsLoading.value = false
  }
}

watch(
  [() => props.state.chapterNum.value, () => props.state.filepath.value],
  ([ch]) => {
    if (ch) loadChapterBundle(ch)
  },
)

watch(
  () => props.state.pipelineRunning.value,
  (running, prev) => {
    if (prev && !running) {
      loadChapterBundle(selectedChapterNum.value)
      emit('refresh')
    }
  },
)

function selectChapter(num: number) {
  props.state.chapterNum.value = num
}

function openInWorkflowCanvas() {
  wf.canvasChapterNum.value = selectedChapterNum.value
  router.push({ path: '/', query: { chapter: String(selectedChapterNum.value) } })
}

async function handleRunSingle(num: number) {
  props.state.chapterNum.value = num
  if (engineMode.value === 'canvas_default' && wf.defaultWorkflow.value) {
    props.state.pipelineTerminalLogs.value.push(`[${new Date().toLocaleTimeString()}] 🔗 按画布默认工作流「${wf.defaultWorkflow.value.name}」执行第 ${num} 章…`)
    await wf.executeSingleChapter({
      chapterNum: num,
      graphOverride: { nodes: wf.defaultWorkflow.value.nodes, edges: wf.defaultWorkflow.value.edges },
      onEventLog: (line) => props.state.pipelineTerminalLogs.value.push(line),
    })
    await loadChapterBundle(num)
    emit('refresh')
    return
  }
  await props.state.doRunPipeline(num)
}

async function handleRunBatch() {
  const s = props.state.batchQueueStart.value
  const e = props.state.batchQueueEnd.value
  if (engineMode.value === 'canvas_default' && wf.defaultWorkflow.value) {
    props.state.batchQueueRunning.value = true
    for (let ch = s; ch <= e; ch++) {
      const exist = props.chapters.find(c => c.num === ch)
      if (!overwriteCompleted.value && exist?.has_final) {
        props.state.batchQueueStatusMap.value = { ...props.state.batchQueueStatusMap.value, [ch]: 'skipped' }
        continue
      }
      props.state.batchQueueCurrent.value = ch
      props.state.batchQueueStatusMap.value = { ...props.state.batchQueueStatusMap.value, [ch]: 'running' }
      const ok = await wf.executeSingleChapter({
        chapterNum: ch,
        graphOverride: { nodes: wf.defaultWorkflow.value.nodes, edges: wf.defaultWorkflow.value.edges },
        isBatch: true,
        onEventLog: (line) => props.state.pipelineTerminalLogs.value.push(line),
      })
      props.state.batchQueueStatusMap.value = { ...props.state.batchQueueStatusMap.value, [ch]: ok ? 'completed' : 'error' }
      if (!ok) break
    }
    props.state.batchQueueRunning.value = false
    await loadChapterBundle(selectedChapterNum.value)
    emit('refresh')
    return
  }
  await props.state.doRunBatchQueue(s, e, overwriteCompleted.value)
}

async function handleSaveFinalText() {
  if (!editableFinal.value.trim()) return
  savingFinal.value = true
  try {
    await generateApi.saveChapter(selectedChapterNum.value, editableFinal.value, props.state.filepath.value)
    artifactsData.value.polished = editableFinal.value
    props.state.saveMsg.value = `✅ 第 ${selectedChapterNum.value} 章定稿已保存`
    setTimeout(() => { props.state.saveMsg.value = '' }, 2500)
    emit('refresh')
  } catch (e: unknown) {
    props.state.saveMsg.value = `❌ 保存失败: ${(e as Error).message}`
  } finally {
    savingFinal.value = false
  }
}

async function handleCopyFinal() {
  const txt = editableFinal.value || displayDraft.value
  if (!txt) return
  try {
    await navigator.clipboard.writeText(txt)
    copiedTip.value = true
    setTimeout(() => { copiedTip.value = false }, 1800)
  } catch { /* ignore */ }
}

// ── 左侧工单列表过滤 ────────────────────────────────────────────────────────────
const filteredChapters = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  const qStart = props.state.batchQueueStart.value || 1
  const qEnd = props.state.batchQueueEnd.value || 10

  // 确保 batch 区间内的章节即使还没出现在磁盘也可见
  const map = new Map<number, DashboardChapterItem>()
  for (const c of props.chapters) map.set(c.num, c)
  for (let n = qStart; n <= qEnd; n++) {
    if (!map.has(n)) {
      map.set(n, {
        num: n,
        title: `第 ${n} 章`,
        has_draft: false,
        chars: 0,
        has_final: false,
        has_en: false,
        en_words: 0,
        has_outline: false,
      })
    }
  }
  let list = Array.from(map.values()).sort((a, b) => a.num - b.num)

  if (listFilter.value === 'batch') {
    list = list.filter(c => c.num >= qStart && c.num <= qEnd)
  } else if (listFilter.value === 'done') {
    list = list.filter(c => c.has_final)
  } else if (listFilter.value === 'todo') {
    list = list.filter(c => !c.has_final)
  }

  if (q) {
    list = list.filter(c =>
      String(c.num).includes(q) || (c.title || '').toLowerCase().includes(q),
    )
  }
  return list
})

const batchProgressSummary = computed(() => {
  const map = props.state.batchQueueStatusMap.value
  const keys = Object.keys(map).map(Number)
  if (!keys.length) return null
  const total = keys.length
  const done = keys.filter(k => map[k] === 'completed' || map[k] === 'skipped').length
  const err = keys.filter(k => map[k] === 'error').length
  return { total, done, err, pct: Math.round((done / total) * 100) }
})

const visibleStages = computed(() => props.state.pipelineStages.value.slice(0, 4))

// 透明化输入条目配置（4 个可控开关 + 3 个固定基准）
const toggleableDeps = [
  { key: 'global_summary', toggleKey: 'summary' as const, title: '前文全局摘要' },
  { key: 'character_state', toggleKey: 'charState' as const, title: '角色能力状态表' },
  { key: 'world_building', toggleKey: 'worldBuilding' as const, title: '世界观与设定' },
  { key: 'canon_history', toggleKey: 'canon' as const, title: '已发生正史约束' },
]

function openDepPreview(key: string, fallbackTitle: string) {
  const item = contextItems.value[key]
  previewModal.value = {
    title: item?.label || fallbackTitle,
    content: item?.content?.trim() ? item.content : '（当前尚无此项记忆或设定内容）',
  }
}

function getTicketStatusBadge(ch: DashboardChapterItem) {
  const qStatus = props.state.batchQueueStatusMap.value[ch.num]
  if (qStatus === 'running' || (props.state.pipelineRunning.value && props.state.pipelineTargetChapter.value === ch.num)) {
    return { text: '生产中 ⚡', cls: 'bg-amber-100 text-amber-800 border-amber-300 animate-pulse' }
  }
  if (qStatus === 'error') return { text: '出错', cls: 'bg-rose-100 text-rose-800 border-rose-200' }
  if (qStatus === 'pending') return { text: '排队中', cls: 'bg-sky-50 text-sky-700 border-sky-200' }
  if (ch.has_final) return { text: '定稿 ✓', cls: 'bg-emerald-100 text-emerald-800 border-emerald-200' }
  if (ch.has_draft) return { text: '仅初稿', cls: 'bg-amber-50 text-amber-800 border-amber-200' }
  if (ch.has_outline) return { text: '待写', cls: 'bg-stone-100 text-stone-700 border-stone-200' }
  return { text: '缺细纲', cls: 'bg-stone-50 text-stone-500 border-stone-200' }
}
</script>

<template>
  <div class="space-y-4">
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- 顶部批量队列总控条                                                  -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div class="rounded-2xl border border-[var(--color-parchment-darker)] bg-white p-3.5 sm:p-4 shadow-xs space-y-3">
      <div class="flex items-center justify-between flex-wrap gap-3">
        <div class="flex items-center gap-3 flex-wrap text-xs">
          <div class="flex items-center gap-1.5 font-bold text-[var(--color-ink)] text-sm">
            <span>🏭 批量写审队列：</span>
          </div>
          <div class="flex items-center gap-1.5">
            <span>第</span>
            <input
              v-model.number="state.batchQueueStart.value"
              :disabled="state.batchQueueRunning.value"
              type="number"
              min="1"
              :max="state.numChapters.value"
              class="w-16 px-2 py-1 rounded-lg border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/30 text-center font-mono"
            />
            <span>至</span>
            <input
              v-model.number="state.batchQueueEnd.value"
              :disabled="state.batchQueueRunning.value"
              type="number"
              min="1"
              :max="state.numChapters.value"
              class="w-16 px-2 py-1 rounded-lg border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/30 text-center font-mono"
            />
            <span>章</span>
          </div>

          <!-- 审校强度切换（核心用户需求） -->
          <div class="flex items-center gap-1.5 pl-1">
            <span class="font-medium text-[var(--color-ink-light)]">🛡️ 去AI审校：</span>
            <div class="inline-flex rounded-lg border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/40 p-0.5">
              <button
                @click="state.setReviewStrength('strong')"
                type="button"
                class="px-2.5 py-1 rounded-md text-[11px] font-semibold cursor-pointer transition-colors"
                :class="state.pipelineReviewStrength.value === 'strong'
                  ? 'bg-[var(--color-leather)] text-white shadow-2xs'
                  : 'text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
              >
                🔥 强力去AI味
              </button>
              <button
                @click="state.setReviewStrength('light')"
                type="button"
                class="px-2.5 py-1 rounded-md text-[11px] font-semibold cursor-pointer transition-colors"
                :class="state.pipelineReviewStrength.value === 'light'
                  ? 'bg-[var(--color-leather)] text-white shadow-2xs'
                  : 'text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
              >
                🍃 轻度润色
              </button>
            </div>
          </div>

          <label class="flex items-center gap-1.5 cursor-pointer select-none text-[var(--color-ink-light)]">
            <input v-model="overwriteCompleted" type="checkbox" class="rounded accent-[var(--color-leather)]" />
            <span>重跑已定稿章节</span>
          </label>

          <div class="flex items-center gap-1.5">
            <span class="font-medium text-[var(--color-ink-light)]">🔗 执行链路：</span>
            <select
              v-model="engineMode"
              class="px-2 py-1 rounded-lg border border-[var(--color-parchment-darker)] bg-white text-[11px] font-medium text-[var(--color-ink)] max-w-[200px]"
            >
              <option value="standard">标准 4 步写审流水线</option>
              <option value="canvas_default">
                画布默认链：{{ wf.defaultWorkflow.value?.name || '自定义工作流' }}
              </option>
            </select>
          </div>
        </div>

        <!-- 批量执行按钮组 -->
        <div class="flex items-center gap-2 flex-wrap">
          <button
            v-if="!state.batchQueueRunning.value"
            @click="handleRunBatch()"
            :disabled="state.pipelineRunning.value || wf.isRunning.value"
            type="button"
            class="btn-primary text-xs sm:text-sm"
          >
            🚀 开始批量生产（第 {{ state.batchQueueStart.value }}-{{ state.batchQueueEnd.value }} 章）
          </button>

          <template v-else>
            <button
              @click="state.togglePauseBatchQueue()"
              type="button"
              class="px-3.5 py-2 rounded-xl border border-amber-400 bg-amber-50 hover:bg-amber-100 text-amber-900 text-xs font-bold cursor-pointer"
            >
              {{ state.batchQueuePaused.value ? '▶️ 继续队列' : '⏸️ 暂停队列' }}
            </button>
            <button
              @click="state.stopBatchQueue()"
              type="button"
              class="px-3.5 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold cursor-pointer"
            >
              🛑 停止全部
            </button>
          </template>
        </div>
      </div>

      <!-- 批量队列进度条 -->
      <div
        v-if="batchProgressSummary"
        class="rounded-xl bg-[var(--color-parchment)]/55 border border-[var(--color-parchment-darker)] px-3 py-2 flex items-center gap-3 text-xs"
      >
        <span class="font-semibold text-[var(--color-ink)] whitespace-nowrap">
          {{ state.batchQueueRunning.value
            ? (state.batchQueuePaused.value ? '⏸️ 队列已暂停' : `⚡ 正在生产第 ${state.batchQueueCurrent.value} 章`)
            : '📋 本批队列状态' }}
        </span>
        <div class="flex-1 h-2 bg-white rounded-full overflow-hidden border border-[var(--color-parchment-darker)]">
          <div
            class="h-full bg-emerald-600 transition-all duration-300"
            :style="{ width: `${batchProgressSummary.pct}%` }"
          />
        </div>
        <span class="font-mono font-semibold text-[var(--color-ink)] whitespace-nowrap">
          {{ batchProgressSummary.done }} / {{ batchProgressSummary.total }} 章
          <span v-if="batchProgressSummary.err > 0" class="text-rose-600 ml-1">({{ batchProgressSummary.err }} 异常)</span>
        </span>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- 双栏工单主体：左章列工单队列 + 右单章透明工单卡（输入 -> 处理 -> 输出） -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div class="flex flex-col lg:flex-row gap-4 items-start">
      <!-- 左栏：章节工单队列 -->
      <aside class="w-full lg:w-[300px] shrink-0 rounded-2xl border border-[var(--color-parchment-darker)] bg-white shadow-xs overflow-hidden">
        <div class="p-3 border-b border-[var(--color-parchment-dark)] space-y-2 bg-[var(--color-parchment)]/45">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-[var(--color-ink)]">📑 章节工单队列</span>
            <button
              @click="emit('refresh')"
              :disabled="loading"
              type="button"
              class="text-[11px] text-zinc-200 hover:text-white hover:underline cursor-pointer"
            >
              {{ loading ? '刷新中…' : '🔄 刷新' }}
            </button>
          </div>

          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索章号或标题…"
            class="w-full px-2.5 py-1.5 rounded-lg border border-[var(--color-parchment-darker)] bg-white text-xs"
          />

          <div class="grid grid-cols-4 gap-1 text-[11px]">
            <button
              v-for="tab in ([
                { id: 'batch', label: '本批' },
                { id: 'all', label: '全部' },
                { id: 'todo', label: '待写' },
                { id: 'done', label: '定稿' },
              ] as const)"
              :key="tab.id"
              @click="listFilter = tab.id"
              type="button"
              class="py-1 rounded-md font-medium cursor-pointer transition-colors"
              :class="listFilter === tab.id
                ? 'bg-[var(--color-leather)] text-white'
                : 'bg-white text-[var(--color-ink-light)] hover:bg-[var(--color-parchment)]'"
            >
              {{ tab.label }}
            </button>
          </div>
        </div>

        <div class="max-h-[72vh] overflow-y-auto divide-y divide-[var(--color-parchment-dark)]">
          <div
            v-for="ch in filteredChapters"
            :key="ch.num"
            @click="selectChapter(ch.num)"
            class="px-3 py-2.5 cursor-pointer transition-colors flex items-center justify-between gap-2 group"
            :class="selectedChapterNum === ch.num
              ? 'bg-[#1f222a] border-l-4 border-l-zinc-200'
              : 'hover:bg-[var(--color-parchment-dark)]/70'"
          >
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5">
                <span class="text-xs font-bold font-mono text-[var(--color-ink)] shrink-0">第{{ ch.num }}章</span>
                <span class="text-xs text-[var(--color-ink)] truncate">{{ ch.title.replace(/^第\s*\d+\s*章[：:\s\-—]*/, '') }}</span>
              </div>
              <div class="flex items-center gap-2 mt-1 text-[10px] text-[var(--color-ink-light)]">
                <span
                  class="px-1.5 py-0.2 rounded border font-medium"
                  :class="getTicketStatusBadge(ch).cls"
                >
                  {{ getTicketStatusBadge(ch).text }}
                </span>
                <span v-if="ch.chars > 0" class="font-mono">{{ ch.chars }} 字</span>
              </div>
            </div>

            <button
              @click.stop="handleRunSingle(ch.num)"
              :disabled="state.pipelineRunning.value"
              type="button"
              title="立即单章写审"
              class="opacity-75 group-hover:opacity-100 px-2 py-1 rounded-lg bg-[var(--color-parchment)] hover:bg-[var(--color-leather)] hover:text-white text-[11px] font-bold border border-[var(--color-parchment-darker)] disabled:opacity-30 cursor-pointer transition-colors shrink-0"
            >
              ▶
            </button>
          </div>

          <div v-if="filteredChapters.length === 0" class="py-10 text-center text-xs text-[var(--color-ink-light)]">
            当前筛选条件下暂无章节
          </div>
        </div>
      </aside>

      <!-- 右栏：当前选中章节工单详情（输入 -> 处理 -> 输出） -->
      <section class="flex-1 min-w-0 space-y-4 w-full">
        <!-- 工单头 -->
        <div class="rounded-2xl border border-[var(--color-parchment-darker)] bg-white p-4 shadow-xs flex items-center justify-between flex-wrap gap-3">
          <div class="min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="px-2.5 py-0.5 rounded-lg bg-[var(--color-leather)] text-white text-xs font-mono font-bold">
                工单 #{{ selectedChapterNum }}
              </span>
              <h3 class="text-base sm:text-lg font-bold text-[var(--color-ink)] truncate">
                {{ selectedChapterMeta.title }}
              </h3>
              <span class="text-xs text-[var(--color-ink-light)] font-mono">
                目标约 {{ state.wordNumber.value }} 字
              </span>
            </div>
            <p class="text-xs text-[var(--color-ink-light)] mt-1">
              流程透明追踪：检查下方依赖设定 ➔ 启动 3.8 Flash 起草与 4 Hydrogen 去AI审校 ➔ 红绿对比验货并保存。
            </p>
          </div>

          <div class="flex items-center gap-2 flex-wrap">
            <button
              @click="openInWorkflowCanvas()"
              type="button"
              class="px-3 py-1.5 rounded-lg border border-[#2f333f] bg-[#1b1e25] hover:bg-[#252934] text-emerald-400 text-xs font-semibold cursor-pointer transition-colors"
              title="带着当前章号跳转至 ComfyUI 节点工作流画布进行深度调参或分支对比"
            >
              🔗 在节点画布中调试本章
            </button>
            <button
              v-if="selectedChapterNum > 1"
              @click="state.openQuickReader(selectedChapterNum - 1)"
              type="button"
              class="px-3 py-1.5 rounded-lg border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/50 hover:bg-[var(--color-parchment)] text-xs font-medium cursor-pointer"
            >
              📖 速览第 {{ selectedChapterNum - 1 }} 章
            </button>
            <button
              v-if="!state.pipelineRunning.value && !wf.isRunning.value"
              @click="handleRunSingle(selectedChapterNum)"
              type="button"
              class="btn-primary text-xs sm:text-sm"
            >
              ⚡ 单章写审第 {{ selectedChapterNum }} 章
            </button>
            <button
              v-else
              @click="state.cancelPipeline(); wf.cancelActiveRun()"
              type="button"
              class="px-3.5 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold cursor-pointer"
            >
              ⏹️ 终止当前运行
            </button>
          </div>
        </div>

        <!-- ── 区块 1：📥 输入依赖（透明可勾选） ── -->
        <div class="rounded-2xl border border-[var(--color-parchment-darker)] bg-white p-4 shadow-xs space-y-3">
          <div class="flex items-center justify-between flex-wrap gap-2">
            <div class="flex items-center gap-2">
              <span class="text-sm font-bold text-[var(--color-ink)]">📥 一、输入依赖（写本章前喂给 AI 的资料）</span>
              <span v-if="contextLoading" class="text-[11px] text-[var(--color-ink-light)]">加载中…</span>
            </div>
            <button
              @click="showDirectingOptions = !showDirectingOptions"
              type="button"
              class="text-xs text-zinc-200 hover:text-white font-medium hover:underline cursor-pointer"
            >
              {{ showDirectingOptions ? '收起导演指令与文风设置 ▴' : '展开导演指令 / 文风 / 分场景设置 ▾' }}
            </button>
          </div>

          <!-- 固定核心依赖 + 4 个可控开关 -->
          <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-2.5 text-xs">
            <!-- 本章细纲 -->
            <div
              class="rounded-xl border p-2.5 flex flex-col justify-between gap-1.5"
              :class="contextItems.outline?.exists ? 'border-emerald-200 bg-emerald-50/35' : 'border-amber-300 bg-amber-50/60'"
            >
              <div class="flex items-center justify-between">
                <span class="font-bold text-[var(--color-ink)]">📑 本章细纲</span>
                <span class="font-mono text-[11px]" :class="contextItems.outline?.exists ? 'text-emerald-700' : 'text-amber-700'">
                  {{ contextItems.outline?.exists ? `${contextItems.outline.chars} 字` : '未规划（将自动补全）' }}
                </span>
              </div>
              <div class="flex items-center justify-between text-[11px]">
                <button
                  @click="openDepPreview('outline', '本章细纲')"
                  type="button"
                  class="text-zinc-200 hover:text-white hover:underline cursor-pointer"
                >
                  预览细纲
                </button>
                <button
                  @click="emit('go-stage', 'stage3')"
                  type="button"
                  class="text-stone-600 hover:text-[var(--color-ink)] hover:underline cursor-pointer"
                >
                  去第3步修改 ➔
                </button>
              </div>
            </div>

            <!-- 上章交接 Handoff -->
            <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/35 p-2.5 flex flex-col justify-between gap-1.5">
              <div class="flex items-center justify-between">
                <span class="font-bold text-[var(--color-ink)]">🔗 上章交接契约</span>
                <span class="font-mono text-[11px] text-[var(--color-ink-light)]">
                  {{ selectedChapterNum === 1 ? '首章无需' : (contextItems.handoff?.exists ? `${contextItems.handoff.chars} 字` : '暂无') }}
                </span>
              </div>
              <div class="flex items-center justify-between text-[11px]">
                <span class="text-[var(--color-ink-light)]">防断片与开篇禁令</span>
                <button
                  v-if="selectedChapterNum > 1"
                  @click="openDepPreview('handoff', '上章因果交接 (Handoff)')"
                  type="button"
                  class="text-zinc-200 hover:text-white hover:underline cursor-pointer"
                >
                  预览交接
                </button>
              </div>
            </div>

            <!-- 可勾选的 4 项记忆依赖 -->
            <div
              v-for="dep in toggleableDeps"
              :key="dep.key"
              class="rounded-xl border p-2.5 flex flex-col justify-between gap-1.5 transition-colors"
              :class="state.pipelineContextToggles.value[dep.toggleKey]
                ? 'border-[var(--color-parchment-darker)] bg-white'
                : 'border-dashed border-stone-300 bg-stone-50/60 opacity-70'"
            >
              <label class="flex items-center justify-between cursor-pointer select-none">
                <span class="flex items-center gap-1.5 font-bold text-[var(--color-ink)]">
                  <input
                    v-model="state.pipelineContextToggles.value[dep.toggleKey]"
                    type="checkbox"
                    class="rounded accent-[var(--color-leather)]"
                  />
                  <span>{{ dep.title }}</span>
                </span>
                <span class="font-mono text-[11px] text-[var(--color-ink-light)]">
                  {{ contextItems[dep.key]?.exists ? `${contextItems[dep.key].chars} 字` : '空' }}
                </span>
              </label>
              <div class="flex items-center justify-between text-[11px]">
                <span class="text-[var(--color-ink-light)]">
                  {{ state.pipelineContextToggles.value[dep.toggleKey] ? '本次注入' : '本次跳过' }}
                </span>
                <button
                  @click="openDepPreview(dep.key, dep.title)"
                  type="button"
                  class="text-zinc-200 hover:text-white hover:underline cursor-pointer"
                >
                  预览全文
                </button>
              </div>
            </div>
          </div>

          <!-- 可折叠：导演补充指令与文风 -->
          <div
            v-if="showDirectingOptions"
            class="rounded-xl border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/35 p-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs"
          >
            <div class="md:col-span-2">
              <label class="block font-semibold text-[var(--color-ink)] mb-1">🎬 本章导演特别指令（可选，覆盖/补充细纲节奏）</label>
              <textarea
                v-model="state.chGuidance.value"
                rows="2"
                placeholder="例如：本章重点写主角当众打脸退婚，对话要短促嚣张，章末留下一封神秘黑卡的钩子..."
                class="w-full rounded-lg border border-[var(--color-parchment-darker)] bg-white p-2 text-xs"
              />
            </div>
            <div>
              <label class="block font-semibold text-[var(--color-ink)] mb-1">🎨 章节文风 DNA</label>
              <select v-model="state.chStyle.value" class="w-full rounded-lg border border-[var(--color-parchment-darker)] bg-white px-2.5 py-1.5 text-xs">
                <option value="">不使用文风</option>
                <option v-for="s in state.styleList.value" :key="s" :value="s">{{ s }}</option>
              </select>
            </div>
            <div class="flex items-end gap-4 pb-1">
              <label class="flex items-center gap-1.5 cursor-pointer select-none">
                <input v-model="state.sceneByScene.value" type="checkbox" class="rounded accent-[var(--color-leather)]" />
                <span>开启分场景渐进扩写（字数更扎实）</span>
              </label>
            </div>
          </div>
        </div>

        <!-- ── 区块 2：⚙️ 实时处理（4 阶段流水线追踪） ── -->
        <div class="rounded-2xl border border-[var(--color-parchment-darker)] bg-white p-4 shadow-xs space-y-3">
          <div class="flex items-center justify-between flex-wrap gap-2">
            <div class="flex items-center gap-2">
              <span class="text-sm font-bold text-[var(--color-ink)]">⚙️ 二、实时处理进度</span>
              <span
                v-if="state.pipelineRunning.value"
                class="px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 text-[11px] font-semibold animate-pulse"
              >
                第 {{ state.pipelineTargetChapter.value }} 章运行中 · {{ state.pipelineElapsed.value }}s
              </span>
              <span v-else-if="state.pipelineStatusMsg.value" class="text-xs text-[var(--color-ink-light)]">
                {{ state.pipelineStatusMsg.value }}
              </span>
            </div>

            <button
              @click="showLogsDrawer = !showLogsDrawer"
              type="button"
              class="text-xs text-zinc-200 hover:text-white hover:underline cursor-pointer"
            >
              {{ showLogsDrawer ? '收起实时日志 ▴' : `查看运行日志 (${state.pipelineTerminalLogs.value.length}) ▾` }}
            </button>
          </div>

          <!-- 4 阶段暖纸风卡片条 -->
          <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-2.5">
            <div
              v-for="st in visibleStages"
              :key="st.id"
              class="rounded-xl border p-2.5 space-y-1.5 transition-all"
              :class="
                st.status === 'running'
                  ? 'border-amber-400 bg-amber-50/70 shadow-2xs'
                  : st.status === 'completed'
                    ? 'border-emerald-200 bg-emerald-50/45'
                    : st.status === 'error'
                      ? 'border-rose-300 bg-rose-50/60'
                      : 'border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/30'
              "
            >
              <div class="flex items-center justify-between gap-1 text-xs">
                <span class="font-bold text-[var(--color-ink)] truncate">{{ st.icon }} {{ st.id }}. {{ st.name }}</span>
                <span class="font-mono text-[10px] shrink-0">
                  {{ st.status === 'completed' ? '✓' : st.status === 'running' ? `${Math.round(st.progress)}%` : st.status === 'error' ? '✕' : '待命' }}
                </span>
              </div>
              <div class="h-1.5 rounded-full bg-white/80 overflow-hidden border border-black/5">
                <div
                  class="h-full transition-all duration-300"
                  :class="st.status === 'error' ? 'bg-rose-500' : st.status === 'completed' ? 'bg-emerald-600' : 'bg-amber-600'"
                  :style="{ width: `${st.status === 'completed' ? 100 : st.progress}%` }"
                />
              </div>
              <div class="text-[11px] text-[var(--color-ink-light)] truncate">
                {{ st.message || st.subtitle }}
              </div>
            </div>
          </div>

          <!-- 可折叠纯暖纸风日志 -->
          <div
            v-if="showLogsDrawer"
            class="rounded-xl border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/50 p-3 max-h-48 overflow-y-auto font-mono text-[11px] text-[var(--color-ink)] space-y-0.5"
          >
            <div v-if="state.pipelineTerminalLogs.value.length === 0" class="text-[var(--color-ink-light)]">
              暂无运行日志，启动单章或批量队列后将在此实时滚动记录。
            </div>
            <div v-for="(line, idx) in state.pipelineTerminalLogs.value" :key="idx">{{ line }}</div>
          </div>
        </div>

        <!-- ── 区块 3：📤 输出交付与红绿对比 ── -->
        <div class="rounded-2xl border border-[var(--color-parchment-darker)] bg-white p-4 shadow-xs space-y-3">
          <div class="flex items-center justify-between flex-wrap gap-2 border-b border-[var(--color-parchment-dark)] pb-2.5">
            <div class="flex items-center gap-1.5 flex-wrap">
              <button
                @click="outputTab = 'diff'"
                type="button"
                class="px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors"
                :class="outputTab === 'diff'
                  ? 'bg-[var(--color-leather)] text-white'
                  : 'bg-[var(--color-parchment)]/60 text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
              >
                ⚖️ 红绿对比 Diff + 修改清单
              </button>
              <button
                @click="outputTab = 'final'"
                type="button"
                class="px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors"
                :class="outputTab === 'final'
                  ? 'bg-[var(--color-leather)] text-white'
                  : 'bg-[var(--color-parchment)]/60 text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
              >
                📄 最终定稿正文 ({{ editableFinal.length }} 字)
              </button>
              <button
                @click="outputTab = 'draft'"
                type="button"
                class="px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors"
                :class="outputTab === 'draft'
                  ? 'bg-[var(--color-leather)] text-white'
                  : 'bg-[var(--color-parchment)]/60 text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
              >
                📝 3.8 Flash 原初稿 ({{ displayDraft.length }} 字)
              </button>
              <button
                @click="outputTab = 'memory'"
                type="button"
                class="px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors"
                :class="outputTab === 'memory'
                  ? 'bg-[var(--color-leather)] text-white'
                  : 'bg-[var(--color-parchment)]/60 text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
              >
                🔗 归档记忆与下章交接
              </button>
            </div>

            <div class="flex items-center gap-2">
              <button
                @click="handleCopyFinal"
                :disabled="!editableFinal && !displayDraft"
                type="button"
                class="px-2.5 py-1 rounded-lg border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/40 hover:bg-[var(--color-parchment)] text-xs font-medium disabled:opacity-40 cursor-pointer"
              >
                {{ copiedTip ? '✓ 已复制' : '📋 复制正文' }}
              </button>
              <button
                v-if="outputTab === 'final'"
                @click="handleSaveFinalText"
                :disabled="savingFinal || !editableFinal.trim()"
                type="button"
                class="btn-primary text-xs"
              >
                {{ savingFinal ? '保存中…' : '💾 保存修改' }}
              </button>
            </div>
          </div>

          <!-- Tab 1: 红绿 Diff -->
          <DiffViewer
            v-if="outputTab === 'diff'"
            :old-text="displayDraft"
            :new-text="displayFinal"
            :checklist="displayChecklist"
            :loading="artifactsLoading"
          />

          <!-- Tab 2: 最终定稿可编辑正文 -->
          <div v-else-if="outputTab === 'final'" class="space-y-2">
            <textarea
              v-model="editableFinal"
              rows="20"
              placeholder="本章暂无定稿正文。运行单章或批量队列后，审校定稿将自动显示于此，您可直接精修并保存。"
              class="w-full rounded-xl border border-[var(--color-parchment-darker)] !bg-[#131417] p-4 text-sm !text-[#d4d4d8] leading-loose focus:outline-none focus:border-zinc-500 font-novel-prose"
            />
          </div>

          <!-- Tab 3: 3.8 Flash 原初稿 -->
          <div v-else-if="outputTab === 'draft'" class="space-y-2">
            <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-[#131417] p-4 text-sm text-[#d4d4d8] leading-loose whitespace-pre-wrap max-h-[600px] overflow-y-auto font-novel-prose">
              {{ displayDraft || '暂无 3.8 Flash 原初稿记录。' }}
            </div>
          </div>

          <!-- Tab 4: 归档记忆与交接 -->
          <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-3 text-xs">
            <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/25 p-3 space-y-1.5">
              <div class="font-bold text-[var(--color-ink)]">📌 归档后的全局摘要 (global_summary.txt)</div>
              <div class="text-[var(--color-ink)] whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
                {{ state.pipelineData.value.summary || artifactsData.summary || '暂无摘要' }}
              </div>
            </div>
            <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/25 p-3 space-y-1.5">
              <div class="font-bold text-[var(--color-ink)]">🧬 角色状态演进表 (character_state.txt)</div>
              <div class="text-[var(--color-ink)] whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
                {{ state.pipelineData.value.characterState || artifactsData.character_state || '暂无状态记录' }}
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- 依赖全文预览弹窗（柔和暖纸风） -->
    <div
      v-if="previewModal"
      class="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
      @click.self="previewModal = null"
    >
      <div class="w-full max-w-3xl rounded-2xl border border-[var(--color-parchment-darker)] bg-white shadow-xl overflow-hidden flex flex-col max-h-[82vh]">
        <div class="px-4 py-3 border-b border-[var(--color-parchment-dark)] bg-[var(--color-parchment)] flex items-center justify-between">
          <span class="font-bold text-sm text-[var(--color-ink)]">📥 {{ previewModal.title }} · 注入内容全文预览</span>
          <button
            @click="previewModal = null"
            type="button"
            class="px-2.5 py-1 rounded-lg bg-white border border-[var(--color-parchment-darker)] text-xs font-medium cursor-pointer"
          >
            关闭 ✕
          </button>
        </div>
        <div class="p-4 overflow-y-auto text-xs text-[var(--color-ink)] whitespace-pre-wrap leading-relaxed font-mono">
          {{ previewModal.content }}
        </div>
      </div>
    </div>
  </div>
</template>
