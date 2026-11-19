<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'

const props = defineProps<{
  state: ReturnType<typeof useWorkshopState>
}>()

const activeTab = ref<'whitepaper' | 'chapter'>('whitepaper')
const loading = ref(false)
const whitepaperText = ref('')
const masterIndex = ref<any>(null)
const selectedChapter = ref<number>(1)
const chapterAuditData = ref<any>(null)
const chapterAuditMd = ref<string>('')
const copyToast = ref('')

function showToast(msg: string) {
  copyToast.value = msg
  setTimeout(() => { copyToast.value = '' }, 2500)
}

function copyToClipboard(text: string, label: string) {
  if (!text) return
  navigator.clipboard.writeText(text).then(() => {
    showToast(`✅ ${label} 已复制`)
  }).catch(() => {
    showToast(`❌ 复制失败`)
  })
}

function downloadText(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
  showToast(`📥 已导出文件: ${filename}`)
}

async function fetchWhitepaper() {
  const fp = props.state.projectStore.activeProjectData?.filepath
  if (!fp) return
  loading.value = true
  try {
    const res = await fetch(`/api/generate/book_audit_whitepaper?filepath=${encodeURIComponent(fp)}`)
    if (res.ok) {
      const data = await res.json()
      whitepaperText.value = data.whitepaper || ''
      masterIndex.value = data.index || null
    }
  } catch (e) {
    console.error('Failed to fetch whitepaper:', e)
  } finally {
    loading.value = false
  }
}

async function fetchChapterAudit(num: number) {
  const fp = props.state.projectStore.activeProjectData?.filepath
  if (!fp) return
  try {
    const res = await fetch(`/api/generate/audit_trail?filepath=${encodeURIComponent(fp)}&chapter_num=${num}`)
    if (res.ok) {
      const data = await res.json()
      if (data.exists) {
        chapterAuditData.value = data.data
        chapterAuditMd.value = data.markdown
      } else {
        chapterAuditData.value = null
        chapterAuditMd.value = '暂无本章留底档案（将在流水线生成完成后自动持久化归档）'
      }
    }
  } catch (e) {
    console.error('Failed to fetch chapter audit:', e)
  }
}

const availableChapters = computed(() => {
  if (!masterIndex.value?.chapters) return []
  return Object.keys(masterIndex.value.chapters)
    .map(k => parseInt(k, 10))
    .sort((a, b) => a - b)
})

watch(() => props.state.whitepaperModalOpen?.value, (open) => {
  if (open) {
    fetchWhitepaper()
    selectedChapter.value = props.state.chapterNum.value || 1
    fetchChapterAudit(selectedChapter.value)
  }
})

