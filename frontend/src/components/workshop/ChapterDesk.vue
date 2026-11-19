<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useLocalStorage } from '@vueuse/core'
import { generateApi } from '@/api/client'
import type { useWorkshopState } from '@/composables/useWorkshopState'
import type { DashboardChapterItem } from './WorkflowStepper.vue'
import ChapterSidebar from './ChapterSidebar.vue'
import DetailedOutlineStep from './DetailedOutlineStep.vue'
import ChapterStep from './ChapterStep.vue'
import FinalizeStep from './FinalizeStep.vue'
import ExpandStep from './ExpandStep.vue'
import HumanizerStep from './HumanizerStep.vue'
import BrainstormPanel from '@/components/BrainstormPanel.vue'

const props = defineProps<{
  state: ReturnType<typeof useWorkshopState>
  chapters: DashboardChapterItem[]
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'goStage', stage: 'stage1' | 'stage2'): void
}>()

// ── 中央正文画布状态 ──────────────────────────────────────────────────────────
type CanvasTab = 'prose' | 'compare' | 'notes' | 'translation'
const canvasTab = ref<CanvasTab>('prose')
const editing = ref(false)
const editText = ref('')
const savingProse = ref(false)
const toastMsg = ref('')
const fontSize = useLocalStorage('desk-prose-font-size', 17)

// ── 右侧 AI 副驾驶抽屉 ──────────────────────────────────────────────────────
type CopilotTab = 'pipeline' | 'manual' | 'chat'
const copilotOpen = ref(true)
const copilotTab = ref<CopilotTab>('pipeline')
const manualTool = ref<'outline' | 'draft' | 'finalize' | 'expand' | 'humanize'>('expand')
const showLogs = ref(false)
const showAdvanced = ref(false)
const logBoxRef = ref<HTMLDivElement | null>(null)

// ── 正史设定加载 ──────────────────────────────────────────────────────────────
const canonHistoryText = ref('')
async function fetchCanonHistory() {
  const fp = props.state.filepath.value
  if (!fp) return
  try {
    const res = await fetch(`/api/generate/canon_history?filepath=${encodeURIComponent(fp)}`)
    if (res.ok) {
      const data = await res.json()
      canonHistoryText.value = data.canon || ''
    }
  } catch { /* ignore */ }
}

onMounted(async () => {
  if (!props.state.pipelineRunning.value) {
    await props.state.loadChapterArtifacts(props.state.chapterNum.value)
    await props.state.loadHandoff(props.state.chapterNum.value > 1 ? props.state.chapterNum.value - 1 : 1)
    if (props.state.pipelineMode.value === 'bilingual') {
      await props.state.loadFixedTerms()
    }
  }
  fetchCanonHistory()
})

watch(() => props.state.filepath.value, () => {
  editing.value = false
  fetchCanonHistory()
})

watch(() => props.state.chapterNum.value, async (newNum) => {
  editing.value = false
  if (newNum && !props.state.pipelineRunning.value) {
    await props.state.loadChapterArtifacts(newNum)
  }
})

watch(() => props.state.pipelineMode.value, (mode) => {
  if (mode === 'fast_zh' && canvasTab.value === 'translation') {
    canvasTab.value = 'prose'
  }
})

watch(() => props.state.pipelineTerminalLogs.value.length, () => {
  nextTick(() => {
    if (logBoxRef.value) {
      logBoxRef.value.scrollTop = logBoxRef.value.scrollHeight
    }
  })
})

// ── 计算属性：产物展示 ────────────────────────────────────────────────────────
const currentChapterMeta = computed(() =>
  props.chapters.find((c) => c.num === props.state.chapterNum.value),
)

const displayDraft = computed(() =>
  props.state.pipelineData.value.draft || '',
)

const displayFinal = computed(() =>
  props.state.pipelineData.value.polished ||
  props.state.expandNew.value ||
  props.state.chapter.value.result ||
  '',
)

const displayChecklist = computed(() =>
  props.state.pipelineData.value.checklist || '',
)

const displayTranslation = computed(() =>
  props.state.pipelineData.value.translation ||
  props.state.translateResult.value ||
  props.state.translateState.value.result ||
  '',
)

const displayAudit = computed(() =>
  props.state.pipelineData.value.audit ||
  props.state.auditState.value.result ||
  '',
)

const displaySummary = computed(() =>
  props.state.pipelineData.value.summary || '',
)

