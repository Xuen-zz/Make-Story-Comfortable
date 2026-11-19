<script setup lang="ts">
import { computed } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'

export type WorkshopStage = 'stage1' | 'stage2' | 'stage3' | 'stage4'

export interface DashboardAssetInfo {
  exists: boolean
  chars: number
  label: string
  file: string
  total_chapters?: number
  planned_chapters?: number
}

export interface DashboardChapterItem {
  num: number
  title: string
  title_en?: string
  has_draft: boolean
  chars: number
  has_final: boolean
  has_en: boolean
  en_words: number
  has_outline: boolean
}

export interface DashboardPayload {
  project_name: string
  filepath: string
  assets: Record<string, DashboardAssetInfo>
  chapters: DashboardChapterItem[]
}

const props = defineProps<{
  state: ReturnType<typeof useWorkshopState>
  activeStage: WorkshopStage
  dashboard: DashboardPayload | null
}>()

const emit = defineEmits<{
  (e: 'update:activeStage', stage: WorkshopStage): void
}>()

const hasArch = computed(() =>
  Boolean(props.dashboard?.assets?.architecture?.exists || props.state.arch.value.result || props.state.seedText.value),
)

const bpChapters = computed(() =>
  props.dashboard?.assets?.blueprint?.total_chapters || 0,
)

const hasBp = computed(() =>
  Boolean(props.dashboard?.assets?.blueprint?.exists || props.state.bp.value.result),
)

const plannedOutlines = computed(() =>
  props.dashboard?.assets?.detailed_outline?.planned_chapters || 0,
)

const writtenStats = computed(() => {
  const list = props.dashboard?.chapters ?? []
  let written = 0
  let finalized = 0
  let totalWords = 0
  for (const ch of list) {
    if (ch.has_final || ch.has_draft || ch.chars > 0) {
      written++
      totalWords += ch.chars || 0
    }
    if (ch.has_final) finalized++
  }
  return { written, finalized, totalWords }
})

const targetTotalWords = computed(() =>
  Math.max(1, (props.state.numChapters.value || 200) * (props.state.wordNumber.value || 2500)),
)

const wordProgressPct = computed(() =>
  Math.min(100, Math.round((writtenStats.value.totalWords / targetTotalWords.value) * 1000) / 10),
)

const targetWan = computed(() => (targetTotalWords.value / 10000).toFixed(1))
const writtenWan = computed(() => (writtenStats.value.totalWords / 10000).toFixed(2))

const steps = computed(() => [
  {
    id: 'stage1' as WorkshopStage,
    num: 1,
    icon: '🏛️',
    title: '立项与架构',
    desc: `${props.state.genre.value || '未设题材'} · 目标 ${targetWan.value}万字`,
    done: hasArch.value,
    running: props.state.arch.value.running || props.state.fastIncubating.value,
    statusText: props.state.arch.value.running || props.state.fastIncubating.value
      ? '推演中'
      : hasArch.value
        ? '已就绪'
        : '待立项',
  },
  {
    id: 'stage2' as WorkshopStage,
    num: 2,
    icon: '🗺️',
    title: `全书目录 (${props.state.numChapters.value}章)`,
    desc: bpChapters.value > 0
      ? `已生成 ${bpChapters.value} / ${props.state.numChapters.value} 章目录`
      : `分批规划 ${props.state.numChapters.value} 章大纲节奏`,
    done: hasBp.value,
    running: props.state.bp.value.running,
    statusText: props.state.bp.value.running
      ? '生成中'
      : hasBp.value
        ? `${bpChapters.value} 章`
        : '待生成',
  },
  {
    id: 'stage3' as WorkshopStage,
    num: 3,
    icon: '📑',
    title: '分批细纲审核',
    desc: plannedOutlines.value > 0
      ? `已规划 ${plannedOutlines.value} 章细纲 · 滚动10章/批`
      : '生成并人工审核 1-10 章等滚动细纲',
    done: plannedOutlines.value > 0,
    running: props.state.detailedOutline.value.running || props.state.outlineRevision.value.running,
    statusText: props.state.detailedOutline.value.running
      ? '推演中'
      : plannedOutlines.value > 0
        ? `已备 ${plannedOutlines.value} 章`
        : '待审核',
  },
  {
    id: 'stage4' as WorkshopStage,
    num: 4,
    icon: '📋',
    title: '批量写审生产看板',
    desc: props.state.batchQueueRunning.value
      ? `队列生产第 ${props.state.batchQueueCurrent.value} 章 (${props.state.batchQueueStart.value}-${props.state.batchQueueEnd.value})`
      : `3.8 Flash写 ➔ 4 Hydrogen审 · 已写 ${writtenStats.value.written} 章`,
    done: writtenStats.value.finalized > 0,
    running: props.state.pipelineRunning.value || props.state.batchQueueRunning.value,
    statusText: props.state.pipelineRunning.value
      ? `生产中 ${Math.round(props.state.pipelineProgressVal.value * 100)}%`
      : `定稿 ${writtenStats.value.finalized} 章`,
  },
])
</script>

