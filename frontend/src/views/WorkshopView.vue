<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { generateApi } from '@/api/client'
import { useWorkshopState } from '@/composables/useWorkshopState'
import WorkflowStepper, { type WorkshopStage, type DashboardPayload } from '@/components/workshop/WorkflowStepper.vue'
import GlobalParamsCard from '@/components/workshop/GlobalParamsCard.vue'
import ArchitectureStep from '@/components/workshop/ArchitectureStep.vue'
import BlueprintStep from '@/components/workshop/BlueprintStep.vue'
import StepOutlineReview from '@/components/workshop/StepOutlineReview.vue'
import StepProductionBoard from '@/components/workshop/StepProductionBoard.vue'
import QuickChapterReader from '@/components/workshop/QuickChapterReader.vue'
import '@/styles/workshop.css'

const state = useWorkshopState()

const activeStage = ref<WorkshopStage>('stage4')
const dashboard = ref<DashboardPayload | null>(null)
const dashboardLoading = ref(false)
const stageInitializedFor = ref('')

async function fetchDashboard(autoSelectStage = false) {
  const fp = state.filepath.value
  if (!fp) return
  dashboardLoading.value = true
  try {
    const res = await generateApi.dashboard(fp)
    dashboard.value = res.data as DashboardPayload
    if (autoSelectStage && stageInitializedFor.value !== fp) {
      stageInitializedFor.value = fp
      const hasBp = Boolean(dashboard.value?.assets?.blueprint?.exists)
      const hasArch = Boolean(dashboard.value?.assets?.architecture?.exists)
      const hasOutlines = (dashboard.value?.assets?.detailed_outline?.planned_chapters || 0) > 0
      if (hasOutlines) {
        activeStage.value = 'stage4'
      } else if (hasBp) {
        activeStage.value = 'stage3'
      } else if (hasArch) {
        activeStage.value = 'stage2'
      } else {
        activeStage.value = 'stage1'
      }
    }
  } catch (e) {
    console.error('Failed to load dashboard:', e)
  } finally {
    dashboardLoading.value = false
  }
}

onMounted(() => {
  if (state.pipelineMode.value !== 'fast_zh') {
    state.setPipelineMode('fast_zh')
  }
  fetchDashboard(true)
})

watch(() => state.filepath.value, (fp) => {
  if (fp) fetchDashboard(true)
})

watch(() => state.saveMsg.value, (msg) => {
  if (msg && msg.startsWith('✅')) {
    setTimeout(() => fetchDashboard(false), 500)
  }
})

watch(() => state.pipelineRunning.value, (running, prev) => {
  if (prev && !running) {
    setTimeout(() => fetchDashboard(false), 400)
  }
})

watch(() => state.fastIncubating.value, (running, prev) => {
  if (prev && !running) {
    setTimeout(() => {
      fetchDashboard(false)
      if (state.bp.value.result) {
        activeStage.value = 'stage3'
      }
    }, 400)
  }
})

async function handleQuickIncubateFromStage1() {
  if (!state.topic.value.trim()) {
    alert('请先在下方「题材/主题」输入框填写你的故事脑洞！')
    return
  }
  await state.doFastIncubateBook()
}

function handleProceedToBatch(start: number, end: number) {
  state.batchQueueStart.value = start
  state.batchQueueEnd.value = end
  state.chapterNum.value = start
  activeStage.value = 'stage4'
}
</script>