const displayCanon = computed(() =>
  props.state.pipelineData.value.canonHistory || canonHistoryText.value || '',
)

const isDirty = computed(() => editing.value && editText.value !== displayFinal.value)

const needsOutline = computed(() =>
  !props.state.bp.value.result && !props.state.arch.value.result,
)

// ── 交互操作 ──────────────────────────────────────────────────────────────────
function showToast(msg: string) {
  toastMsg.value = msg
  setTimeout(() => { toastMsg.value = '' }, 2500)
}

function enterEdit() {
  editText.value = displayFinal.value
  editing.value = true
  canvasTab.value = 'prose'
}

function cancelEdit() {
  editing.value = false
  editText.value = displayFinal.value
}

async function saveProseEdit() {
  const num = props.state.chapterNum.value
  if (!num) return
  savingProse.value = true
  try {
    await generateApi.saveChapter(num, editText.value, props.state.filepath.value)
    props.state.pipelineData.value.polished = editText.value
    props.state.chapter.value.result = editText.value
    editing.value = false
    showToast(`✅ 第 ${num} 章正文已保存`)
    emit('refresh')
  } catch (e: unknown) {
    showToast(`❌ 保存失败: ${(e as Error).message}`)
  } finally {
    savingProse.value = false
  }
}

async function copyText(text: string, label: string) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    showToast(`✅ 已复制${label}`)
  } catch {
    showToast('❌ 复制失败')
  }
}

function appendGuidance(text: string) {
  const cur = props.state.chGuidance.value?.trim()
  props.state.chGuidance.value = cur ? `${cur}\n${text}` : text
}