watch(selectedChapter, (newNum) => {
  if (newNum) {
    fetchChapterAudit(newNum)
  }
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="state.whitepaperModalOpen?.value"
      class="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md animate-fadeIn"
      @click.self="state.closeWhitepaperModal?.()"
    >
      <div class="relative w-full max-w-5xl h-[88vh] bg-[#0c121c] border-2 border-amber-600/60 rounded-2xl shadow-2xl flex flex-col overflow-hidden text-stone-200">
        <!-- 顶部操作栏 -->
        <header class="px-5 py-3.5 bg-[#090e17] border-b border-stone-800 flex items-center justify-between flex-wrap gap-3">
          <div class="flex items-center gap-3">
            <span class="text-2xl p-2 rounded-xl bg-amber-950/80 border border-amber-600/50 text-amber-300 shadow-[0_0_15px_rgba(217,119,6,0.3)]">
              📘
            </span>
            <div>
              <h3 class="text-base sm:text-lg font-bold text-amber-200 flex items-center gap-2">
                全书生成质量追踪留底与规则迭代白皮书
                <span class="text-xs px-2 py-0.5 rounded-full bg-amber-950 text-amber-400 border border-amber-700/60 font-mono">
                  共 {{ availableChapters.length }} 章档案
                </span>
              </h3>
              <p class="text-xs text-stone-400 mt-0.5">
                追踪 Gemini 起草、朱雀客观雷达 AI 率、Codex (GPT) 靶向开刀与高频病灶套话排行榜
              </p>
            </div>
          </div>

          <!-- 右侧动作 -->
          <div class="flex items-center gap-2">
            <!-- 视图模式切换 -->
            <div class="flex items-center bg-stone-900 border border-stone-800 p-0.5 rounded-lg text-xs mr-2">
              <button
                @click="activeTab = 'whitepaper'"
                :class="[
                  'px-3 py-1 rounded font-semibold transition-all cursor-pointer flex items-center gap-1.5',
                  activeTab === 'whitepaper' ? 'bg-amber-950 text-amber-300 border border-amber-800/80 shadow-sm' : 'text-stone-400 hover:text-stone-200'
                ]"
                type="button"
              >
                <span>📈</span><span>全书迭代白皮书</span>
              </button>
              <button
                @click="activeTab = 'chapter'"
                :class="[
                  'px-3 py-1 rounded font-semibold transition-all cursor-pointer flex items-center gap-1.5',
                  activeTab === 'chapter' ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/80 shadow-sm' : 'text-stone-400 hover:text-stone-200'
                ]"
                type="button"
              >
                <span>📑</span><span>单章留底档案库</span>
              </button>
            </div>

            <button
              @click="copyToClipboard(activeTab === 'whitepaper' ? whitepaperText : chapterAuditMd, activeTab === 'whitepaper' ? '白皮书' : `第${selectedChapter}章留底档案`)"
              type="button"
              class="px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-200 border border-stone-600 text-xs font-semibold flex items-center gap-1 transition-all cursor-pointer"
            >
              <span>📋</span><span>复制</span>
            </button>
            <button
              @click="downloadText(activeTab === 'whitepaper' ? whitepaperText : chapterAuditMd, activeTab === 'whitepaper' ? 'book_iteration_whitepaper.md' : `chapter_${selectedChapter}_audit.md`)"
              type="button"
              class="px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-200 border border-stone-600 text-xs font-semibold flex items-center gap-1 transition-all cursor-pointer"
            >
              <span>📥</span><span>导出</span>
            </button>
            <button
              @click="fetchWhitepaper"
              type="button"
              class="px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-amber-300 border border-stone-600 text-xs font-semibold flex items-center gap-1 transition-all cursor-pointer"
              title="重新聚合各章档案并更新分析"
            >
              <span>🔄</span><span>刷新分析</span>
            </button>
            <button
              @click="state.closeWhitepaperModal?.()"
              type="button"
              class="p-1.5 rounded-lg hover:bg-stone-800 text-stone-400 hover:text-stone-200 transition-colors cursor-pointer"
            >
              ✕
            </button>
          </div>
        </header>

        <!-- 提示 Toast -->
        <Transition name="fade">
          <div v-if="copyToast" class="absolute top-16 right-6 z-50 px-3.5 py-1.5 rounded-lg bg-amber-900 border border-amber-500 text-white text-xs font-bold shadow-xl">
            {{ copyToast }}
          </div>
        </Transition>

        <!-- 视口 1: 全书迭代白皮书总览 -->
        <div v-show="activeTab === 'whitepaper'" class="flex-1 overflow-y-auto p-6 bg-[#090d14] text-stone-300 leading-relaxed font-sans text-xs sm:text-sm">
          <div v-if="loading" class="text-center py-16 text-stone-500 italic">
            正在全面扫描各章留底档案并聚合生成白皮书...
          </div>
          <div v-else class="max-w-4xl mx-auto whitespace-pre-wrap font-sans space-y-4">
            {{ whitepaperText }}
          </div>
        </div>

        <!-- 视口 2: 单章留底档案库 -->
        <div v-show="activeTab === 'chapter'" class="flex-1 flex flex-col overflow-hidden bg-[#090d14]">
          <!-- 章节选择横条 -->
          <div class="px-5 py-2.5 bg-stone-900/80 border-b border-stone-800 flex items-center justify-between gap-3 flex-wrap text-xs">
            <div class="flex items-center gap-1.5 overflow-x-auto py-1">
              <span class="text-stone-500 font-semibold mr-1">选择章节档案:</span>
              <button
                v-for="num in availableChapters"
                :key="num"
                @click="selectedChapter = num"
                :class="[
                  'px-2.5 py-1 rounded font-mono font-bold transition-all cursor-pointer',
                  selectedChapter === num
                    ? 'bg-amber-600 text-white shadow-sm ring-1 ring-amber-400 scale-105'
                    : 'bg-stone-800 text-stone-400 hover:bg-stone-700 hover:text-stone-200'
                ]"
                type="button"
              >
                第 {{ num }} 章
              </button>
            </div>

            <div v-if="chapterAuditData" class="flex items-center gap-3 text-stone-400 text-xs font-mono">
              <span>模式: <strong class="text-amber-300">{{ chapterAuditData.pipeline_mode }}</strong></span>
              <span>初稿: <strong class="text-stone-200">{{ chapterAuditData.metrics?.draft_chars }} 字</strong></span>
              <span>定稿: <strong class="text-emerald-400">{{ chapterAuditData.metrics?.polished_chars }} 字</strong></span>
            </div>
          </div>

          <!-- 单章 Markdown 内容展示 -->
          <div class="flex-1 overflow-y-auto p-6 text-stone-300 whitespace-pre-wrap font-sans text-xs sm:text-sm leading-relaxed max-w-4xl mx-auto w-full">
            {{ chapterAuditMd }}
          </div>
        </div>

        <!-- 底部状态条 -->
        <footer class="px-5 py-2.5 bg-[#080c13] border-t border-stone-800/80 flex items-center justify-between text-xs text-stone-500">
          <span>📂 物理留底目录: <code class="text-stone-400 font-mono">output/&lt;项目&gt;/audit_trails/chapter_*_audit.md</code></span>
          <span>每一章生成定稿后自动追加入库，完结后一键提炼整书写作 Prompt 负向禁令</span>
        </footer>
      </div>
    </div>
  </Teleport>
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