<template>
  <div class="max-w-[1680px] mx-auto px-4 py-4 space-y-4">
    <!-- 顶部精简动作栏 -->
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div class="flex items-center gap-3">
        <h2 class="text-xl font-bold text-[var(--color-ink)]">📋 写书工单台</h2>
        <span class="text-xs px-2.5 py-0.5 rounded-full border border-emerald-200 bg-emerald-50 text-emerald-900 font-medium">
          🇨🇳 纯中文长篇连载流水线（3.8 Flash 写 ➔ 4 Hydrogen 审）
        </span>
      </div>

      <div class="flex items-center gap-2 flex-wrap">
        <button
          @click="state.reloadProjectContent(); fetchDashboard(false)"
          :disabled="state.reloading.value"
          class="px-3 py-1.5 rounded-lg border border-[var(--color-parchment-darker)] bg-white hover:bg-[var(--color-parchment)] text-xs font-medium cursor-pointer"
          type="button"
        >
          {{ state.reloading.value ? '同步中…' : '🔄 同步磁盘' }}
        </button>
        <button
          @click="state.doExportNovel()"
          :disabled="state.exporting.value"
          class="btn-primary text-xs"
          type="button"
        >
          {{ state.exporting.value ? '导出中…' : '📥 合并导出全书' }}
        </button>
      </div>
    </div>

    <!-- 全局保存反馈提示 -->
    <Transition name="fade">
      <div
        v-if="state.saveMsg.value"
        class="px-4 py-2 rounded-lg text-sm"
        :class="state.saveMsg.value.startsWith('✅') ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'"
      >
        {{ state.saveMsg.value }}
      </div>
    </Transition>

    <!-- 4 步清晰流水线工单导航条 -->
    <WorkflowStepper
      :state="state"
      :active-stage="activeStage"
      :dashboard="dashboard"
      @update:active-stage="activeStage = $event"
    />

    <!-- ① 立项与架构 -->
    <div v-if="activeStage === 'stage1'" class="space-y-4">
      <div class="rounded-2xl border border-[var(--color-parchment-darker)] bg-[var(--color-surface)] p-4 flex items-center justify-between flex-wrap gap-3">
        <div>
          <div class="font-bold text-[var(--color-gold-light)] text-sm sm:text-base">
            🏛️ 第 1 步：确立题材、目标篇幅（默认 {{ state.numChapters.value }} 章 / {{ ((state.numChapters.value * state.wordNumber.value) / 10000).toFixed(0) }} 万字）与雪花架构
          </div>
          <p class="text-xs text-[var(--color-ink-light)] mt-0.5">
            填好下方核心脑洞与篇幅后，可直接一键生成「全书架构 + {{ state.numChapters.value }} 章目录」，也可在下方逐项精修。
          </p>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="handleQuickIncubateFromStage1()"
            :disabled="state.fastIncubating.value"
            type="button"
            class="btn-primary text-xs sm:text-sm"
          >
            {{ state.fastIncubating.value ? '⏳ 推演中…' : '🚀 一键立项并生成全书目录' }}
          </button>
          <button
            @click="activeStage = 'stage2'"
            type="button"
            class="px-3.5 py-2 rounded-lg border border-[var(--color-leather)] text-[var(--color-leather)] hover:bg-[var(--color-parchment)] text-xs sm:text-sm font-semibold cursor-pointer"
          >
            下一步：全书目录 ➔
          </button>
        </div>
      </div>

      <div v-if="state.fastIncubating.value" class="px-4 py-2.5 rounded-xl bg-amber-50 border border-amber-300 text-amber-950 text-xs font-mono flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full bg-amber-600 animate-ping" />
        <span>{{ state.fastIncubateProgress.value }}</span>
      </div>

      <GlobalParamsCard :state="state" />
      <ArchitectureStep :state="state" />
    </div>

    <!-- ② 全书目录 -->
    <div v-else-if="activeStage === 'stage2'" class="space-y-4">
      <div class="rounded-2xl border border-[var(--color-parchment-darker)] bg-white px-4 py-3 flex items-center justify-between flex-wrap gap-3">
        <div>
          <div class="font-bold text-sm text-[var(--color-ink)]">
            🗺️ 第 2 步：规划全书 {{ state.numChapters.value }} 章目录骨架（支持分批断点续写）
          </div>
          <div class="text-xs text-[var(--color-ink-light)] mt-0.5">
            先确立整本书每一章的标题与一句话梗概，再进入第 3 步按 10 章一批生成可编辑细纲。
          </div>
        </div>
        <button @click="activeStage = 'stage3'" type="button" class="btn-primary text-xs sm:text-sm">
          下一步：分批审核细纲 ➔
        </button>
      </div>

      <BlueprintStep :state="state" />
    </div>

    <!-- ③ 分批细纲审核 -->
    <StepOutlineReview
      v-else-if="activeStage === 'stage3'"
      :state="state"
      :chapters="dashboard?.chapters ?? []"
      :dashboard="dashboard"
      @proceed-to-batch="handleProceedToBatch"
      @refresh="fetchDashboard(false)"
    />

    <!-- ④ 批量写审生产看板 -->
    <StepProductionBoard
      v-else
      :state="state"
      :chapters="dashboard?.chapters ?? []"
      :loading="dashboardLoading"
      @refresh="fetchDashboard(false)"
      @go-stage="activeStage = $event"
    />

    <!-- 快捷前章阅读器弹窗 -->
    <QuickChapterReader :state="state" />
  </div>
</template>
