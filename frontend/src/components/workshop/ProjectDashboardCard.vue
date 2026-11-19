<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'
import { generateApi } from '@/api/client'

const props = defineProps<{ state: ReturnType<typeof useWorkshopState> }>()

const isOpen = ref(true)
const activeFilter = ref<'all' | 'written' | 'finalized' | 'outlined'>('all')
const loading = ref(false)

interface AssetInfo {
  exists: boolean
  chars: number
  label: string
  file: string
  total_chapters?: number
  planned_chapters?: number
}

interface ChapterItem {
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

interface DashboardData {
  project_name: string
  filepath: string
  assets: Record<string, AssetInfo>
  chapters: ChapterItem[]
}

const dashboardData = ref<DashboardData | null>(null)

async function fetchDashboard() {
  if (!props.state) return
  loading.value = true
  try {
    const res = await generateApi.dashboard(props.state.filepath.value)
    dashboardData.value = res.data
  } catch (e) {
    console.error('Failed to load dashboard:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDashboard()
})

// 监听项目路径就绪或切换，自动加载看板与50章资产
watch(() => props.state.filepath.value, (newFp) => {
  if (newFp) {
    fetchDashboard()
  }
}, { immediate: true })

// 监听保存/重新载入事件自动刷新看板
watch(() => props.state.saveMsg.value, (msg) => {
  if (msg && msg.startsWith('✅')) {
    setTimeout(fetchDashboard, 600)
  }
})

watch(() => props.state.chapterNum.value, () => {
  // 章节切换微刷新
})

const filteredChapters = computed(() => {
  if (!dashboardData.value?.chapters) return []
  const list = dashboardData.value.chapters
  if (activeFilter.value === 'written') {
    return list.filter(c => c.has_draft || c.chars > 0)
  }
  if (activeFilter.value === 'finalized') {
    return list.filter(c => c.has_final)
  }
  if (activeFilter.value === 'outlined') {
    return list.filter(c => c.has_outline)
  }
  return list
})

const stats = computed(() => {
  if (!dashboardData.value?.chapters) return { total: 0, written: 0, finalized: 0, outlined: 0, en: 0, totalWords: 0 }
  const list = dashboardData.value.chapters
  let totalWords = 0
  let written = 0
  let finalized = 0
  let outlined = 0
  let en = 0
  for (const c of list) {
    if (c.has_draft || c.chars > 0) {
      written++
      totalWords += c.chars
    }
    if (c.has_final) finalized++
    if (c.has_outline) outlined++
    if (c.has_en) en++
  }
  return {
    total: list.length,
    written,
    finalized,
    outlined,
    en,
    totalWords,
  }
})

function scrollToSection(id: string) {
  const el = document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function handleRowClick(num: number) {
  props.state.selectChapter(num)
}

function goToDraft(num: number) {
  props.state.selectChapter(num)
  scrollToSection('step-chapter-draft')
}

function goToFinalize(num: number) {
  props.state.selectChapter(num)
  scrollToSection('step-finalize')
}

function goToTranslate(num: number) {
  props.state.selectChapter(num)
  scrollToSection('step-localization')
}
</script>

<template>
  <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-white shadow-md overflow-hidden transition-all duration-300">
    <!-- 头部横条 -->
    <div class="px-5 py-3.5 bg-gradient-to-r from-[var(--color-parchment-light)] via-white to-[var(--color-parchment-light)] border-b border-[var(--color-parchment-darker)] flex items-center justify-between flex-wrap gap-2">
      <div class="flex items-center gap-2.5">
        <span class="text-xl">📊</span>
        <div>
          <div class="flex items-center gap-2">
            <h2 class="text-base font-bold text-[var(--color-leather)]">
              《{{ dashboardData?.project_name || state.topic.value || '当前项目' }}》创作进度与资产看板
            </h2>
            <span class="text-xs bg-emerald-100 text-emerald-800 font-semibold px-2 py-0.5 rounded-full border border-emerald-300">
              已就绪
            </span>
          </div>
          <p class="text-xs text-[var(--color-ink-light)] mt-0.5">
            实时扫描磁盘文件 · 纵览全书架构规划与章节定稿/出海译制状态
          </p>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <button
          @click="fetchDashboard()"
          :disabled="loading"
          class="px-2.5 py-1 text-xs border border-[var(--color-parchment-darker)] rounded-md hover:bg-[var(--color-parchment)] transition-colors flex items-center gap-1 cursor-pointer"
          type="button"
          title="刷新最新磁盘保存状态"
        >
          <span :class="{ 'animate-spin': loading }">🔄</span>
          <span>刷新看板</span>
        </button>

        <button
          @click="isOpen = !isOpen"
          class="px-2.5 py-1 text-xs font-medium text-[var(--color-leather)] hover:text-black border border-[var(--color-parchment-darker)] rounded-md hover:bg-[var(--color-parchment)] transition-colors cursor-pointer"
          type="button"
        >
          {{ isOpen ? '▲ 折叠详情' : '▼ 展开全书进度' }}
        </button>
      </div>
    </div>

    <!-- 核心全书资产状态横条（始终可见） -->
    <div class="px-5 py-3 bg-[var(--color-parchment)]/30 border-b border-[var(--color-parchment-darker)]">
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
        <!-- 1. 架构 -->
        <div class="p-2.5 rounded-lg border bg-white flex flex-col justify-between"
             :class="dashboardData?.assets?.architecture?.exists ? 'border-emerald-300 bg-emerald-50/20' : 'border-stone-200'">
          <div class="flex items-center justify-between text-xs">
            <span class="font-medium text-stone-700">🏛️ 小说架构</span>
            <span v-if="dashboardData?.assets?.architecture?.exists" class="text-emerald-700 font-semibold">✅ 已保存</span>
            <span v-else class="text-stone-400">未就绪</span>
          </div>
          <div class="mt-1.5 text-[11px] text-[var(--color-ink-light)] truncate">
            {{ dashboardData?.assets?.architecture?.exists ? `${dashboardData.assets.architecture.chars.toLocaleString()} 字符` : 'Novel_architecture.txt' }}
          </div>
        </div>

        <!-- 2. 蓝图 -->
        <div class="p-2.5 rounded-lg border bg-white flex flex-col justify-between"
             :class="dashboardData?.assets?.blueprint?.exists ? 'border-emerald-300 bg-emerald-50/20' : 'border-stone-200'">
          <div class="flex items-center justify-between text-xs">
            <span class="font-medium text-stone-700">📋 章节蓝图</span>
            <span v-if="dashboardData?.assets?.blueprint?.exists" class="text-emerald-700 font-semibold">✅ 已保存</span>
            <span v-else class="text-stone-400">未就绪</span>
          </div>
          <div class="mt-1.5 text-[11px] text-[var(--color-ink-light)] truncate">
            {{ dashboardData?.assets?.blueprint?.exists ? `${dashboardData.assets.blueprint.total_chapters} 章全书蓝图` : 'Novel_directory.txt' }}
          </div>
        </div>

        <!-- 3. 细纲 -->
        <div class="p-2.5 rounded-lg border bg-white flex flex-col justify-between"
             :class="dashboardData?.assets?.detailed_outline?.exists ? 'border-emerald-300 bg-emerald-50/20' : 'border-stone-200'">
          <div class="flex items-center justify-between text-xs">
            <span class="font-medium text-stone-700">📝 章节细纲</span>
            <span v-if="dashboardData?.assets?.detailed_outline?.exists" class="text-emerald-700 font-semibold">✅ 已保存</span>
            <span v-else class="text-stone-400">未就绪</span>
          </div>
          <div class="mt-1.5 text-[11px] text-[var(--color-ink-light)] truncate">
            {{ dashboardData?.assets?.detailed_outline?.exists ? `${dashboardData.assets.detailed_outline.planned_chapters} 章细纲就绪` : 'Novel_detailed_outline.txt' }}
          </div>
        </div>

        <!-- 4. 前文记忆 -->
        <div class="p-2.5 rounded-lg border bg-white flex flex-col justify-between"
             :class="dashboardData?.assets?.global_summary?.exists ? 'border-emerald-300 bg-emerald-50/20' : 'border-stone-200'">
          <div class="flex items-center justify-between text-xs">
            <span class="font-medium text-stone-700">🧠 前文主线记忆</span>
            <span v-if="dashboardData?.assets?.global_summary?.exists" class="text-emerald-700 font-semibold">✅ 已更新</span>
            <span v-else class="text-stone-400">待首次定稿</span>
          </div>
          <div class="mt-1.5 text-[11px] text-[var(--color-ink-light)] truncate">
            {{ dashboardData?.assets?.global_summary?.exists ? '第 1 章已录入入库' : 'global_summary.txt' }}
          </div>
        </div>

        <!-- 5. 角色状态 -->
        <div class="p-2.5 rounded-lg border bg-white flex flex-col justify-between"
             :class="dashboardData?.assets?.character_state?.exists ? 'border-emerald-300 bg-emerald-50/20' : 'border-stone-200'">
          <div class="flex items-center justify-between text-xs">
            <span class="font-medium text-stone-700">👤 角色能力库</span>
            <span v-if="dashboardData?.assets?.character_state?.exists" class="text-emerald-700 font-semibold">✅ 已同步</span>
            <span v-else class="text-stone-400">未就绪</span>
          </div>
          <div class="mt-1.5 text-[11px] text-[var(--color-ink-light)] truncate">
            {{ dashboardData?.assets?.character_state?.exists ? `${dashboardData.assets.character_state.chars.toLocaleString()} 字符` : 'character_state.txt' }}
          </div>
        </div>

        <!-- 6. 英文目录与章名（仅英文出海模式或已存在英文目录时展示） -->
        <div
          v-if="state.pipelineMode.value === 'bilingual' || dashboardData?.assets?.directory_en?.exists"
          @click="scrollToSection('step-localization')"
          class="p-2.5 rounded-lg border bg-white flex flex-col justify-between cursor-pointer hover:border-amber-400 hover:shadow-sm transition-all"
          :class="dashboardData?.assets?.directory_en?.exists ? 'border-amber-300 bg-amber-50/20' : 'border-stone-200'"
          title="点击查看英文目录"
        >
          <div class="flex items-center justify-between text-xs">
            <span class="font-medium text-stone-700">📚 英文目录</span>
            <span v-if="dashboardData?.assets?.directory_en?.exists" class="text-amber-800 font-semibold">✅ {{ dashboardData.assets.directory_en.total_chapters || 0 }} 章已译</span>
            <span v-else class="text-stone-400">未就绪</span>
          </div>
          <div class="mt-1.5 text-[11px] text-[var(--color-ink-light)] truncate flex items-center justify-between">
            <span>Novel_directory_en.txt</span>
            <span class="text-amber-700 font-bold ml-1">查看 ➔</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 折叠展开的章节竖状详细列表 -->
    <div v-show="isOpen" class="p-5 space-y-4">
      <!-- 统计指标与筛选标签栏 -->
      <div class="flex items-center justify-between flex-wrap gap-3">
        <div class="flex items-center gap-1.5 bg-[var(--color-parchment)] p-1 rounded-lg text-xs">
          <button
            @click="activeFilter = 'all'"
            class="px-2.5 py-1 rounded font-medium transition-colors cursor-pointer"
            :class="activeFilter === 'all' ? 'bg-white shadow-sm text-[var(--color-leather)]' : 'text-stone-600 hover:text-black'"
          >
            全部章节 ({{ stats.total }})
          </button>
          <button
            @click="activeFilter = 'written'"
            class="px-2.5 py-1 rounded font-medium transition-colors cursor-pointer"
            :class="activeFilter === 'written' ? 'bg-white shadow-sm text-emerald-800' : 'text-stone-600 hover:text-black'"
          >
            已生成草稿 ({{ stats.written }})
          </button>
          <button
            @click="activeFilter = 'finalized'"
            class="px-2.5 py-1 rounded font-medium transition-colors cursor-pointer"
            :class="activeFilter === 'finalized' ? 'bg-white shadow-sm text-green-800' : 'text-stone-600 hover:text-black'"
          >
            已终稿定稿 ({{ stats.finalized }})
          </button>
          <button
            @click="activeFilter = 'outlined'"
            class="px-2.5 py-1 rounded font-medium transition-colors cursor-pointer"
            :class="activeFilter === 'outlined' ? 'bg-white shadow-sm text-amber-800' : 'text-stone-600 hover:text-black'"
          >
            细纲已规划 ({{ stats.outlined }})
          </button>
        </div>

        <div class="text-xs text-stone-600 font-medium flex items-center gap-2">
          <span>总正文字数：<strong class="text-emerald-800">{{ stats.totalWords.toLocaleString() }}</strong> 字</span>
          <span v-if="state.pipelineMode.value === 'bilingual' || stats.en > 0">| 出海译制：<strong class="text-indigo-800">{{ stats.en }}</strong> 章</span>
        </div>
      </div>

      <!-- 优雅竖向卡片流（Vertical Card List，点击任意章节行自动联动全页） -->
      <div class="max-h-[520px] overflow-y-auto space-y-2.5 pr-1.5">
        <div
          v-for="ch in filteredChapters"
          :key="ch.num"
          @click="handleRowClick(ch.num)"
          class="p-3.5 rounded-lg border transition-all duration-200 flex flex-col md:flex-row md:items-center justify-between gap-3 cursor-pointer select-none"
          :class="[
            ch.num === state.chapterNum.value
              ? 'ring-2 ring-[var(--color-leather)] bg-amber-50/90 shadow-md border-[var(--color-leather)] scale-[1.005]'
              : (ch.has_final
                  ? 'bg-emerald-50/40 border-emerald-300 hover:border-emerald-400 hover:bg-emerald-50/60'
                  : (ch.has_draft
                      ? 'bg-emerald-50/20 border-emerald-200 hover:border-emerald-300 hover:bg-emerald-50/40'
                      : (ch.has_outline
                          ? 'bg-amber-50/20 border-amber-200 hover:border-amber-300 hover:bg-amber-50/40'
                          : 'bg-white border-stone-200 hover:border-stone-300 hover:bg-stone-50'))),
          ]"
        >
          <!-- 左侧：章号、标题与状态药丸 -->
          <div class="flex items-start md:items-center gap-3 min-w-0 flex-1">
            <div
              class="w-10 h-10 rounded-lg flex items-center justify-center font-bold text-sm flex-shrink-0"
              :class="ch.has_final
                ? 'bg-emerald-700 text-white shadow-sm'
                : (ch.has_draft
                    ? 'bg-emerald-500 text-white'
                    : (ch.has_outline
                        ? 'bg-amber-500 text-white'
                        : 'bg-stone-200 text-stone-600'))"
            >
              {{ ch.num }}
            </div>

            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-bold text-sm text-[var(--color-ink)] truncate">
                  第 {{ ch.num }} 章 · {{ ch.title }}
                </span>
                <span v-if="ch.title_en" class="text-xs text-amber-900 font-serif italic truncate hidden sm:inline" :title="ch.title_en">
                  ({{ ch.title_en }})
                </span>

                <span v-if="ch.num === state.chapterNum.value" class="text-[11px] px-2 py-0.5 rounded-full font-bold bg-[var(--color-leather)] text-white shadow-xs animate-pulse">
                  ⭐ 当前已选中联动
                </span>

                <!-- 状态徽章组合 -->
                <span v-if="ch.has_final" class="text-[11px] px-2 py-0.5 rounded-full font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
                  ⚡ 已终稿定稿 (已录入全书记忆)
                </span>
                <span v-else-if="ch.has_draft" class="text-[11px] px-2 py-0.5 rounded-full font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                  ✍️ 草稿已保存 (待定稿)
                </span>
                <span v-else class="text-[11px] px-2 py-0.5 rounded-full text-stone-500 bg-stone-100 border border-stone-200">
                  ⏳ 正文待创作
                </span>

                <span v-if="ch.has_outline" class="text-[11px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200">
                  📋 细纲已规划
                </span>

                <span v-if="ch.has_en" class="text-[11px] px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-800 border border-indigo-200 font-medium">
                  🇺🇸 英文已译制 ({{ ch.en_words }} words)
                </span>
              </div>

              <!-- 辅助字数与文件信息 -->
              <div class="text-xs text-[var(--color-ink-light)] mt-1 flex items-center gap-3">
                <span v-if="ch.chars > 0">
                  中文正文：<strong class="text-emerald-800 font-medium">{{ ch.chars.toLocaleString() }}</strong> 字
                </span>
                <span v-else class="text-stone-400">
                  中文正文：暂无
                </span>

                <span>文件：<code>chapter_{{ ch.num }}.txt</code></span>

                <span v-if="ch.has_en" class="text-indigo-700">
                  英文文件：<code>chapters_en/chapter_{{ ch.num }}_en.txt</code>
                </span>
              </div>
            </div>
          </div>

          <!-- 右侧：快捷操作按钮组 -->
          <div class="flex items-center gap-2 flex-shrink-0 self-end md:self-center">
            <!-- 读写草稿 -->
            <button
              @click="goToDraft(ch.num)"
              class="px-2.5 py-1 text-xs font-medium rounded border transition-colors cursor-pointer"
              :class="ch.has_draft
                ? 'bg-white text-emerald-800 border-emerald-300 hover:bg-emerald-50'
                : 'bg-emerald-700 text-white border-emerald-800 hover:bg-emerald-800 font-semibold'"
              type="button"
            >
              {{ ch.has_draft ? '📖 查看草稿' : '▶ 创作本章' }}
            </button>

            <!-- 定稿 -->
            <button
              v-if="ch.has_draft"
              @click="goToFinalize(ch.num)"
              class="px-2.5 py-1 text-xs font-medium rounded border transition-colors cursor-pointer"
              :class="ch.has_final
                ? 'bg-white text-stone-600 border-stone-300 hover:bg-stone-50'
                : 'bg-amber-600 text-white border-amber-700 hover:bg-amber-700'"
              type="button"
            >
              {{ ch.has_final ? '⚡ 查看定稿' : '⚡ 立即定稿' }}
            </button>

            <!-- 出海译制 -->
            <button
              v-if="ch.has_draft"
              @click="goToTranslate(ch.num)"
              class="px-2.5 py-1 text-xs font-medium rounded border transition-colors cursor-pointer"
              :class="ch.has_en
                ? 'bg-indigo-50 text-indigo-800 border-indigo-300 hover:bg-indigo-100'
                : 'bg-white text-indigo-700 border-indigo-300 hover:bg-indigo-50'"
              type="button"
            >
              {{ ch.has_en ? '🇺🇸 查看译文' : '🇺🇸 出海译制' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