<template>
  <div class="rounded-2xl border border-[var(--color-parchment-darker)] bg-white shadow-xs p-3.5 sm:p-4 space-y-3">
    <!-- 4 步工单主流程导航 -->
    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-2.5">
      <button
        v-for="(st, idx) in steps"
        :key="st.id"
        type="button"
        @click="emit('update:activeStage', st.id)"
        class="relative text-left rounded-xl p-3 border-2 transition-all cursor-pointer group flex items-start gap-3"
        :class="
          activeStage === st.id
            ? 'border-zinc-300 bg-[#1e2129] shadow-sm ring-1 ring-white/15'
            : st.done
              ? 'border-emerald-500/40 bg-[#131d19] hover:border-emerald-400/70 hover:bg-[#17231e]'
              : 'border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/80 hover:border-zinc-500 hover:bg-[var(--color-parchment-dark)]'
        "
      >
        <div
          class="w-9 h-9 rounded-xl flex items-center justify-center text-base font-bold shrink-0 transition-transform group-hover:scale-105"
          :class="
            st.running
              ? 'bg-emerald-500 text-zinc-950 animate-pulse'
              : activeStage === st.id
                ? 'bg-zinc-100 text-zinc-950 shadow-xs'
                : st.done
                  ? 'bg-emerald-600 text-white'
                  : 'bg-[var(--color-parchment-dark)] text-[var(--color-ink-light)]'
          "
        >
          <span v-if="st.running">⚡</span>
          <span v-else-if="st.done && activeStage !== st.id">✓</span>
          <span v-else>{{ st.num }}</span>
        </div>

        <div class="min-w-0 flex-1">
          <div class="flex items-center justify-between gap-1.5">
            <span class="font-bold text-sm text-[var(--color-ink)] truncate">
              {{ st.icon }} {{ st.title }}
            </span>
            <span
              class="text-[10px] px-1.5 py-0.5 rounded-full font-semibold shrink-0"
              :class="
                st.running
                  ? 'bg-emerald-500/20 text-emerald-300'
                  : st.done
                    ? 'bg-emerald-500/15 text-emerald-300'
                    : 'bg-zinc-800 text-zinc-400'
              "
            >
              {{ st.statusText }}
            </span>
          </div>
          <p class="text-xs text-[var(--color-ink-light)] mt-1 truncate">
            {{ st.desc }}
          </p>
        </div>

        <span
          v-if="idx < steps.length - 1"
          class="hidden xl:flex absolute -right-3 top-1/2 -translate-y-1/2 z-10 w-5 h-5 rounded-full bg-[#15171c] border border-[var(--color-parchment-darker)] items-center justify-center text-[10px] text-zinc-400 shadow-xs pointer-events-none"
        >
          ➔
        </span>
      </button>
    </div>

    <!-- 全书进度条与模型说明 -->
    <div class="flex items-center justify-between flex-wrap gap-3 pt-2 border-t border-[var(--color-parchment-dark)] text-xs">
      <div class="flex items-center gap-3 flex-1 min-w-[240px]">
        <span class="font-semibold text-zinc-200 whitespace-nowrap">
          📈 全书累计
        </span>
        <div class="flex-1 h-2.5 bg-[var(--color-parchment-dark)] rounded-full overflow-hidden max-w-md">
          <div
            class="h-full rounded-full transition-all duration-500 bg-emerald-500"
            :style="{ width: `${Math.max(writtenStats.totalWords > 0 ? 2 : 0, wordProgressPct)}%` }"
          />
        </div>
        <span class="font-mono text-[var(--color-ink)] font-semibold whitespace-nowrap">
          {{ writtenWan }} / {{ targetWan }} 万字
          <span class="text-[var(--color-ink-light)] font-normal">
            ({{ writtenStats.written }}/{{ state.numChapters.value }} 章)
          </span>
        </span>
      </div>

      <div class="flex items-center gap-2 text-[11px] flex-wrap">
        <span class="px-2.5 py-0.5 rounded-full bg-zinc-800/80 border border-zinc-700 text-zinc-200 font-medium">
          ✍️ 写稿引擎：{{ state.llmConfig.value || 'Gemini 3.8 Flash' }}
        </span>
        <span class="px-2.5 py-0.5 rounded-full bg-emerald-950/60 border border-emerald-700/50 text-emerald-300 font-medium">
          🛡️ 去AI审校：Gemini 4 Hydrogen (Medium)
        </span>
      </div>
    </div>
  </div>
</template>
