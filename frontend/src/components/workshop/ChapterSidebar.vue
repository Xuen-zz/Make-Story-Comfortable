<script setup lang="ts">
import { ref, computed } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'
import type { DashboardChapterItem } from './WorkflowStepper.vue'

const props = defineProps<{
  state: ReturnType<typeof useWorkshopState>
  chapters: DashboardChapterItem[]
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
}>()

const filter = ref<'all' | 'written' | 'unwritten'>('all')
const searchText = ref('')
const jumpNum = ref<number | null>(null)

const mergedChapters = computed(() => {
  const byNum = new Map<number, DashboardChapterItem>()
  for (const ch of props.chapters) {
    byNum.set(ch.num, ch)
  }
  const maxPlan = Math.max(
    props.state.numChapters.value || 200,
    props.chapters.length ? Math.max(...props.chapters.map((c) => c.num)) : 1,
  )
  const list: DashboardChapterItem[] = []
  for (let i = 1; i <= maxPlan; i++) {
    const found = byNum.get(i)
    if (found) {
      list.push(found)
    } else {
      list.push({
        num: i,
        title: `第 ${i} 章（待规划/待写）`,
        has_draft: false,
        chars: 0,
        has_final: false,
        has_en: false,
        en_words: 0,
        has_outline: false,
      })
    }
  }
  return list
})

const filteredList = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  return mergedChapters.value.filter((ch) => {
    const isWritten = ch.has_final || ch.has_draft || ch.chars > 0
    if (filter.value === 'written' && !isWritten) return false
    if (filter.value === 'unwritten' && isWritten) return false
    if (q) {
      const matchNum = String(ch.num).includes(q) || `第${ch.num}章`.includes(q)
      const matchTitle = ch.title?.toLowerCase().includes(q)
      return matchNum || matchTitle
    }
    return true
  })
})

function onJump() {
  if (!jumpNum.value || jumpNum.value < 1) return
  props.state.selectChapter(jumpNum.value)
}
</script>

