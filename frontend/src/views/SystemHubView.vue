<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ConfigView from '@/views/ConfigView.vue'
import ConsistencyView from '@/views/ConsistencyView.vue'
import FilesView from '@/views/FilesView.vue'
import LogsView from '@/views/LogsView.vue'

type SystemTab = 'config' | 'consistency' | 'files' | 'logs'

const route = useRoute()
const router = useRouter()

const tabs: { id: SystemTab; label: string; icon: string; desc: string }[] = [
  { id: 'config', label: '模型与审校配置', icon: '⚙️', desc: '配置写作模型 (3.8 Flash)、审校模型 (4 Hydrogen) 与代理' },
  { id: 'consistency', label: '一致性检查', icon: '🔍', desc: '核对单章与角色状态、架构和前文摘要是否冲突' },
  { id: 'files', label: '项目文件管理', icon: '📁', desc: '直接浏览与编辑当前项目目录下的原始 txt/json 文件' },
  { id: 'logs', label: '运行与 Prompt 日志', icon: '📜', desc: '查看后台服务日志与每次大模型调用历史' },
]

const activeTab = ref<SystemTab>('config')

watch(
  () => route.query.tab,
  (t) => {
    if (t === 'config' || t === 'consistency' || t === 'files' || t === 'logs') {
      activeTab.value = t
    }
  },
  { immediate: true },
)

function selectTab(id: SystemTab) {
  activeTab.value = id
  router.replace({ path: '/system', query: { tab: id } })
}
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-6 space-y-5">
    <div>
      <h2 class="text-2xl font-bold text-[var(--color-ink)]">⚙️ 系统与工具中心</h2>
      <p class="text-xs text-[var(--color-ink-light)] mt-0.5">
        统一管理模型接口、读写分离审校配置、一致性校对、本地文件与调用日志
      </p>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-2.5">
      <button
        v-for="t in tabs"
        :key="t.id"
        @click="selectTab(t.id)"
        type="button"
        class="text-left p-3 rounded-xl border-2 transition-all cursor-pointer"
        :class="
          activeTab === t.id
            ? 'border-[var(--color-leather)] bg-white shadow-sm'
            : 'border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/50 hover:bg-white'
        "
      >
        <div class="font-bold text-sm text-[var(--color-ink)] flex items-center gap-1.5">
          <span>{{ t.icon }}</span>
          <span>{{ t.label }}</span>
        </div>
        <div class="text-[11px] text-[var(--color-ink-light)] mt-1 line-clamp-1">
          {{ t.desc }}
        </div>
      </button>
    </div>

    <div class="rounded-2xl border border-[var(--color-parchment-darker)] bg-white/60 p-2 sm:p-4">
      <ConfigView v-if="activeTab === 'config'" />
      <ConsistencyView v-else-if="activeTab === 'consistency'" />
      <FilesView v-else-if="activeTab === 'files'" />
      <LogsView v-else />
    </div>
  </div>
</template>