function formatElapsed(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
</script>

<template>
  <div class="flex flex-col lg:flex-row items-stretch gap-4">
    <!-- ── 左栏：章节目录树 ── -->
    <div class="w-full lg:w-64 xl:w-68 shrink-0">
      <ChapterSidebar
        :state="state"
        :chapters="chapters"
        :loading="loading"
        @refresh="emit('refresh')"
      />
    </div>

    <!-- ── 中栏：大画布阅读与直接编辑区 ── -->
    <section class="flex-1 min-w-0 rounded-2xl border border-[var(--color-parchment-darker)] bg-white shadow-sm flex flex-col overflow-hidden h-[760px]">
      <!-- 顶部工具栏 -->
      <div class="px-4 py-2.5 bg-[var(--color-parchment)]/50 border-b border-[var(--color-parchment-darker)] flex items-center justify-between flex-wrap gap-2">
        <div class="flex items-center gap-2 min-w-0">
          <span class="font-bold text-base text-[var(--color-ink)]">
            第 {{ state.chapterNum.value }} 章
          </span>
          <span v-if="currentChapterMeta?.title" class="text-xs text-[var(--color-ink-light)] truncate max-w-[220px]">
            {{ currentChapterMeta.title }}
          </span>
          <span v-if="displayFinal" class="text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200">
            {{ displayFinal.length.toLocaleString() }} 字
          </span>
          <span v-if="isDirty" class="text-[11px] text-amber-600 font-semibold">● 未保存</span>
          <span v-if="toastMsg" class="text-xs font-medium text-[var(--color-leather)]">{{ toastMsg }}</span>
        </div>

        <div class="flex items-center gap-1.5 flex-wrap">
          <!-- 画布视图切换 -->
          <div class="flex items-center bg-[var(--color-parchment)] p-0.5 rounded-lg border border-[var(--color-parchment-darker)] text-xs">
            <button
              @click="canvasTab = 'prose'"
              type="button"
              class="px-2.5 py-1 rounded-md font-medium cursor-pointer transition-colors"
              :class="canvasTab === 'prose' ? 'bg-white text-[var(--color-leather)] shadow-xs font-bold' : 'text-[var(--color-ink-light)]'"
            >
              📄 正文
            </button>
            <button
              @click="canvasTab = 'compare'"
              type="button"
              class="px-2.5 py-1 rounded-md font-medium cursor-pointer transition-colors"
              :class="canvasTab === 'compare' ? 'bg-white text-[var(--color-leather)] shadow-xs font-bold' : 'text-[var(--color-ink-light)]'"
            >
              ⚖️ 初稿对比
            </button>
            <button
              @click="canvasTab = 'notes'"
              type="button"
              class="px-2.5 py-1 rounded-md font-medium cursor-pointer transition-colors"
              :class="canvasTab === 'notes' ? 'bg-white text-[var(--color-leather)] shadow-xs font-bold' : 'text-[var(--color-ink-light)]'"
            >
              📋 清单与记忆
            </button>
            <button
              v-if="state.pipelineMode.value === 'bilingual'"
              @click="canvasTab = 'translation'"
              type="button"
              class="px-2.5 py-1 rounded-md font-medium cursor-pointer transition-colors"
              :class="canvasTab === 'translation' ? 'bg-white text-indigo-700 shadow-xs font-bold' : 'text-[var(--color-ink-light)]'"
            >
              🇺🇸 英文译稿
            </button>
          </div>

          <!-- 编辑/保存控制 -->
          <template v-if="canvasTab === 'prose'">
            <button
              v-if="!editing"
              @click="enterEdit()"
              :disabled="!displayFinal"
              type="button"
              class="px-2.5 py-1 rounded-md border border-[var(--color-parchment-darker)] bg-white hover:bg-[var(--color-parchment)] text-xs font-medium disabled:opacity-40 cursor-pointer"
            >
              ✏️ 编辑
            </button>
            <template v-else>
              <button
                @click="saveProseEdit()"
                :disabled="savingProse || !isDirty"
                type="button"
                class="px-2.5 py-1 rounded-md bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 disabled:opacity-40 cursor-pointer"
              >
                {{ savingProse ? '保存中…' : '💾 保存' }}
              </button>
              <button
                @click="cancelEdit()"
                type="button"
                class="px-2 py-1 rounded-md border border-[var(--color-parchment-darker)] bg-white text-xs cursor-pointer"
              >
                取消
              </button>
            </template>
            <button
              @click="copyText(displayFinal, '章节正文')"
              :disabled="!displayFinal"
              type="button"
              class="px-2 py-1 rounded-md border border-[var(--color-parchment-darker)] bg-white hover:bg-[var(--color-parchment)] text-xs disabled:opacity-40 cursor-pointer"
              title="复制正文"
            >
              📋
            </button>
            <div class="hidden sm:flex items-center border border-[var(--color-parchment-darker)] rounded-md bg-white text-xs">
              <button @click="fontSize = Math.max(13, fontSize - 1)" type="button" class="px-1.5 py-1 hover:bg-[var(--color-parchment)] cursor-pointer">A-</button>
              <button @click="fontSize = Math.min(24, fontSize + 1)" type="button" class="px-1.5 py-1 hover:bg-[var(--color-parchment)] cursor-pointer border-l border-[var(--color-parchment-dark)]">A+</button>
            </div>
          </template>

          <!-- 展开/收起右侧 AI 副驾驶 -->
          <button
            @click="copilotOpen = !copilotOpen"
            type="button"
            class="px-2.5 py-1 rounded-md text-xs font-semibold cursor-pointer transition-colors"
            :class="copilotOpen ? 'bg-[var(--color-leather)] text-white' : 'bg-amber-100 text-amber-900 border border-amber-300'"
          >
            {{ copilotOpen ? '收起 AI 面板 ▸' : '◂ 打开 AI 面板' }}
          </button>
        </div>
      </div>

      <!-- 画布主体 -->
      <div class="flex-1 overflow-y-auto p-5 bg-[#fdfbf7]">
        <!-- 1. 正式正文阅读 / 直接编辑 -->
        <template v-if="canvasTab === 'prose'">
          <div v-if="editing" class="h-full flex flex-col">
            <textarea
              v-model="editText"
              class="flex-1 w-full rounded-xl border border-[var(--color-parchment-darker)] bg-white p-4 font-serif leading-loose text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-leather)] resize-none"
              :style="{ fontSize: `${fontSize}px` }"
              placeholder="在此直接撰写或修改本章正文…"
            />
          </div>

          <div v-else-if="displayFinal" class="max-w-3xl mx-auto font-serif leading-loose text-[var(--color-ink)] whitespace-pre-wrap" :style="{ fontSize: `${fontSize}px` }">
            {{ displayFinal }}
          </div>

          <div v-else class="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto space-y-4">
            <div class="text-4xl">✍️</div>
            <div v-if="needsOutline" class="space-y-2">
              <h4 class="font-bold text-base text-[var(--color-ink)]">这本书还没有生成大纲蓝图</h4>
              <p class="text-xs text-[var(--color-ink-light)] leading-relaxed">
                建议先到「① 立项与架构」填好脑洞与 50 万字目标（200 章），一键生成全书骨架与目录，再回来自动写稿。
              </p>
              <button
                @click="emit('goStage', 'stage1')"
                type="button"
                class="btn-primary text-xs"
              >
                前往 ① 立项与架构 ➔
              </button>
            </div>
            <div v-else class="space-y-2">
              <h4 class="font-bold text-base text-[var(--color-ink)]">第 {{ state.chapterNum.value }} 章尚未生成</h4>
              <p class="text-xs text-[var(--color-ink-light)] leading-relaxed">
                点击右侧「⚡ 一键生成并审校第 {{ state.chapterNum.value }} 章」，系统会自动补全细纲、用 3.8 Flash 起草、再由 4 Hydrogen 审校润色并显示在这里。
              </p>
              <button
                v-if="!state.pipelineRunning.value"
                @click="copilotOpen = true; copilotTab = 'pipeline'; state.doRunPipeline()"
                type="button"
                class="btn-primary text-xs"
              >
                ⚡ 立即生成第 {{ state.chapterNum.value }} 章
              </button>
            </div>
          </div>
        </template>

        <!-- 2. 初稿 vs 审校定稿对比 -->
        <div v-else-if="canvasTab === 'compare'" class="grid grid-cols-1 md:grid-cols-2 gap-4 h-full">
          <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-white flex flex-col overflow-hidden">
            <div class="px-3.5 py-2 bg-amber-50 border-b border-amber-200 flex items-center justify-between text-xs font-bold text-amber-900">
              <span>📝 3.8 Flash 原始初稿</span>
              <span class="font-mono">{{ displayDraft.length }} 字</span>
            </div>
            <div class="p-4 flex-1 overflow-y-auto font-serif text-sm leading-relaxed whitespace-pre-wrap text-[var(--color-ink)]">
              {{ displayDraft || '暂无初稿记录' }}
            </div>
          </div>
          <div class="rounded-xl border border-emerald-200 bg-white flex flex-col overflow-hidden">
            <div class="px-3.5 py-2 bg-emerald-50 border-b border-emerald-200 flex items-center justify-between text-xs font-bold text-emerald-900">
              <span>🛡️ 4 Hydrogen 审校定稿</span>
              <span class="font-mono">{{ displayFinal.length }} 字</span>
            </div>
            <div class="p-4 flex-1 overflow-y-auto font-serif text-sm leading-relaxed whitespace-pre-wrap text-[var(--color-ink)]">
              {{ displayFinal || '暂无审校定稿' }}
            </div>
          </div>
        </div>

        <!-- 3. 审校修改清单 & 因果记忆 -->
        <div v-else-if="canvasTab === 'notes'" class="space-y-4 max-w-4xl mx-auto">
          <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-white p-4 space-y-2">
            <h4 class="font-bold text-sm text-[var(--color-leather)]">📋 本章审校修改清单</h4>
            <div class="text-xs font-mono whitespace-pre-wrap text-[var(--color-ink-light)] leading-relaxed">
              {{ displayChecklist || '运行自动流水线或精修后，修改说明将显示在此处。' }}
            </div>
          </div>

          <div v-if="state.handoffData.value" class="rounded-xl border border-sky-200 bg-sky-50/40 p-4 space-y-1.5 text-xs">
            <h4 class="font-bold text-sm text-sky-900">🔗 因果交接契约 (Handoff)</h4>
            <div><strong>核心转变：</strong>{{ state.handoffData.value.what_changed }}</div>
            <div><strong>下章意图：</strong>{{ state.handoffData.value.active_intentions }}</div>
            <div v-if="state.handoffData.value.must_not_restate?.length" class="text-rose-700">
              <strong>🚫 禁止重复：</strong>{{ state.handoffData.value.must_not_restate.join('；') }}
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-white p-4 space-y-2">
              <h4 class="font-bold text-sm text-[var(--color-leather)]">📜 正史设定页</h4>
              <div class="text-xs whitespace-pre-wrap text-[var(--color-ink-light)] leading-relaxed max-h-64 overflow-y-auto">
                {{ displayCanon || '暂无正史记录' }}
              </div>
            </div>
            <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-white p-4 space-y-2">
              <h4 class="font-bold text-sm text-[var(--color-leather)]">🧠 全局前文摘要</h4>
              <div class="text-xs whitespace-pre-wrap text-[var(--color-ink-light)] leading-relaxed max-h-64 overflow-y-auto">
                {{ displaySummary || '暂无前文摘要' }}
              </div>
            </div>
          </div>
        </div>

        <!-- 4. 出海英文译稿（仅 bilingual 模式） -->
        <div v-else-if="canvasTab === 'translation'" class="space-y-4 max-w-4xl mx-auto">
          <div class="rounded-xl border border-indigo-200 bg-white p-4 space-y-2">
            <div class="flex items-center justify-between">
              <h4 class="font-bold text-sm text-indigo-900">🇺🇸 美式英文译稿</h4>
              <button @click="copyText(displayTranslation, '英文译稿')" :disabled="!displayTranslation" type="button" class="btn-sm">
                📋 复制英文
              </button>
            </div>
            <div class="font-serif text-sm leading-relaxed whitespace-pre-wrap text-[var(--color-ink)]">
              {{ displayTranslation || '暂无英文译稿，请在流水线切换到「英文出海」后生成。' }}
            </div>
          </div>
          <div v-if="displayAudit" class="rounded-xl border border-amber-200 bg-amber-50/40 p-4 space-y-2">
            <h4 class="font-bold text-sm text-amber-900">🛡️ 双语质检报告</h4>
            <div class="text-xs font-mono whitespace-pre-wrap text-[var(--color-ink-light)]">{{ displayAudit }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ── 右栏：可切换 AI 副驾驶抽屉 ── -->
    <aside
      v-if="copilotOpen"
      class="w-full lg:w-88 xl:w-96 shrink-0 rounded-2xl border border-[var(--color-parchment-darker)] bg-white shadow-sm flex flex-col overflow-hidden h-[760px]"
    >
      <!-- 抽屉顶部 3 模式切换 -->
      <div class="p-2 bg-[var(--color-parchment)]/60 border-b border-[var(--color-parchment-darker)] grid grid-cols-3 gap-1 text-xs">
        <button
          @click="copilotTab = 'pipeline'"
          type="button"
          class="py-1.5 rounded-lg font-semibold cursor-pointer transition-all"
          :class="copilotTab === 'pipeline' ? 'bg-[var(--color-leather)] text-white shadow-xs' : 'text-[var(--color-ink-light)] hover:bg-white'"
        >
          ⚡ 自动流水线
        </button>
        <button
          @click="copilotTab = 'manual'"
          type="button"
          class="py-1.5 rounded-lg font-semibold cursor-pointer transition-all"
          :class="copilotTab === 'manual' ? 'bg-[var(--color-leather)] text-white shadow-xs' : 'text-[var(--color-ink-light)] hover:bg-white'"
        >
          🛠️ 单步精修
        </button>
        <button
          @click="copilotTab = 'chat'"
          type="button"
          class="py-1.5 rounded-lg font-semibold cursor-pointer transition-all"
          :class="copilotTab === 'chat' ? 'bg-[var(--color-leather)] text-white shadow-xs' : 'text-[var(--color-ink-light)] hover:bg-white'"
        >
          💬 AI 聊天
        </button>
      </div>

      <!-- Tab 1: 自动流水线 -->
      <div v-show="copilotTab === 'pipeline'" class="flex-1 overflow-y-auto p-3.5 space-y-3.5">
        <!-- 模式切换 + 顺延开关 -->
        <div class="flex items-center justify-between gap-2 flex-wrap">
          <div class="flex items-center bg-[var(--color-parchment)] p-0.5 rounded-lg border border-[var(--color-parchment-darker)] text-xs">
            <button
              @click="state.setPipelineMode('fast_zh')"
              type="button"
              class="px-2.5 py-1 rounded-md font-semibold cursor-pointer transition-all"
              :class="state.pipelineMode.value === 'fast_zh' ? 'bg-[var(--color-leather)] text-white shadow-xs' : 'text-[var(--color-ink-light)]'"
            >
              🇨🇳 中文 4步
            </button>
            <button
              @click="state.setPipelineMode('bilingual')"
              type="button"
              class="px-2.5 py-1 rounded-md font-semibold cursor-pointer transition-all"
              :class="state.pipelineMode.value === 'bilingual' ? 'bg-indigo-700 text-white shadow-xs' : 'text-[var(--color-ink-light)]'"
            >
              🌐 出海 6步
            </button>
          </div>
          <label class="flex items-center gap-1.5 text-xs text-[var(--color-ink-light)] cursor-pointer select-none">
            <input type="checkbox" v-model="state.pipelineAutoAdvance.value" class="accent-[var(--color-leather)]" />
            <span>写完跳下一章</span>
          </label>
        </div>

        <!-- 纵向可视化流水线步骤图 -->
        <div class="space-y-2">
          <div
            v-for="(st, idx) in state.pipelineStages.value"
            :key="st.id"
            class="relative rounded-xl border p-2.5 transition-all"
            :class="
              st.status === 'running'
                ? 'border-amber-400 bg-amber-50/70 shadow-xs'
                : st.status === 'completed'
                  ? 'border-emerald-200 bg-emerald-50/40'
                  : st.status === 'error'
                    ? 'border-red-300 bg-red-50'
                    : 'border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/25'
            "
          >
            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2 min-w-0">
                <span
                  class="w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center shrink-0"
                  :class="
                    st.status === 'completed'
                      ? 'bg-emerald-600 text-white'
                      : st.status === 'running'
                        ? 'bg-amber-600 text-white animate-pulse'
                        : st.status === 'error'
                          ? 'bg-red-600 text-white'
                          : 'bg-[var(--color-parchment-dark)] text-[var(--color-ink-light)]'
                  "
                >
                  {{ st.status === 'completed' ? '✓' : st.status === 'running' ? '⚡' : idx + 1 }}
                </span>
                <div class="min-w-0">
                  <div class="text-xs font-bold text-[var(--color-ink)] truncate">{{ st.name }}</div>
                  <div class="text-[10px] text-[var(--color-ink-light)] truncate">{{ st.subtitle }}</div>
                </div>
              </div>
              <span class="text-[10px] font-mono font-semibold shrink-0 text-[var(--color-ink-light)]">
                {{ st.status === 'completed' ? '100%' : st.status === 'running' ? `${Math.round(st.progress || 0)}%` : '待命' }}
              </span>
            </div>
            <div v-if="st.status === 'running' || st.status === 'completed'" class="w-full h-1 bg-stone-200 rounded-full mt-2 overflow-hidden">
              <div
                class="h-full transition-all duration-300"
                :class="st.status === 'completed' ? 'bg-emerald-500' : 'bg-amber-500'"
                :style="{ width: `${st.progress || 0}%` }"
              />
            </div>
          </div>
        </div>

        <!-- 本章导演指令 -->
        <div class="space-y-1.5">
          <div class="flex items-center justify-between text-xs">
            <label class="font-semibold text-[var(--color-ink)]">🎬 本章写作指令（可选）</label>
            <button
              @click="state.autoFillChapterParams(state.chapterNum.value, true)"
              type="button"
              class="text-[11px] text-[var(--color-leather)] hover:underline cursor-pointer"
            >
              ✨ 从大纲同步
            </button>
          </div>
          <textarea
            v-model="state.chGuidance.value"
            :disabled="state.pipelineRunning.value"
            rows="3"
            placeholder="输入本章重点冲突、金手指或反转要求；留空则按细纲自动写…"
            class="w-full rounded-xl border border-[var(--color-parchment-darker)] p-2.5 text-xs leading-relaxed focus:outline-none focus:border-[var(--color-leather)]"
          />
          <div v-if="state.pipelineMode.value === 'fast_zh'" class="flex flex-wrap gap-1 text-[11px]">
            <button @click="appendGuidance('【受辱觉醒】绝境下系统觉醒，反差震撼')" type="button" class="px-2 py-0.5 rounded bg-[var(--color-parchment)] hover:bg-[var(--color-parchment-dark)] cursor-pointer">⚡ 受辱觉醒</button>
            <button @click="appendGuidance('【当面反杀】反派挑衅，主角果断打脸')" type="button" class="px-2 py-0.5 rounded bg-[var(--color-parchment)] hover:bg-[var(--color-parchment-dark)] cursor-pointer">💥 当面反杀</button>
            <button @click="appendGuidance('【章末卡点】结尾留在危机爆发或反转瞬间')" type="button" class="px-2 py-0.5 rounded bg-[var(--color-parchment)] hover:bg-[var(--color-parchment-dark)] cursor-pointer">🪝 章末卡点</button>
          </div>

          <button
            @click="showAdvanced = !showAdvanced"
            type="button"
            class="text-[11px] text-[var(--color-ink-light)] hover:text-[var(--color-leather)] cursor-pointer"
          >
            {{ showAdvanced ? '▲ 收起角色/场景参数' : '▼ 展开角色/场景/字数参数' }}
          </button>
          <div v-if="showAdvanced" class="grid grid-cols-2 gap-2 pt-1 text-xs">
            <input v-model="state.charactersInvolved.value" placeholder="登场角色" class="border border-[var(--color-parchment-darker)] rounded px-2 py-1" />
            <input v-model="state.sceneLocation.value" placeholder="场景地点" class="border border-[var(--color-parchment-darker)] rounded px-2 py-1" />
            <input v-model="state.keyItems.value" placeholder="关键道具" class="border border-[var(--color-parchment-darker)] rounded px-2 py-1" />
            <input v-model.number="state.wordNumber.value" type="number" step="500" placeholder="每章字数" class="border border-[var(--color-parchment-darker)] rounded px-2 py-1" />
          </div>
        </div>

        <!-- 主行动按钮 -->
        <div class="pt-1 space-y-2">
          <button
            v-if="!state.pipelineRunning.value"
            @click="state.doRunPipeline()"
            type="button"
            class="w-full py-2.5 rounded-xl bg-[var(--color-leather)] hover:bg-[var(--color-leather-light)] text-white font-bold text-sm shadow-sm cursor-pointer transition-all"
          >
            ⚡ 一键生成并审校第 {{ state.chapterNum.value }} 章
          </button>
          <button
            v-else
            @click="state.cancelPipeline()"
            type="button"
            class="w-full py-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white font-bold text-sm cursor-pointer"
          >
            ⏹️ 终止运行 ({{ formatElapsed(state.pipelineElapsed.value) }})
          </button>

          <div class="flex items-center justify-between text-[11px] text-[var(--color-ink-light)]">
            <span class="truncate">{{ state.pipelineStatusMsg.value || '就绪' }}</span>
            <button @click="showLogs = !showLogs" type="button" class="underline cursor-pointer shrink-0 ml-2">
              {{ showLogs ? '隐藏日志' : '查看日志' }}
            </button>
          </div>

          <div
            v-if="showLogs"
            ref="logBoxRef"
            class="max-h-36 overflow-y-auto rounded-lg bg-[var(--color-parchment)]/60 border border-[var(--color-parchment-darker)] p-2 font-mono text-[10px] space-y-1 text-[var(--color-ink-light)]"
          >
            <div v-for="(line, i) in state.pipelineTerminalLogs.value" :key="i">{{ line }}</div>
          </div>
        </div>
      </div>

      <!-- Tab 2: 单步精修工具 -->
      <div v-show="copilotTab === 'manual'" class="flex-1 overflow-y-auto p-3 space-y-3">
        <div class="flex flex-wrap gap-1 bg-[var(--color-parchment)]/60 p-1 rounded-lg text-[11px]">
          <button
            v-for="m in [
              { id: 'outline', label: '📝 细纲' },
              { id: 'draft', label: '✍️ 起草' },
              { id: 'finalize', label: '⚡ 定稿' },
              { id: 'expand', label: '🪄 扩写润色' },
              { id: 'humanize', label: '🧹 去AI味' },
            ]"
            :key="m.id"
            @click="manualTool = m.id as any"
            type="button"
            class="px-2 py-1 rounded font-medium cursor-pointer"
            :class="manualTool === m.id ? 'bg-white text-[var(--color-leather)] shadow-xs font-bold' : 'text-[var(--color-ink-light)]'"
          >
            {{ m.label }}
          </button>
        </div>
        <DetailedOutlineStep v-if="manualTool === 'outline'" :state="state" />
        <ChapterStep v-else-if="manualTool === 'draft'" :state="state" />
        <FinalizeStep v-else-if="manualTool === 'finalize'" :state="state" />
        <ExpandStep v-else-if="manualTool === 'expand'" :state="state" />
        <HumanizerStep v-else :state="state" />
      </div>

      <!-- Tab 3: 同屏 AI 聊天 -->
      <div v-show="copilotTab === 'chat'" class="flex-1 overflow-hidden flex flex-col">
        <BrainstormPanel compact @close="copilotTab = 'pipeline'" />
      </div>
    </aside>
  </div>
</template>
