<script setup lang="ts">
import { ref } from 'vue'
import AssetsHubView from '@/views/AssetsHubView.vue'
import SystemHubView from '@/views/SystemHubView.vue'

const activeGroup = ref<'assets' | 'system'>('assets')
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 py-5">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-[var(--color-border)]">
      <div>
        <h1 class="text-lg font-bold text-[var(--color-ink)]">⚙️ 资产与系统设置</h1>
        <p class="text-xs text-[var(--color-ink-light)] mt-0.5">
          低频工具统一收纳于此，日常写书请专注于左侧「📋 写书工单台」。
        </p>
      </div>
      <div class="inline-flex rounded-xl p-1 bg-[var(--color-paper-dark)] border border-[var(--color-border)] self-start">
        <button
          @click="activeGroup = 'assets'"
          type="button"
          class="px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer"
          :class="activeGroup === 'assets'
            ? 'bg-[var(--color-leather)] text-zinc-100 shadow-xs'
            : 'text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
        >
          📚 创作资产（文风 / 知识库 / 提示词 / 画像）
        </button>
        <button
          @click="activeGroup = 'system'"
          type="button"
          class="px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer"
          :class="activeGroup === 'system'
            ? 'bg-[var(--color-leather)] text-zinc-100 shadow-xs'
            : 'text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
        >
          🛠️ 系统与工具（模型配置 / 一致性 / 文件 / 日志）
        </button>
      </div>
    </div>

    <AssetsHubView v-if="activeGroup === 'assets'" />
    <SystemHubView v-else />
  </div>
</template>
