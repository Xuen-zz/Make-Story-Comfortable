<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'
import { generateApi } from '@/api/client'

const props = defineProps<{
  state: ReturnType<typeof useWorkshopState>
}>()

const terminalContainer = ref<HTMLDivElement | null>(null)
const polishSubTab = ref<'text' | 'checklist'>('text')
const copySuccessMsg = ref('')

function showCopyToast(msg: string) {
  copySuccessMsg.value = msg
  setTimeout(() => { copySuccessMsg.value = '' }, 2500)
}

function copyToClipboard(text: string, label: string) {
  if (!text) return
  navigator.clipboard.writeText(text).then(() => {
    showCopyToast(`✅ ${label} 已复制到剪贴板！`)
  }).catch(() => {
    showCopyToast(`❌ 复制失败，请手动选取复制`)
  })
}

function downloadText(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
  showCopyToast(`📥 已导出文件: ${filename}`)
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

// 自动滚动终端监视器
watch(
  () => props.state.pipelineTerminalLogs.value.length,
  () => {
    nextTick(() => {
      if (terminalContainer.value) {
        terminalContainer.value.scrollTop = terminalContainer.value.scrollHeight
      }
    })
  }
)

// 节点点击交互：智能切换到对应视图
function handleNodeClick(stageId: number) {
  switch (stageId) {
    case 1:
      props.state.pipelineActiveTab.value = 'continuity'
      props.state.loadHandoff(props.state.chapterNum.value > 1 ? props.state.chapterNum.value - 1 : 1)
      fetchCanonHistory()
      break
    case 2:
      props.state.pipelineActiveTab.value = 'draft'
      break
    case 3:
      props.state.pipelineActiveTab.value = 'polish'
      break
    case 4:
      if (props.state.pipelineMode?.value === 'fast_zh') {
        props.state.pipelineActiveTab.value = 'continuity'
        props.state.loadHandoff(props.state.chapterNum.value)
        fetchCanonHistory()
      } else {
        props.state.pipelineActiveTab.value = 'translation'
        if (!displayTranslation.value) {
          props.state.loadChapterEn(props.state.chapterNum.value)
        }
      }
      break
    case 5:
      props.state.pipelineActiveTab.value = 'audit'
      break
    case 6:
      props.state.pipelineActiveTab.value = 'continuity'
      props.state.loadHandoff(props.state.chapterNum.value)
      fetchCanonHistory()
      break
    default:
      props.state.pipelineActiveTab.value = 'terminal'
  }
}

const displayTranslation = computed(() => {
  return props.state.pipelineData.value.translation || props.state.translateResult.value || props.state.translateState.value.result || ''
})

const displayDraft = computed(() => {
  return props.state.pipelineData.value.draft || props.state.chapter.value.result || ''
})

const displayPolished = computed(() => {
  return props.state.pipelineData.value.polished || props.state.expandNew.value || props.state.chapter.value.result || ''
})

const displayChecklist = computed(() => {
  return props.state.pipelineData.value.checklist || ''
})

const englishWordCount = computed(() => {
  const t = displayTranslation.value
  if (!t.trim()) return 0
  return t.trim().split(/\s+/).length
})

const draftWordCount = computed(() => {
  return displayDraft.value.length
})

const polishedWordCount = computed(() => {
  return displayPolished.value.length
})

const canonHistoryText = ref('')

async function fetchCanonHistory() {
  try {
    const fp = props.state.filepath?.value || props.state.projectStore?.activeProjectData?.filepath
    if (!fp) return
    const res = await fetch(`/api/generate/canon_history?filepath=${encodeURIComponent(fp)}`)
    if (res.ok) {
      const data = await res.json()
      canonHistoryText.value = data.canon || ''
    }
  } catch (e) {
    console.error('Failed to fetch canon history:', e)
  }
}

watch(() => props.state.chapterNum.value, async (newVal) => {
  if (newVal && !props.state.pipelineRunning.value) {
    await props.state.loadChapterArtifacts(newVal)
    await props.state.loadHandoff(newVal > 1 ? newVal - 1 : 1)
  }
})

const directoryChapters = ref<{ num?: number; chapter_num?: number; title_zh?: string; title_en?: string }[]>([])

async function fetchDirectory() {
  try {
    const fp = props.state.filepath?.value || props.state.projectStore?.activeProjectData?.filepath
    if (!fp) return
    const res = await generateApi.getDirectoryEn(fp)
    if (res.data?.chapters) {
      directoryChapters.value = res.data.chapters
    }
  } catch (e) {
    // ignore
  }
}

const currentTargetCh = computed(() => props.state.pipelineTargetChapter.value || props.state.chapterNum.value)

const currentTitleEn = computed(() => {
  const item = directoryChapters.value.find((c) => (c.num ?? c.chapter_num) === currentTargetCh.value)
  if (item?.title_en) return item.title_en
  return `Chapter ${currentTargetCh.value}`
})

const currentTitleZh = computed(() => {
  const item = directoryChapters.value.find((c) => (c.num ?? c.chapter_num) === currentTargetCh.value)
  if (item?.title_zh) return item.title_zh
  return `第 ${currentTargetCh.value} 章`
})

function copyTranslationWithTitle() {
  if (!displayTranslation.value) return
  const full = `${currentTitleEn.value}\n\n${displayTranslation.value}`
  copyToClipboard(full, '英文【标题+正文】')
}

watch(() => props.state.pipelineOpen.value, async (isOpen) => {
  if (isOpen) {
    if (!props.state.pipelineRunning.value) {
      await props.state.loadChapterArtifacts(props.state.chapterNum.value)
    }
    fetchCanonHistory()
    fetchDirectory()
    props.state.loadHandoff(props.state.chapterNum.value > 1 ? props.state.chapterNum.value - 1 : 1)
    props.state.loadFixedTerms()
  }
})

watch(() => props.state.pipelineData.value.canonHistory, (newVal) => {
  if (newVal) {
    fetchCanonHistory()
  }
})

const displayCanon = computed(() => {
  return props.state.pipelineData.value.canonHistory || canonHistoryText.value || ''
})
</script>

<template>
  <div
    v-if="state.pipelineOpen.value"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-3 sm:p-5 select-none animate-fadeIn"
  >
    <!-- 全屏控制舱主体容器 -->
    <div
      class="w-full h-full max-w-7xl max-h-[96vh] bg-[#0c1017] border border-cyan-950/60 rounded-2xl shadow-2xl flex flex-col overflow-hidden text-stone-200 select-text"
    >
      <!-- 顶部高科技态势驾驶舱状态栏 -->
      <header class="px-5 py-3.5 bg-gradient-to-r from-[#0d141f] via-[#121b2a] to-[#0d141f] border-b border-cyan-900/40 flex items-center justify-between flex-wrap gap-3">
        <!-- 左侧标题与模式指示 -->
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/30 border border-cyan-500/40 flex items-center justify-center text-xl shadow-[0_0_15px_rgba(6,182,212,0.25)]">
            🚀
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h2 class="text-base sm:text-lg font-bold tracking-wide text-cyan-200 flex items-center gap-2">
                全链路自动化生产控制舱
                <span class="text-xs px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-700/50 font-mono">
                  v2.0 Factory
                </span>
              </h2>
            </div>
            <div class="text-xs text-stone-400 flex items-center gap-2 mt-0.5 flex-wrap">
              <span>当前作业目标：</span>
              <strong class="text-amber-300 font-medium">第 {{ state.chapterNum.value }} 章</strong>
              <span class="text-stone-600">|</span>
              <span>模型: <code class="text-stone-300">{{ state.llmConfig.value || '默认' }}</code></span>
              <span v-if="state.chGuidance.value" class="text-stone-600">|</span>
              <span v-if="state.chGuidance.value" class="text-cyan-300 font-mono truncate max-w-[220px]" :title="state.chGuidance.value">
                🎬 指令: {{ state.chGuidance.value }}
              </span>
            </div>
          </div>
        </div>

        <!-- 中部当前生产状态胶囊 -->
        <div class="flex items-center gap-2.5">
          <!-- 运行中状态 -->
          <div
            v-if="state.pipelineRunning.value"
            class="flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-950/80 border border-cyan-500/60 text-cyan-300 text-xs shadow-[0_0_12px_rgba(6,182,212,0.3)] animate-pulse"
          >
            <span class="relative flex h-2 w-2">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
            </span>
            <span class="font-medium">流水线高速运转中 [阶段 {{ state.pipelineCurrentStageId.value }}/6]</span>
          </div>

          <!-- 自纠重试中 -->
          <div
            v-else-if="state.pipelineData.value.retryOccurred && state.pipelineRunning.value"
            class="flex items-center gap-2 px-3 py-1 rounded-full bg-amber-950/80 border border-amber-500/60 text-amber-300 text-xs animate-pulse"
          >
            <span>🔁</span>
            <span>触发智能自纠重译 [1/1]</span>
          </div>

          <!-- 完成并质检通过 -->
          <div
            v-else-if="state.pipelineData.value.auditPass"
            class="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-950/80 border border-emerald-500/60 text-emerald-300 text-xs shadow-[0_0_12px_rgba(16,185,129,0.25)]"
          >
            <span>✅</span>
            <span class="font-medium">全链路生产完成 · 独立质检通过</span>
          </div>

          <!-- 待命就绪 -->
          <div
            v-else
            class="flex items-center gap-2 px-3 py-1 rounded-full bg-stone-900 border border-stone-700 text-stone-400 text-xs"
          >
            <span class="w-2 h-2 rounded-full bg-stone-500"></span>
            <span>待命准备就绪</span>
          </div>

          <!-- 计时器 -->
          <div class="px-2.5 py-1 rounded-lg bg-black/40 border border-stone-800 text-xs font-mono text-cyan-400 flex items-center gap-1.5">
            <span class="text-stone-500">⏱️</span>
            <span>{{ formatElapsed(state.pipelineElapsed.value) }}</span>
          </div>
        </div>

        <!-- 右侧核心控制动作按钮 -->
        <div class="flex items-center gap-2">
          <!-- 🍅 番茄/纯中文极速模式 VS 🌐 出海双语模式 胶囊切换 -->
          <div class="flex items-center bg-stone-900 border border-stone-800 p-0.5 rounded-lg text-xs">
            <button
              @click="state.pipelineMode.value = 'fast_zh'; state.pipelineStages.value = state.defaultPipelineStages()"
              :class="[
                'px-2.5 py-1 rounded font-semibold transition-all cursor-pointer flex items-center gap-1',
                state.pipelineMode.value === 'fast_zh' ? 'bg-rose-950 text-rose-300 border border-rose-800/80 shadow-sm' : 'text-stone-400 hover:text-stone-200'
              ]"
              type="button"
            >
              <span>🍅</span><span>番茄/纯中文模式 (极速4步)</span>
            </button>
            <button
              @click="state.pipelineMode.value = 'bilingual'; state.pipelineStages.value = state.defaultPipelineStages()"
              :class="[
                'px-2.5 py-1 rounded font-semibold transition-all cursor-pointer flex items-center gap-1',
                state.pipelineMode.value === 'bilingual' ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/80 shadow-sm' : 'text-stone-400 hover:text-stone-200'
              ]"
              type="button"
            >
              <span>🌐</span><span>出海双语模式 (完整6步)</span>
            </button>
          </div>

          <!-- 运行 / 终止按钮 -->
          <button
            v-if="state.pipelineRunning.value"
            @click="state.cancelPipeline()"
            type="button"
            class="px-3.5 py-1.5 rounded-lg bg-red-950/80 hover:bg-red-900 border border-red-500/60 text-red-200 text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer shadow-lg active:scale-95"
            title="强行终止当前流水线"
          >
            <span>⏹️</span>
            <span>终止生产</span>
          </button>

          <button
            v-else
            @click="state.doRunPipeline()"
            type="button"
            class="px-4 py-1.5 rounded-lg bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 border border-cyan-400/50 text-white text-xs font-bold flex items-center gap-1.5 transition-all cursor-pointer shadow-[0_0_15px_rgba(6,182,212,0.35)] active:scale-95"
            :title="state.pipelineMode.value === 'fast_zh' ? '一键启动当前章番茄纯中文 4 步极速流水线' : '一键启动当前章出海双语 6 步全自动流水线'"
          >
            <span>⚡</span>
            <span>启动全链路生产</span>
          </button>

          <!-- 跨章查阅其他章节内容 -->
          <button
            @click="state.openQuickReader(state.pipelineTargetChapter.value ? Math.max(1, state.pipelineTargetChapter.value - 1) : 1)"
            type="button"
            class="px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 border border-stone-600 text-amber-300 hover:text-amber-200 text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer shadow hover:border-amber-400 active:scale-95"
            title="在流水线生产期间查阅其他章节的中英文内容（绝不影响后台编译）"
          >
            <span>📖</span>
            <span>查阅其他章</span>
          </button>

          <!-- 规则迭代白皮书 -->
          <button
            @click="state.openWhitepaperModal()"
            type="button"
            class="px-3 py-1.5 rounded-lg bg-amber-950/80 hover:bg-amber-900 border border-amber-600/60 text-amber-300 hover:text-amber-200 text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer shadow hover:border-amber-400 active:scale-95"
            title="查看全书生成留底全景台账与审校记录白皮书"
          >
            <span>📘</span>
            <span>规则迭代白皮书</span>
          </button>

          <!-- 关闭控制舱 -->
          <button
            @click="state.closePipelineControlRoom()"
            type="button"
            class="p-1.5 rounded-lg hover:bg-stone-800 text-stone-400 hover:text-stone-200 transition-colors cursor-pointer"
            title="关闭控制舱（流水线仍可在后台运行）"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </header>

      <!-- 快捷参数与全局进度长条 -->
      <div class="px-5 py-2 bg-[#090d13] border-b border-stone-800/80 flex items-center justify-between text-xs text-stone-400 flex-wrap gap-2">
        <div class="flex items-center gap-4 flex-wrap">
          <div class="flex items-center gap-1.5">
            <span class="text-stone-500">目标字数:</span>
            <span class="text-stone-300 font-mono">{{ state.wordNumber.value }} 字</span>
          </div>
          <template v-if="state.pipelineMode.value === 'bilingual'">
            <div class="flex items-center gap-1.5">
              <span class="text-stone-500">出海标准:</span>
              <span class="text-indigo-300 font-medium">{{ state.translateStyle.value }}</span>
            </div>
            <label class="flex items-center gap-1.5 cursor-pointer hover:text-stone-200 transition-colors">
              <input
                type="checkbox"
                v-model="state.pipelineAutoRetry.value"
                :disabled="state.pipelineRunning.value"
                class="rounded border-stone-700 bg-stone-900 text-cyan-500 focus:ring-0 cursor-pointer"
              />
              <span>质检不达标自动重试 (1次)</span>
            </label>
            <label class="flex items-center gap-1.5 cursor-pointer hover:text-stone-200 transition-colors">
              <input
                type="checkbox"
                v-model="state.adultMode.value"
                :disabled="state.pipelineRunning.value"
                class="rounded border-stone-700 bg-stone-900 text-pink-500 focus:ring-0 cursor-pointer"
              />
              <span :class="state.adultMode.value ? 'text-pink-300 font-bold' : ''">成人向亲密模块(规范转场/失控三要素)</span>
            </label>
          </template>
        </div>

        <div class="flex items-center gap-3 w-full sm:w-auto">
          <span class="text-stone-400 truncate max-w-xs sm:max-w-md font-mono text-[11px]">
            {{ state.pipelineStatusMsg.value || '流水线就绪，点击上方启动按钮开始' }}
          </span>
          <div class="flex items-center gap-2">
            <div class="w-28 sm:w-36 bg-stone-800 rounded-full h-2 overflow-hidden border border-stone-700">
              <div
                class="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 transition-all duration-300"
                :style="{ width: `${Math.round(state.pipelineProgressVal.value * 100)}%` }"
              ></div>
            </div>
            <span class="text-xs font-mono font-bold text-cyan-300">{{ Math.round(state.pipelineProgressVal.value * 100) }}%</span>
          </div>
        </div>
      </div>

      <!-- 中间主体双栏分屏控制区 -->
      <div class="flex-1 flex flex-col md:flex-row overflow-hidden">
        <!-- 左栏：动态连线节点图 (35% 宽度) -->
        <section class="w-full md:w-[35%] lg:w-[32%] bg-[#0e131b] border-r border-stone-800/80 p-4 flex flex-col overflow-y-auto">
          <div class="flex items-center justify-between mb-3 text-xs font-semibold text-stone-400 tracking-wider">
            <span>🏭 生产流水线节点拓扑</span>
            <span class="text-[11px] text-cyan-400/80">点击节点查看产物</span>
          </div>

          <!-- 节点拓扑垂直列表 -->
          <div class="relative flex flex-col gap-3 my-auto">
            <!-- 贯穿连接线背景 -->
            <div class="absolute left-6 top-5 bottom-5 w-0.5 bg-stone-800 z-0"></div>
            <!-- 激活状态流动光效线 -->
            <div
              class="absolute left-6 top-5 w-0.5 bg-gradient-to-b from-cyan-400 via-indigo-500 to-emerald-400 z-0 transition-all duration-500"
              :style="{
                height: `${Math.min(100, Math.max(0, (state.pipelineCurrentStageId.value - 1) * 20 + 10))}%`
              }"
            ></div>

            <!-- 6 个节点卡片 -->
            <div
              v-for="stage in state.pipelineStages.value"
              :key="stage.id"
              @click="handleNodeClick(stage.id)"
              :class="[
                'relative z-10 p-3 rounded-xl border transition-all cursor-pointer select-none flex items-start gap-3',
                stage.status === 'running'
                  ? 'bg-cyan-950/40 border-cyan-500/80 shadow-[0_0_15px_rgba(6,182,212,0.25)] ring-1 ring-cyan-400/40'
                  : stage.status === 'retrying'
                  ? 'bg-amber-950/40 border-amber-500/80 shadow-[0_0_15px_rgba(245,158,11,0.25)] ring-1 ring-amber-400/40'
                  : stage.status === 'completed'
                  ? 'bg-emerald-950/20 border-emerald-500/40 hover:border-emerald-400/70 hover:bg-emerald-950/30'
                  : stage.status === 'error'
                  ? 'bg-red-950/30 border-red-500/60'
                  : 'bg-[#121822]/70 border-stone-800/80 hover:border-stone-700 opacity-70'
              ]"
            >
              <!-- 节点圆形图标圈 -->
              <div
                :class="[
                  'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all shrink-0',
                  stage.status === 'running'
                    ? 'bg-cyan-500 text-black shadow-[0_0_10px_rgba(6,182,212,0.8)] animate-pulse'
                    : stage.status === 'retrying'
                    ? 'bg-amber-500 text-black shadow-[0_0_10px_rgba(245,158,11,0.8)] animate-bounce'
                    : stage.status === 'completed'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/60'
                    : stage.status === 'error'
                    ? 'bg-red-500/20 text-red-300 border border-red-400/60'
                    : 'bg-stone-800 text-stone-500 border border-stone-700'
                ]"
              >
                <span v-if="stage.status === 'completed'">✓</span>
                <span v-else-if="stage.status === 'running'">⚡</span>
                <span v-else-if="stage.status === 'retrying'">🔁</span>
                <span v-else-if="stage.status === 'error'">✕</span>
                <span v-else>{{ stage.id }}</span>
              </div>

              <!-- 节点内容说明 -->
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between gap-1">
                  <h4 class="text-xs font-bold text-stone-200 flex items-center gap-1.5">
                    <span>{{ stage.icon }}</span>
                    <span>{{ stage.name }}</span>
                  </h4>
                  <span
                    :class="[
                      'text-[10px] px-2 py-0.5 rounded-full font-mono font-bold border transition-all',
                      stage.status === 'running' ? 'bg-cyan-900 text-cyan-200 border-cyan-400 animate-pulse' :
                      stage.status === 'retrying' ? 'bg-amber-900 text-amber-200 border-amber-400' :
                      stage.status === 'completed' ? 'bg-emerald-950 text-emerald-300 border-emerald-500/60' :
                      stage.status === 'error' ? 'bg-red-950 text-red-300 border-red-500' :
                      'text-stone-500 bg-stone-900 border-stone-800'
                    ]"
                  >
                    {{
                      stage.status === 'completed' ? '✓ 100%' :
                      stage.status === 'running' ? `${Math.round(stage.progress || 0)}%` :
                      stage.status === 'retrying' ? `⚠️ ${Math.round(stage.progress || 0)}%` :
                      stage.status === 'error' ? '✕ 异常' : '0%'
                    }}
                  </span>
                </div>
                <p class="text-[11px] text-stone-400 mt-0.5 truncate">
                  {{ stage.subtitle }}
                </p>
                <!-- 契约与正史直达微标 -->
                <div v-if="stage.id === 1" class="mt-1 flex items-center gap-1.5 text-[10px] text-sky-400 font-mono">
                  <span class="px-1.5 py-0.5 rounded bg-sky-950/80 border border-sky-800/60 font-semibold flex items-center gap-1">
                    <span>🔗</span><span>上章交接契约与因果门禁</span>
                  </span>
                </div>
                <div v-if="stage.id === 5" class="mt-1 flex items-center gap-1.5 text-[10px] text-amber-300 font-mono">
                  <span class="px-1.5 py-0.5 rounded bg-amber-950/80 border border-amber-800/60 font-semibold flex items-center gap-1">
                    <span>🛡️</span><span>朱雀客观雷达 + 微创自纠</span>
                  </span>
                </div>
                <div v-if="stage.id === 6" class="mt-1 flex items-center gap-1.5 text-[10px] text-purple-300 font-mono">
                  <span class="px-1.5 py-0.5 rounded bg-purple-950/80 border border-purple-800/60 font-semibold flex items-center gap-1">
                    <span>📜</span><span>正史设定与下章契约提炼</span>
                  </span>
                </div>
                <div class="w-full bg-stone-900 rounded-full h-1 mt-1.5 overflow-hidden border border-stone-800">
                  <div
                    class="h-full transition-all duration-300 rounded-full"
                    :class="[
                      stage.status === 'completed' ? 'bg-emerald-400' :
                      stage.status === 'running' ? 'bg-gradient-to-r from-cyan-400 to-blue-500' :
                      'bg-stone-800'
                    ]"
                    :style="{ width: `${stage.progress || 0}%` }"
                  ></div>
                </div>

                <!-- 节点完成产物数据小标签 -->
                <div class="mt-1 flex items-center gap-1.5 flex-wrap text-[10px]">
                  <span
                    v-if="stage.id === 2 && draftWordCount > 0"
                    class="px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800/40"
                  >
                    草稿 {{ draftWordCount }} 字
                  </span>
                  <span
                    v-if="stage.id === 3 && polishedWordCount > 0"
                    class="px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800/40"
                  >
                    润色后 {{ polishedWordCount }} 字
                  </span>
                  <span
                    v-if="stage.id === 4 && englishWordCount > 0"
                    class="px-1.5 py-0.5 rounded bg-indigo-950/80 text-indigo-300 border border-indigo-800/40"
                  >
                    英译 {{ englishWordCount }} 词
                  </span>
                  <span
                    v-if="stage.id === 5 && state.pipelineData.value.audit"
                    :class="[
                      'px-1.5 py-0.5 rounded border',
                      state.pipelineData.value.auditPass
                        ? 'bg-emerald-950/80 text-emerald-300 border-emerald-700/50'
                        : 'bg-amber-950/80 text-amber-300 border-amber-700/50'
                    ]"
                  >
                    {{ state.pipelineData.value.auditPass ? '✅ 质检合格' : '⚠️ 质检提示' }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- 右栏：多视窗中央监视器 (65% 宽度) -->
        <main class="w-full md:w-[65%] lg:w-[68%] bg-[#090d13] flex flex-col overflow-hidden">
          <!-- 监视器 Tab 切换栏 -->
          <div class="px-4 py-2.5 bg-[#0e141d] border-b border-stone-800 flex items-center justify-between flex-wrap gap-2">
            <div class="flex items-center gap-1 overflow-x-auto text-xs">
              <button
                @click="state.pipelineActiveTab.value = 'terminal'"
                :class="[
                  'px-3 py-1.5 rounded-lg font-medium transition-all cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
                  state.pipelineActiveTab.value === 'terminal'
                    ? 'bg-cyan-950 text-cyan-300 border border-cyan-700/60 shadow-sm'
                    : 'text-stone-400 hover:text-stone-200 hover:bg-stone-800/60'
                ]"
              >
                <span>🖥️</span>
                <span>实时流水线终端</span>
              </button>

              <button
                @click="state.pipelineActiveTab.value = 'continuity'"
                :class="[
                  'px-3 py-1.5 rounded-lg font-bold transition-all cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
                  state.pipelineActiveTab.value === 'continuity'
                    ? 'bg-sky-950 text-sky-300 border border-sky-500 shadow-[0_0_12px_rgba(14,165,233,0.35)]'
                    : 'text-sky-400 hover:text-sky-200 hover:bg-sky-950/40 border border-sky-900/60'
                ]"
              >
                <span>🔗</span>
                <span>正史因果交接 (Handoff)</span>
                <span class="px-1.5 py-0.2 rounded text-[10px] bg-sky-900/90 text-sky-200 font-mono border border-sky-600/60">连贯核心</span>
                <span
                  v-if="displayCanon || state.handoffData.value"
                  class="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"
                ></span>
              </button>

              <button
                @click="state.pipelineActiveTab.value = 'draft'"
                :class="[
                  'px-3 py-1.5 rounded-lg font-medium transition-all cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
                  state.pipelineActiveTab.value === 'draft'
                    ? 'bg-cyan-950 text-cyan-300 border border-cyan-700/60 shadow-sm'
                    : 'text-stone-400 hover:text-stone-200 hover:bg-stone-800/60'
                ]"
              >
                <span>✍️</span>
                <span>中文草稿</span>
                <span v-if="draftWordCount > 0" class="text-[10px] opacity-75 font-mono">({{ draftWordCount }})</span>
              </button>

              <button
                @click="state.pipelineActiveTab.value = 'polish'"
                :class="[
                  'px-3 py-1.5 rounded-lg font-medium transition-all cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
                  state.pipelineActiveTab.value === 'polish'
                    ? 'bg-cyan-950 text-cyan-300 border border-cyan-700/60 shadow-sm'
                    : 'text-stone-400 hover:text-stone-200 hover:bg-stone-800/60'
                ]"
              >
                <span>🎯</span>
                <span>AI 总编审校</span>
                <span v-if="polishedWordCount > 0" class="text-[10px] opacity-75 font-mono">({{ polishedWordCount }})</span>
              </button>

              <button
                v-if="state.pipelineMode.value === 'bilingual'"
                @click="state.pipelineActiveTab.value = 'translation'"
                :class="[
                  'px-3 py-1.5 rounded-lg font-medium transition-all cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
                  state.pipelineActiveTab.value === 'translation'
                    ? 'bg-indigo-950 text-indigo-300 border border-indigo-700/60 shadow-sm'
                    : 'text-stone-400 hover:text-stone-200 hover:bg-stone-800/60'
                ]"
              >
                <span>🇺🇸</span>
                <span>美式英文译稿</span>
                <span v-if="englishWordCount > 0" class="text-[10px] opacity-75 font-mono">({{ englishWordCount }}w)</span>
              </button>

              <button
                v-if="state.pipelineMode.value === 'bilingual'"
                @click="state.pipelineActiveTab.value = 'audit'"
                :class="[
                  'px-3 py-1.5 rounded-lg font-medium transition-all cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
                  state.pipelineActiveTab.value === 'audit'
                    ? 'bg-amber-950 text-amber-300 border border-amber-700/60 shadow-sm'
                    : 'text-stone-400 hover:text-stone-200 hover:bg-stone-800/60'
                ]"
              >
                <span>🛡️</span>
                <span>双语质检审校</span>
                <span
                  v-if="state.pipelineData.value.audit"
                  class="w-2 h-2 rounded-full"
                  :class="state.pipelineData.value.auditPass ? 'bg-emerald-400' : 'bg-amber-400'"
                ></span>
              </button>

              <button
                @click="state.pipelineActiveTab.value = 'archive'"
                :class="[
                  'px-3 py-1.5 rounded-lg font-medium transition-all cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
                  state.pipelineActiveTab.value === 'archive'
                    ? 'bg-stone-800 text-stone-200 border border-stone-600 shadow-sm'
                    : 'text-stone-400 hover:text-stone-200 hover:bg-stone-800/60'
                ]"
              >
                <span>📦</span>
                <span>记忆归档</span>
              </button>
            </div>

            <!-- 右侧快捷复制与导出 -->
            <div class="flex items-center gap-2 text-xs">
              <span v-if="copySuccessMsg" class="text-emerald-400 font-semibold animate-pulse">
                {{ copySuccessMsg }}
              </span>
            </div>
          </div>

          <!-- 各 Tab 监视区视口 -->
          <div class="flex-1 p-4 overflow-y-auto font-sans leading-relaxed">
            <!-- 视口 1: 实时终端监视器 -->
            <div
              v-show="state.pipelineActiveTab.value === 'terminal'"
              ref="terminalContainer"
              class="h-full bg-black/60 rounded-xl p-4 border border-stone-800/80 font-mono text-xs overflow-y-auto flex flex-col space-y-1.5 text-stone-300"
            >
              <div class="text-cyan-400 font-semibold pb-1 border-b border-stone-800 flex items-center justify-between">
                <span>[TERMINAL FEED :: 第 {{ state.chapterNum.value }} 章全自动生产实时流水线]</span>
                <span class="text-stone-500 font-normal">Buffer size: {{ state.pipelineTerminalLogs.value.length }}</span>
              </div>
              <div v-if="state.pipelineTerminalLogs.value.length === 0" class="text-stone-600 italic py-4">
                等待启动流水线...
              </div>
              <div
                v-for="(log, i) in state.pipelineTerminalLogs.value"
                :key="i"
                :class="[
                  'transition-all',
                  log.includes('✅') || log.includes('通过') ? 'text-emerald-400' :
                  log.includes('❌') || log.includes('失败') || log.includes('异常') ? 'text-red-400 font-bold' :
                  log.includes('⚠️') || log.includes('自纠') || log.includes('重译') ? 'text-amber-400' :
                  log.includes('🚀') || log.includes('启动') ? 'text-cyan-300 font-semibold' :
                  'text-stone-300'
                ]"
              >
                {{ log }}
              </div>
            </div>

            <!-- 视口 2: 中文草稿 -->
            <div v-show="state.pipelineActiveTab.value === 'draft'" class="h-full flex flex-col">
              <div class="flex items-center justify-between mb-3 pb-2 border-b border-stone-800">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-bold text-stone-200">第 {{ state.chapterNum.value }} 章 · 中文分场景草稿</span>
                  <span class="text-xs px-2 py-0.5 rounded bg-stone-800 text-stone-300 font-mono">
                    {{ draftWordCount }} 字
                  </span>
                </div>
                <div class="flex items-center gap-2">
                  <button
                    @click="copyToClipboard(state.pipelineData.value.draft, '中文草稿')"
                    :disabled="!state.pipelineData.value.draft"
                    class="px-2.5 py-1 text-xs rounded bg-stone-800 hover:bg-stone-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
                  >
                    📋 复制草稿
                  </button>
                  <button
                    @click="downloadText(state.pipelineData.value.draft, `chapter_${state.chapterNum.value}_raw_draft.txt`)"
                    :disabled="!state.pipelineData.value.draft"
                    class="px-2.5 py-1 text-xs rounded bg-stone-800 hover:bg-stone-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
                  >
                    📥 导出 TXT
                  </button>
                </div>
              </div>
              <div v-if="!state.pipelineData.value.draft" class="text-stone-500 italic py-8 text-center">
                草稿阶段尚未生成或正在排队起草中...
              </div>
              <div v-else class="flex-1 bg-stone-900/40 rounded-xl p-5 border border-stone-800 overflow-y-auto whitespace-pre-wrap font-serif text-sm leading-relaxed text-stone-200">
                {{ state.pipelineData.value.draft }}
              </div>
            </div>

            <!-- 视口 3: AI 总编审校与修改清单 -->
            <div v-show="state.pipelineActiveTab.value === 'polish'" class="h-full flex flex-col">
              <div class="flex items-center justify-between mb-3 pb-2 border-b border-stone-800 flex-wrap gap-2">
                <!-- 子 Tab 切换 -->
                <div class="flex items-center gap-2 bg-stone-900 p-1 rounded-lg border border-stone-800 text-xs">
                  <button
                    @click="polishSubTab = 'text'"
                    :class="[
                      'px-3 py-1 rounded font-semibold transition-all cursor-pointer',
                      polishSubTab === 'text' ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/60 shadow-sm' : 'text-stone-400 hover:text-stone-200'
                    ]"
                  >
                    ✨ 审校定稿正文 ({{ polishedWordCount }} 字)
                  </button>
                  <button
                    @click="polishSubTab = 'checklist'"
                    :class="[
                      'px-3 py-1 rounded font-semibold transition-all cursor-pointer',
                      polishSubTab === 'checklist' ? 'bg-emerald-950 text-emerald-300 border border-emerald-800/60 shadow-sm' : 'text-stone-400 hover:text-stone-200'
                    ]"
                  >
                    📋 修改清单
                  </button>
                </div>

                <div class="flex items-center gap-2">
                  <button
                    @click="copyToClipboard(polishSubTab === 'text' ? state.pipelineData.value.polished : state.pipelineData.value.checklist, polishSubTab === 'text' ? '润色正文' : '修改清单')"
                    :disabled="!state.pipelineData.value.polished"
                    class="px-2.5 py-1 text-xs rounded bg-stone-800 hover:bg-stone-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
                  >
                    📋 复制此视图
                  </button>
                  <button
                    @click="downloadText(state.pipelineData.value.polished, `chapter_${state.chapterNum.value}_polished.txt`)"
                    :disabled="!state.pipelineData.value.polished"
                    class="px-2.5 py-1 text-xs rounded bg-stone-800 hover:bg-stone-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
                  >
                    📥 导出润色稿
                  </button>
                </div>
              </div>

              <!-- 润色正文视口 -->
              <div
                v-if="polishSubTab === 'text'"
                class="flex-1 bg-stone-900/40 rounded-xl p-5 border border-stone-800 overflow-y-auto whitespace-pre-wrap font-serif text-sm leading-relaxed text-stone-200"
              >
                <div v-if="!state.pipelineData.value.polished" class="text-stone-500 italic py-8 text-center">
                  审校润色阶段尚未启动或正由 Gemini 4 Hydrogen 精雕细琢中...
                </div>
                <template v-else>
                  {{ state.pipelineData.value.polished }}
                </template>
              </div>

              <!-- 修改清单视口 -->
              <div
                v-else-if="polishSubTab === 'checklist'"
                class="flex-1 bg-stone-900/60 rounded-xl p-5 border border-stone-800 overflow-y-auto whitespace-pre-wrap font-mono text-xs leading-relaxed text-emerald-300"
              >
                <div v-if="!state.pipelineData.value.checklist" class="text-stone-500 italic py-8 text-center">
                  修改清单待提取...
                </div>
                <template v-else>
                  {{ state.pipelineData.value.checklist }}
                </template>
              </div>
            </div>

            <!-- 视口 4: 美式英文译稿 -->
            <div v-show="state.pipelineActiveTab.value === 'translation'" class="h-full flex flex-col">
              <div class="flex items-center justify-between mb-3 pb-2 border-b border-stone-800 flex-wrap gap-2">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-bold text-cyan-300">Chapter {{ state.pipelineTargetChapter.value || state.chapterNum.value }} · Overseas Native English</span>
                  <span class="text-xs px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800/50 font-mono font-bold">
                    {{ englishWordCount }} Words
                  </span>
                  <span class="text-xs px-2 py-0.5 rounded bg-stone-800 text-stone-400">
                    Standard: {{ state.translateStyle.value }}
                  </span>
                </div>
                <div class="flex items-center gap-2 flex-wrap">
                  <button
                    @click="copyTranslationWithTitle()"
                    :disabled="!displayTranslation"
                    class="px-3 py-1 text-xs rounded-lg bg-emerald-600 hover:bg-emerald-500 font-bold text-white shadow transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed active:scale-95"
                    title="一键复制【英文标题 + 整篇英文正文】"
                  >
                    📑 复制标题+英文正文
                  </button>
                  <button
                    @click="copyToClipboard(currentTitleEn, '英文标题')"
                    class="px-2.5 py-1 text-xs rounded bg-indigo-950 hover:bg-indigo-900 text-indigo-200 border border-indigo-700/60 transition-colors cursor-pointer"
                    title="仅复制英文章名"
                  >
                    🏷️ 英文标题
                  </button>
                  <button
                    @click="copyToClipboard(displayTranslation, '美式英文正文')"
                    :disabled="!displayTranslation"
                    class="px-2.5 py-1 text-xs rounded bg-stone-800 hover:bg-stone-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
                    title="仅复制英文正文"
                  >
                    📋 仅正文
                  </button>
                  <button
                    @click="downloadText(`${currentTitleEn}\n\n${displayTranslation}`, `chapter_${state.pipelineTargetChapter.value || state.chapterNum.value}_en.txt`)"
                    :disabled="!displayTranslation"
                    class="px-2.5 py-1 text-xs rounded bg-stone-800 hover:bg-stone-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
                    title="导出纯英文 TXT（首行含英文标题）"
                  >
                    📥 导出 TXT
                  </button>
                </div>
              </div>
              <div v-if="!displayTranslation" class="text-stone-500 italic py-8 text-center">
                英文译制阶段待执行...
              </div>
              <div v-else class="flex-1 bg-indigo-950/20 rounded-xl p-5 border border-indigo-900/40 overflow-y-auto whitespace-pre-wrap font-sans text-sm leading-relaxed text-stone-200">
                {{ displayTranslation }}
              </div>
            </div>

            <!-- 视口 5: 独立双语质检报告 -->
            <div v-show="state.pipelineActiveTab.value === 'audit'" class="h-full flex flex-col">
              <!-- 质检结论横幅 -->
              <div
                v-if="state.pipelineData.value.audit"
                :class="[
                  'px-4 py-3 rounded-xl border mb-3 flex items-center justify-between flex-wrap gap-2',
                  state.pipelineData.value.auditPass
                    ? 'bg-emerald-950/60 border-emerald-500/60 text-emerald-200'
                    : 'bg-amber-950/60 border-amber-500/60 text-amber-200'
                ]"
              >
                <div class="flex items-center gap-2.5">
                  <span class="text-xl">{{ state.pipelineData.value.auditPass ? '🛡️' : '⚠️' }}</span>
                  <div>
                    <h4 class="text-sm font-bold">
                      {{ state.pipelineData.value.auditPass ? '双语独立质检审校通过' : '双语独立审校完成（检出需关注/建议复查项）' }}
                    </h4>
                    <p class="text-xs opacity-80 mt-0.5">
                      {{ state.pipelineData.value.retryOccurred ? '系统此前已自动触发针对性自纠重译并完成复审' : '双语语义对照质检完成' }}
                    </p>
                  </div>
                </div>
                <div class="flex items-center gap-2">
                  <button
                    @click="state.doAuditTranslation()"
                    class="px-3 py-1 text-xs rounded bg-stone-800 hover:bg-stone-700 text-stone-200 transition-colors cursor-pointer"
                  >
                    🔄 重新质检一次
                  </button>
                  <button
                    @click="copyToClipboard(state.pipelineData.value.audit, '双语质检报告')"
                    class="px-3 py-1 text-xs rounded bg-stone-800 hover:bg-stone-700 text-stone-200 transition-colors cursor-pointer"
                  >
                    📋 复制质检报告
                  </button>
                </div>
              </div>

              <div v-if="!state.pipelineData.value.audit" class="text-stone-500 italic py-8 text-center">
                双语独立质检审查报告生成中或尚未启动...
              </div>
              <div
                v-else
                class="flex-1 bg-stone-900/50 rounded-xl p-5 border border-stone-800 overflow-y-auto whitespace-pre-wrap font-mono text-xs leading-relaxed text-amber-200/90"
              >
                {{ state.pipelineData.value.audit }}
              </div>
            </div>

            <!-- 视口 6: 记忆同步与全书归档 -->
            <div v-show="state.pipelineActiveTab.value === 'archive'" class="h-full flex flex-col space-y-4">
              <div class="flex items-center justify-between pb-2 border-b border-stone-800">
                <span class="text-sm font-bold text-stone-200">第 {{ state.chapterNum.value }} 章全书记忆状态更新归档</span>
                <span class="text-xs px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800/40">
                  多态持久化就绪
                </span>
              </div>

              <!-- 全局前文摘要卡片 -->
              <div class="bg-stone-900/50 p-4 rounded-xl border border-stone-800">
                <h5 class="text-xs font-bold text-cyan-300 mb-1 flex items-center gap-1.5">
                  <span>📜</span>
                  <span>全书最新摘要快照 (global_summary.txt)</span>
                </h5>
                <p class="text-xs text-stone-400 whitespace-pre-wrap font-serif leading-relaxed max-h-40 overflow-y-auto">
                  {{ state.pipelineData.value.summary || '已将本章冲突核心与进展自动提炼并压缩至全局摘要' }}
                </p>
              </div>

              <!-- 角色动态状态卡片 -->
              <div class="bg-stone-900/50 p-4 rounded-xl border border-stone-800">
                <h5 class="text-xs font-bold text-amber-300 mb-1 flex items-center gap-1.5">
                  <span>👥</span>
                  <span>角色状态与心境追踪 (character_state.txt)</span>
                </h5>
                <p class="text-xs text-stone-400 whitespace-pre-wrap font-serif leading-relaxed max-h-44 overflow-y-auto">
                  {{ state.pipelineData.value.characterState || '已同步主角与反派在本章末尾的心境、隐患与关系转变' }}
                </p>
              </div>

              <!-- 归档文件路径提示 -->
              <div class="bg-[#0b1016] p-3 rounded-lg border border-stone-800 text-[11px] text-stone-400 flex items-center justify-between">
                <div>
                  <span>📂 物理持久化目录：</span>
                  <code class="text-cyan-400">chapters/chapter_{{ state.chapterNum.value }}.txt</code>
                  <span class="mx-1">&</span>
                  <code class="text-indigo-400">chapters_en/chapter_{{ state.chapterNum.value }}_en.txt</code>
                </div>
                <span class="text-emerald-400">✅ 磁盘已同步</span>
              </div>
            </div>

            <!-- 视口 7: 正史设定演进与幕间因果交接 (Semantic Handoff & Canon History) -->
            <div v-show="state.pipelineActiveTab.value === 'continuity'" class="h-full flex flex-col space-y-3 overflow-y-auto pr-1">
              <div class="flex items-center justify-between pb-2 border-b border-stone-800 flex-wrap gap-2">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-bold text-sky-300">🔗 全链路因果连续性与正史设定监视器</span>
                  <span class="text-[10px] px-2 py-0.5 rounded-full bg-sky-950 text-sky-300 border border-sky-800/50">
                    第 {{ state.chapterNum.value }} 章 ➔ 第 {{ state.chapterNum.value + 1 }} 章闭环
                  </span>
                </div>
                <div class="flex items-center gap-2 flex-wrap">
                  <button
                    @click="state.doColdStartBackfill()"
                    :disabled="state.coldStartLoading.value"
                    class="px-2.5 py-1 text-xs rounded bg-sky-900/70 hover:bg-sky-800 text-sky-200 border border-sky-600/60 transition-colors cursor-pointer flex items-center gap-1"
                    title="依据前文正文提取生成因果交接契约"
                  >
                    <span>⚡</span>
                    <span>{{ state.coldStartLoading.value ? '提炼中...' : '冷启动一键回溯交接' }}</span>
                  </button>
                  <button
                    @click="state.doPreWriteGateCheck()"
                    :disabled="state.preWriteGateLoading.value"
                    class="px-2.5 py-1 text-xs rounded bg-indigo-900/70 hover:bg-indigo-800 text-indigo-200 border border-indigo-600/60 transition-colors cursor-pointer flex items-center gap-1"
                    title="检查本章细纲与草稿是否违背前文交接与套话禁令"
                  >
                    <span>🛡️</span>
                    <span>{{ state.preWriteGateLoading.value ? '门禁自检中...' : '因果门禁自检' }}</span>
                  </button>
                  <button
                    @click="fetchCanonHistory(); state.loadHandoff(state.chapterNum.value > 1 ? state.chapterNum.value - 1 : 1)"
                    class="px-2.5 py-1 text-xs rounded bg-stone-800 hover:bg-stone-700 text-stone-300 transition-colors cursor-pointer flex items-center gap-1"
                  >
                    <span>🔄</span>
                    <span>刷新</span>
                  </button>
                  <button
                    v-if="displayCanon"
                    @click="copyToClipboard(displayCanon, '正史设定页')"
                    class="px-2.5 py-1 text-xs rounded bg-sky-900/60 hover:bg-sky-800 text-sky-200 border border-sky-700/50 transition-colors cursor-pointer"
                  >
                    📋 复制正史
                  </button>
                </div>
              </div>

              <!-- 卡片 1: 幕间因果交接（Semantic Handoff）契约 -->
              <div class="bg-gradient-to-r from-indigo-950/40 via-sky-950/30 to-indigo-950/40 p-4 rounded-xl border border-sky-800/40 space-y-2.5">
                <div class="flex items-center justify-between">
                  <h5 class="text-xs font-bold text-sky-200 flex items-center gap-2">
                    <span class="text-base">📋</span>
                    <span>【本章留给下一章的因果交接契约（Semantic Handoff）】</span>
                    <span class="text-[10px] font-normal text-sky-400">流水线在 Stage 6 归档时自动提炼并持久化</span>
                  </h5>
                  <span v-if="state.handoffData.value" class="text-[10px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800/40">
                    已就绪
                  </span>
                </div>

                <div v-if="state.handoffData.value" class="space-y-2 text-xs">
                  <div class="p-2.5 bg-black/40 rounded-lg border border-sky-900/30">
                    <span class="text-sky-300 font-semibold">1. 核心实锤事实转变：</span>
                    <p class="text-stone-300 mt-0.5">{{ state.handoffData.value.what_changed || '已承接本章推进' }}</p>
                  </div>
                  <div class="p-2.5 bg-black/40 rounded-lg border border-sky-900/30">
                    <span class="text-amber-300 font-semibold">2. 下一章核心即时意图：</span>
                    <p class="text-stone-300 mt-0.5">{{ state.handoffData.value.active_intentions || '接续当前情节继续推进' }}</p>
                  </div>
                  <div v-if="state.handoffData.value.must_not_restate && state.handoffData.value.must_not_restate.length" class="p-2.5 bg-rose-950/30 rounded-lg border border-rose-900/40">
                    <span class="text-rose-300 font-semibold">3. 🚫 开篇绝密禁令（读者已知，严禁下章开篇旁白重复科普水字数）：</span>
                    <ul class="list-disc list-inside text-rose-200/90 mt-1 space-y-0.5 pl-1">
                      <li v-for="(item, idx) in state.handoffData.value.must_not_restate" :key="idx">{{ item }}</li>
                    </ul>
                  </div>
                  <div v-if="state.handoffData.value.worn_phrases && state.handoffData.value.worn_phrases.length" class="p-2 bg-amber-950/30 rounded-lg border border-amber-900/30 text-amber-200/90">
                    <span class="font-semibold text-amber-300">4. 🚫 跨章套路词黑名单：</span>
                    <span>{{ state.handoffData.value.worn_phrases.join('、') }}</span>
                  </div>
                  <div v-if="state.handoffData.value.chapter_tail" class="p-2 bg-black/60 rounded border border-stone-800 text-[11px] font-mono text-stone-400">
                    <span class="text-stone-500">5. 物理尾声锚点（下一章开篇接续此句）：</span>
                    <span>"...{{ state.handoffData.value.chapter_tail.slice(-200) }}"</span>
                  </div>
                </div>
                <div v-else class="text-stone-500 italic py-3 text-center text-xs">
                  暂无当前交接数据。全自动流水线运行到 Stage 6 归档时将自动提炼并展示在此。
                </div>
              </div>

              <!-- 卡片 2: 正史设定页演进与事实边界（Novel_canon_history.txt） -->
              <div class="bg-stone-900/60 p-4 rounded-xl border border-stone-800 space-y-2">
                <div class="flex items-center justify-between">
                  <h5 class="text-xs font-bold text-purple-300 flex items-center gap-1.5">
                    <span>📜</span>
                    <span>【正史设定页事实边界与变更记录 (Novel_canon_history.txt)】</span>
                  </h5>
                  <span class="text-[10px] text-purple-400">只认实锤正文 · 冲突单列受控</span>
                </div>

                <div v-if="displayCanon" class="whitespace-pre-wrap font-mono text-xs leading-relaxed text-stone-300 bg-black/50 p-3.5 rounded-lg border border-stone-800 max-h-96 overflow-y-auto">
                  {{ displayCanon }}
                </div>
                <div v-else class="text-stone-500 italic py-4 text-center text-xs">
                  正史设定页尚未生成。全自动流水线完成 Stage 6.2 时将自动展示本章事实变更与最新正史页。
                </div>
              </div>

              <!-- 卡片 3: 固定写法表与专有名词统一（仅英文出海模式启用，纯中文流水线完全隔离） -->
              <div v-if="state.pipelineMode.value === 'bilingual'" class="bg-indigo-950/20 p-4 rounded-xl border border-indigo-900/40 space-y-2.5">
                <div class="flex items-center justify-between">
                  <h5 class="text-xs font-bold text-indigo-300 flex items-center gap-1.5">
                    <span>📖</span>
                    <span>【固定写法表（一词一译专有对照 · 随书增补）】</span>
                  </h5>
                  <div class="flex items-center gap-2">
                    <button
                      @click="state.loadFixedTerms()"
                      class="px-2.5 py-1 text-xs rounded bg-stone-800 hover:bg-stone-700 text-stone-300 transition-colors cursor-pointer"
                    >
                      🔄 刷新词表
                    </button>
                    <button
                      @click="state.saveFixedTerms()"
                      class="px-2.5 py-1 text-xs rounded bg-indigo-900/80 hover:bg-indigo-800 text-indigo-200 border border-indigo-700/60 transition-colors cursor-pointer"
                    >
                      💾 保存词表
                    </button>
                  </div>
                </div>
                <textarea
                  v-model="state.fixedTermsContent.value"
                  rows="6"
                  placeholder="载入中或尚未配置固定写法表..."
                  class="w-full bg-black/50 border border-stone-800 rounded p-2.5 text-stone-300 font-mono text-xs leading-relaxed focus:outline-none focus:border-indigo-500"
                ></textarea>
                <div class="text-[11px] text-stone-500">
                  严禁自创同义词。全自动流水线生成、AI 总编审校、出海英文译制与独立双语质检全流程强校验此表。
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>

      <!-- 底部控制舱固定状态脚标 -->
      <footer class="px-5 py-2.5 bg-[#090d13] border-t border-stone-800/80 flex items-center justify-between text-xs text-stone-500">
        <div class="flex items-center gap-2">
          <span>🧠 写作流水线引擎 (3.8 Flash 起草 · 4 Hydrogen 审校)</span>
          <span class="text-stone-700">|</span>
          <span class="text-stone-400">
            {{ state.pipelineMode.value === 'fast_zh'
              ? '纯中文 4 步流水线：细纲装配 ➔ 3.8 Flash 起草 ➔ 4 Hydrogen 审校 ➔ 正史归档（与英文出海流水线完全隔离）'
              : '英文出海 6 步流水线：起草 ➔ 审校 ➔ 美式译制 ➔ 双语质检 ➔ 固定词表与正史归档' }}
          </span>
        </div>
        <div class="flex items-center gap-3">
          <button
            @click="state.closePipelineControlRoom()"
            class="px-3 py-1 rounded bg-stone-800 hover:bg-stone-700 text-stone-300 transition-colors cursor-pointer"
          >
            返回主工作台
          </button>
        </div>
      </footer>
    </div>
  </div>
</template>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.98); }
  to { opacity: 1; transform: scale(1); }
}
.animate-fadeIn {
  animation: fadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
</style>
