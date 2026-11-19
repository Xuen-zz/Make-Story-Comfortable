<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StylesView from '@/views/StylesView.vue'
import KnowledgeView from '@/views/KnowledgeView.vue'
import PresetsView from '@/views/PresetsView.vue'
import ProfileView from '@/views/ProfileView.vue'

type AssetTab = 'styles' | 'knowledge' | 'presets' | 'profile'

const route = useRoute()
const router = useRouter()

const tabs: { id: AssetTab; label: string; icon: string; desc: string }[] = [
  { id: 'styles', label: '文风与叙事DNA', icon: '🎨', desc: '管理写作风格、叙事节奏与作者参考库' },
  { id: 'knowledge', label: '知识库 (RAG)', icon: '📚', desc: '导入世界观资料与设定文档供写作自动检索' },
  { id: 'presets', label: '提示词方案', icon: '📋', desc: '查看与微调系统各环节底层 Prompt 模板' },
  { id: 'profile', label: '用户画像', icon: '👤', desc: '全局内容偏好与风格禁忌记忆' },
]

const activeTab = ref<AssetTab>('styles')

watch(
  () => route.query.tab,
  (t) => {
    if (t === 'styles' || t === 'knowledge' || t === 'presets' || t === 'profile') {
      activeTab.value = t
    }
  },
  { immediate: true },
)

function selectTab(id: AssetTab) {
  activeTab.value = id
  router.replace({ path: '/assets', query: { tab: id } })
}
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-6 space-y-5">
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h2 class="text-2xl font-bold text-[var(--color-ink)]">📚 创作资产库</h2>
        <p class="text-xs text-[var(--color-ink-light)] mt-0.5">
          集中管理文风 DNA、参考知识库、提示词模板与个人写作偏好
        </p>
      </div>
    </div>

    <!-- 统一横排标签栏 -->
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

    <!-- 子视图内容 -->
    <div class="rounded-2xl border border-[var(--color-parchment-darker)] bg-white/60 p-2 sm:p-4">
      <StylesView v-if="activeTab === 'styles'" />
      <KnowledgeView v-else-if="activeTab === 'knowledge'" />
      <PresetsView v-else-if="activeTab === 'presets'" />
      <ProfileView v-else />
    </div>
  </div>
</template>