<template>
  <aside class="rounded-2xl border border-[var(--color-parchment-darker)] bg-white shadow-sm flex flex-col overflow-hidden h-[760px]">
    <!-- 顶部控制 -->
    <div class="p-3 bg-[var(--color-parchment)]/60 border-b border-[var(--color-parchment-darker)] space-y-2.5">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-1.5">
          <span class="text-base">📚</span>
          <h3 class="font-bold text-sm text-[var(--color-ink)]">章节导航</h3>
          <span class="text-[11px] font-mono text-[var(--color-ink-light)]">({{ state.numChapters.value }}章)</span>
        </div>
        <div class="flex items-center gap-1">
          <button
            @click="state.openQuickReader()"
            type="button"
            class="px-2 py-0.5 text-[11px] rounded bg-amber-100 hover:bg-amber-200 text-amber-900 font-semibold cursor-pointer"
            title="弹窗对照查阅其他章节"
          >
            📖 查阅
          </button>
          <button
            @click="emit('refresh')"
            type="button"
            class="px-1.5 py-0.5 text-[11px] rounded border border-[var(--color-parchment-darker)] hover:bg-white cursor-pointer"
            title="刷新章节状态"
          >
            <span :class="{ 'animate-spin inline-block': loading }">🔄</span>
          </button>
        </div>
      </div>

      <!-- 快捷切章 + 跳转 -->
      <div class="flex items-center gap-1.5">
        <button
          @click="state.prevChapter()"
          :disabled="state.chapterNum.value <= 1"
          type="button"
          class="px-2 py-1 text-xs rounded border border-[var(--color-parchment-darker)] bg-white hover:bg-[var(--color-parchment)] disabled:opacity-40 cursor-pointer"
        >
          ◀
        </button>
        <input
          v-model.number="jumpNum"
          @keyup.enter="onJump"
          type="number"
          min="1"
          :max="state.numChapters.value"
          :placeholder="`当前 第${state.chapterNum.value}章`"
          class="flex-1 min-w-0 text-xs bg-white border border-[var(--color-parchment-darker)] rounded px-2 py-1 text-center font-mono focus:outline-none focus:border-[var(--color-leather)]"
        />
        <button
          @click="onJump"
          type="button"
          class="px-2 py-1 text-xs rounded bg-[var(--color-leather)] text-white hover:opacity-90 cursor-pointer"
        >
          跳
        </button>
        <button
          @click="state.nextChapter()"
          :disabled="state.chapterNum.value >= state.numChapters.value"
          type="button"
          class="px-2 py-1 text-xs rounded border border-[var(--color-parchment-darker)] bg-white hover:bg-[var(--color-parchment)] disabled:opacity-40 cursor-pointer"
        >
          ▶
        </button>
      </div>

      <!-- 搜索与筛选 -->
      <div class="space-y-1.5">
        <input
          v-model="searchText"
          placeholder="搜索章号或标题..."
          class="w-full text-xs bg-white border border-[var(--color-parchment-darker)] rounded px-2.5 py-1 focus:outline-none focus:border-[var(--color-leather)]"
        />
        <div class="grid grid-cols-3 gap-1 bg-[var(--color-parchment-dark)]/50 p-0.5 rounded-lg text-[11px]">
          <button
            @click="filter = 'all'"
            type="button"
            class="py-1 rounded font-medium cursor-pointer transition-colors"
            :class="filter === 'all' ? 'bg-white text-[var(--color-leather)] shadow-xs font-bold' : 'text-stone-600'"
          >
            全部
          </button>
          <button
            @click="filter = 'written'"
            type="button"
            class="py-1 rounded font-medium cursor-pointer transition-colors"
            :class="filter === 'written' ? 'bg-white text-emerald-700 shadow-xs font-bold' : 'text-stone-600'"
          >
            已写
          </button>
          <button
            @click="filter = 'unwritten'"
            type="button"
            class="py-1 rounded font-medium cursor-pointer transition-colors"
            :class="filter === 'unwritten' ? 'bg-white text-stone-800 shadow-xs font-bold' : 'text-stone-600'"
          >
            待写
          </button>
        </div>
      </div>
    </div>

    <!-- 章节列表 -->
    <div class="flex-1 overflow-y-auto p-2 space-y-1">
      <button
        v-for="ch in filteredList"
        :key="ch.num"
        @click="state.selectChapter(ch.num)"
        type="button"
        class="w-full text-left px-2.5 py-2 rounded-lg border text-xs transition-all cursor-pointer flex items-center gap-2"
        :class="
          ch.num === state.chapterNum.value
            ? 'bg-amber-50 border-[var(--color-leather)] shadow-xs ring-1 ring-[var(--color-leather)]/40'
            : ch.num === state.pipelineTargetChapter.value && state.pipelineRunning.value
              ? 'bg-cyan-50 border-cyan-400 animate-pulse'
              : 'bg-white border-transparent hover:bg-[var(--color-parchment)]/50 hover:border-[var(--color-parchment-darker)]'
        "
      >
        <!-- 状态圆点 -->
        <span
          class="w-2.5 h-2.5 rounded-full shrink-0"
          :class="
            ch.num === state.pipelineTargetChapter.value && state.pipelineRunning.value
              ? 'bg-cyan-500 animate-ping'
              : ch.has_final
                ? 'bg-emerald-500'
                : ch.has_draft || ch.chars > 0
                  ? 'bg-amber-500'
                  : 'bg-stone-300'
          "
          :title="ch.has_final ? '已审校定稿' : ch.has_draft ? '草稿' : '未写'"
        />

        <!-- 章号与标题 -->
        <div class="min-w-0 flex-1">
          <div class="flex items-center justify-between gap-1">
            <span class="font-bold text-[var(--color-ink)] font-mono">
              第 {{ ch.num }} 章
            </span>
            <span v-if="ch.chars > 0" class="text-[10px] font-mono text-emerald-700 bg-emerald-50 px-1.5 rounded">
              {{ ch.chars }}字
            </span>
            <span v-else-if="ch.has_outline" class="text-[10px] text-amber-700 bg-amber-50 px-1 rounded">
              有细纲
            </span>
          </div>
          <div class="text-[11px] text-[var(--color-ink-light)] truncate mt-0.5">
            {{ ch.title }}
          </div>
        </div>
      </button>
    </div>

    <!-- 图例底栏 -->
    <div class="px-3 py-2 border-t border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/30 flex items-center justify-between text-[10px] text-stone-500">
      <span class="flex items-center gap-1"><i class="w-2 h-2 rounded-full bg-emerald-500 inline-block" /> 定稿</span>
      <span class="flex items-center gap-1"><i class="w-2 h-2 rounded-full bg-amber-500 inline-block" /> 草稿</span>
      <span class="flex items-center gap-1"><i class="w-2 h-2 rounded-full bg-stone-300 inline-block" /> 待写</span>
    </div>
  </aside>
</template>
