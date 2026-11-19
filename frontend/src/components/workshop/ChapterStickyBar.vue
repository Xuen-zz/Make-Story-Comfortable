<script setup lang="ts">
import { computed } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'

const props = defineProps<{
  state: ReturnType<typeof useWorkshopState>
}>()

const hasDraft = computed(() => {
  return Boolean(props.state.chapter.value.result && props.state.chapter.value.result.trim())
})

const draftLength = computed(() => {
  return props.state.chapter.value.result ? props.state.chapter.value.result.length : 0
})

const hasEn = computed(() => {
  return Boolean(props.state.translateResult.value && props.state.translateResult.value.trim())
})

function scrollTo(id: string) {
  const el = document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}
</script>

<template>
  <div class="bg-white/95 border border-[var(--color-parchment-darker)] rounded-xl shadow-sm px-3.5 py-2.5 flex items-center justify-between flex-wrap gap-2 transition-all">
    <!-- 左侧：切章按钮与当前章节显示 -->
    <div class="flex items-center gap-2">
      <button
        @click="state.prevChapter()"
        :disabled="!state.pipelineRunning.value && state.chapterNum.value <= 1"
        class="px-2.5 py-1 text-xs font-semibold rounded-md border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/50 hover:bg-[var(--color-parchment)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
        type="button"
        :title="state.pipelineRunning.value ? '流水线生产中：点击快速查阅上一章' : '切换至上一章'"
      >
        ◀ 上一章
      </button>

      <div class="flex items-center gap-1.5 bg-[var(--color-parchment-light)] px-2.5 py-1 rounded-lg border border-[var(--color-parchment-darker)] text-xs">
        <span class="text-stone-500 font-medium hidden sm:inline">当前章节：</span>
        <span class="font-bold text-[var(--color-leather)] text-sm">第 {{ state.chapterNum.value }} 章</span>
        <span v-if="state.pipelineRunning.value" class="text-[10px] px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-500/60 font-mono animate-pulse ml-1">
          🔒 生产锁定 (第 {{ state.pipelineTargetChapter.value }} 章)
        </span>
        <!-- 跨章查阅入口按钮 -->
        <button
          @click="state.openQuickReader()"
          type="button"
          class="ml-1.5 px-2 py-0.5 rounded-md bg-amber-500 hover:bg-amber-600 text-stone-950 font-bold text-xs flex items-center gap-1 transition-all cursor-pointer shadow-sm active:scale-95"
          title="跨章快速查阅器：随时查阅、对照与复制其他章节，绝不中断当前流水线"
        >
          <span>📖</span>
          <span>查阅其他章</span>
        </button>
      </div>

      <button
        @click="state.nextChapter()"
        :disabled="!state.pipelineRunning.value && state.chapterNum.value >= state.numChapters.value"
        class="px-2.5 py-1 text-xs font-semibold rounded-md border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/50 hover:bg-[var(--color-parchment)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
        type="button"
        :title="state.pipelineRunning.value ? '流水线生产中：点击快速查阅下一章' : '切换至下一章'"
      >
        下一章 ▶
      </button>
    </div>

    <!-- 中间：已有章节快捷跳转与磁盘就绪状态 -->
    <div class="flex items-center gap-2 text-xs flex-wrap">
      <!-- 快速跳转章节胶囊 -->
      <div v-if="state.existingChapters.value.length > 0" class="flex items-center gap-1 py-0.5 px-2 bg-stone-100 rounded-lg border border-stone-200">
        <span class="text-[11px] text-stone-500 font-medium">已有:</span>
        <button
          v-for="ch in state.existingChapters.value"
          :key="ch.num"
          @click="state.selectChapter(ch.num)"
          class="px-2 py-0.5 rounded text-[11px] font-mono font-bold transition-all cursor-pointer select-none"
          :class="ch.num === state.chapterNum.value
            ? 'bg-[var(--color-leather)] text-white shadow-sm ring-2 ring-amber-400 scale-105'
            : (ch.num === state.pipelineTargetChapter.value && state.pipelineRunning.value
                ? 'bg-cyan-950 text-cyan-300 border border-cyan-500 animate-pulse'
                : (ch.has_final
                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-300 hover:bg-emerald-200'
                    : 'bg-white text-stone-700 border border-stone-200 hover:bg-stone-50'))"
          :title="state.pipelineRunning.value ? `第 ${ch.num} 章 (流水线运行中：点击查阅内容)` : `第 ${ch.num} 章${ch.has_final ? ' (已定稿)' : ' (草稿)'}`"
          type="button"
        >
          <span v-if="ch.num === state.pipelineTargetChapter.value && state.pipelineRunning.value">⚡</span>
          {{ ch.num }}
        </button>
      </div>
      <!-- 草稿状态 -->
      <span
        v-if="hasDraft"
        class="px-2 py-0.5 rounded-full font-medium bg-emerald-100 text-emerald-800 border border-emerald-300 flex items-center gap-1"
      >
        <span>✍️ 中文草稿:</span>
        <strong>{{ draftLength.toLocaleString() }} 字</strong>
      </span>
      <span
        v-else
        class="px-2 py-0.5 rounded-full text-stone-500 bg-stone-100 border border-stone-200"
      >
        ✍️ 草稿待写
      </span>

      <!-- 英文出海状态 -->
      <span
        v-if="hasEn"
        class="px-2 py-0.5 rounded-full font-medium bg-indigo-100 text-indigo-800 border border-indigo-300"
      >
        🇺🇸 英文已译制
      </span>
      <span
        v-else-if="state.pipelineMode.value === 'bilingual'"
        class="px-2 py-0.5 rounded-full text-stone-400 bg-stone-50 border border-stone-200"
      >
        🇺🇸 英文未译
      </span>

      <!-- 全链路智能生产控制舱快捷按钮 -->
      <button
        @click="state.openPipelineControlRoom()"
        type="button"
        class="ml-2 px-3 py-1 text-xs font-bold rounded-lg bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white shadow-md hover:shadow-cyan-500/20 transition-all flex items-center gap-1.5 cursor-pointer active:scale-95"
        title="打开专属全链路生产控制舱大屏（起草、润色、英译、质检、归档一键全自动）"
      >
        <span>🚀</span>
        <span>生产控制舱</span>
        <span
          v-if="state.pipelineRunning.value"
          class="relative flex h-2 w-2"
        >
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-200 opacity-75"></span>
          <span class="relative inline-flex rounded-full h-2 w-2 bg-white"></span>
        </span>
      </button>
    </div>

    <!-- 右侧：快捷导航锚点 -->
    <div class="flex items-center gap-1 text-xs">
      <span class="text-stone-400 mr-1 hidden md:inline">直达：</span>
      <button
        @click="scrollTo('step-detailed-outline')"
        class="px-2 py-1 rounded hover:bg-[var(--color-parchment)] text-stone-700 hover:text-black transition-colors cursor-pointer"
        type="button"
      >
        📝 细纲
      </button>
      <button
        @click="scrollTo('step-chapter-draft')"
        class="px-2 py-1 rounded hover:bg-[var(--color-parchment)] text-stone-700 hover:text-black font-semibold transition-colors cursor-pointer"
        type="button"
      >
        ✍️ 草稿
      </button>
      <button
        @click="scrollTo('step-finalize')"
        class="px-2 py-1 rounded hover:bg-[var(--color-parchment)] text-stone-700 hover:text-black transition-colors cursor-pointer"
        type="button"
      >
        ⚡ 定稿
      </button>
      <button
        @click="scrollTo('step-localization')"
        class="px-2 py-1 rounded hover:bg-[var(--color-parchment)] text-indigo-700 hover:text-indigo-900 font-medium transition-colors cursor-pointer"
        type="button"
      >
        🇺🇸 出海译制
      </button>
    </div>
  </div>
</template>
