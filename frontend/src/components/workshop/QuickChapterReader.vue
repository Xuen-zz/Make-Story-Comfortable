<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'
import { generateApi } from '@/api/client'
import { useProjectStore } from '@/stores/project'

const props = defineProps<{
  state: ReturnType<typeof useWorkshopState>
}>()

const projectStore = useProjectStore()

// 阅读模式：双语对照、纯中文、纯英文
const viewMode = ref<'chinese' | 'english' | 'bilingual'>('bilingual')
const currentNum = ref<number>(1)
const loading = ref<boolean>(false)
const chineseContent = ref<string>('')
const englishContent = ref<string>('')
const copySuccess = ref<string>('')

// 目录章节信息（获取中英标题）
interface DirectoryChapter {
  num?: number
  chapter_num?: number
  title?: string
  title_zh?: string
  title_en?: string
  title_en_clean?: string
  summary?: string
}
const directoryChapters = ref<DirectoryChapter[]>([])

// 监听弹窗打开与目标章节变化
watch(
  () => props.state.quickReaderOpen.value,
  (open) => {
    if (open) {
      currentNum.value = props.state.quickReaderChapter.value || 1
      loadDirectoryInfo()
      loadChapterData(currentNum.value)
    }
  }
)

watch(
  () => props.state.quickReaderChapter.value,
  (newNum) => {
    if (props.state.quickReaderOpen.value && newNum && newNum !== currentNum.value) {
      currentNum.value = newNum
      loadChapterData(newNum)
    }
  }
)

// 加载目录英文/中文标题
async function loadDirectoryInfo() {
  try {
    const res = await generateApi.getDirectoryEn(projectStore.filepath)
    if (res.data?.chapters) {
      directoryChapters.value = res.data.chapters
    }
  } catch {
    // 忽略加载异常
  }
}

// 查阅指定章节
async function selectReadChapter(num: number) {
  if (num < 1) return
  currentNum.value = num
  props.state.quickReaderChapter.value = num
  await loadChapterData(num)
}

async function loadChapterData(num: number) {
  loading.value = true
  chineseContent.value = ''
  englishContent.value = ''
  try {
    const [zhRes, enRes] = await Promise.allSettled([
      generateApi.getChapter(num, projectStore.filepath),
      generateApi.getChapterEn(num, projectStore.filepath),
    ])

    if (zhRes.status === 'fulfilled' && zhRes.value.data?.content) {
      chineseContent.value = zhRes.value.data.content
    } else {
      chineseContent.value = '（本章暂无中文定稿/草稿，可能尚未编写）'
    }

    if (enRes.status === 'fulfilled' && enRes.value.data?.content) {
      englishContent.value = enRes.value.data.content
    } else {
      englishContent.value = '（本章暂无对应英文译稿）'
    }
  } catch (err: unknown) {
    chineseContent.value = `加载出错: ${(err as Error).message}`
  } finally {
    loading.value = false
  }
}

// 当前章节的标题计算（严格匹配目录数据）
const currentChapterInfo = computed(() => {
  const item = directoryChapters.value.find((c) => (c.num ?? c.chapter_num) === currentNum.value)
  const zhTitle = item?.title_zh || item?.title || ''
  const enTitle = item?.title_en || ''

  const formattedEn = enTitle
    ? (enTitle.startsWith('Chapter') ? enTitle : `Chapter ${currentNum.value}: ${enTitle}`)
    : `Chapter ${currentNum.value}`

  const formattedZh = zhTitle
    ? (zhTitle.startsWith('第') ? zhTitle : `第 ${currentNum.value} 章 ${zhTitle}`)
    : `第 ${currentNum.value} 章`

  return {
    titleEn: formattedEn,
    titleZh: formattedZh,
    rawEnTitle: item?.title_en_clean || enTitle,
    rawZhTitle: zhTitle,
    summary: item?.summary || '',
  }
})

// 中文字数
const zhWordCount = computed(() => {
  if (!chineseContent.value || chineseContent.value.startsWith('（本章')) return 0
  return chineseContent.value.length
})

// 英文单词数
const enWordCount = computed(() => {
  if (!englishContent.value || englishContent.value.startsWith('（本章')) return 0
  return englishContent.value.trim().split(/\s+/).filter(Boolean).length
})

// 复制底层工具
async function copyToClipboard(text: string, label: string) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copySuccess.value = `✅ ${label} 已复制到剪贴板！`
    setTimeout(() => {
      copySuccess.value = ''
    }, 2800)
  } catch {
    copySuccess.value = '❌ 复制失败，请手动选取'
  }
}

// 1. 复制英文【标题 + 正文】（GoodNovel 投稿首选用）
function copyEnWithTitle() {
  if (!englishContent.value || englishContent.value.startsWith('（本章')) {
    copyToClipboard(currentChapterInfo.value.titleEn, '英文标题')
    return
  }
  const text = `${currentChapterInfo.value.titleEn}\n\n${englishContent.value}`
  copyToClipboard(text, '英文【标题 + 正文】')
}

// 2. 仅复制英文标题
function copyEnTitleOnly() {
  copyToClipboard(currentChapterInfo.value.titleEn, '英文标题')
}

// 3. 仅复制英文正文
function copyEnProseOnly() {
  copyToClipboard(englishContent.value, '英文正文')
}

// 4. 复制中文【标题 + 正文】
function copyZhWithTitle() {
  if (!chineseContent.value || chineseContent.value.startsWith('（本章')) {
    copyToClipboard(currentChapterInfo.value.titleZh, '中文标题')
    return
  }
  const text = `${currentChapterInfo.value.titleZh}\n\n${chineseContent.value}`
  copyToClipboard(text, '中文【标题 + 正文】')
}

// 5. 仅复制中文标题
function copyZhTitleOnly() {
  copyToClipboard(currentChapterInfo.value.titleZh, '中文标题')
}

// 6. 仅复制中文正文
function copyZhProseOnly() {
  copyToClipboard(chineseContent.value, '中文正文')
}

// 7. 复制中英双语整章（含双语标题）
function copyAllBilingual() {
  const text = `=== ${currentChapterInfo.value.titleEn} | ${currentChapterInfo.value.titleZh} ===\n\n【ENGLISH TRANSLATION】\n${currentChapterInfo.value.titleEn}\n\n${englishContent.value}\n\n-------------------------\n【中文原稿】\n${currentChapterInfo.value.titleZh}\n\n${chineseContent.value}`
  copyToClipboard(text, '中英双语整章(含标题)')
}

// 导出纯英文 txt（首行带标题）
function downloadEnTxt() {
  const text = `${currentChapterInfo.value.titleEn}\n\n${englishContent.value}`
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `chapter_${currentNum.value}_en.txt`
  a.click()
  URL.revokeObjectURL(url)
}

// 后台流水线状态
const isCompilingThisChapter = computed(() => {
  return (
    props.state.pipelineRunning.value &&
    props.state.pipelineTargetChapter.value === currentNum.value
  )
})
</script>

<template>
  <Teleport to="body">
    <transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="props.state.quickReaderOpen.value"
        class="fixed inset-0 z-[100] flex items-center justify-center p-2 sm:p-4 md:p-6 bg-black/80 backdrop-blur-md"
      >
        <!-- 核心弹窗容器 -->
        <div
          class="relative w-full max-w-7xl h-[94vh] flex flex-col bg-[#0b0f17] border border-stone-700/80 rounded-2xl shadow-2xl overflow-hidden text-stone-200 font-sans"
        >
          <!-- 1. 顶部长条：实时后台生产监视条 -->
          <div
            v-if="props.state.pipelineRunning.value"
            class="px-4 py-2 bg-gradient-to-r from-cyan-950 via-[#0e2135] to-blue-950 border-b border-cyan-500/40 flex items-center justify-between text-xs text-cyan-200 flex-wrap gap-2 select-none"
          >
            <div class="flex items-center gap-2.5">
              <span class="relative flex h-2.5 w-2.5">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500"></span>
              </span>
              <span class="font-bold text-cyan-300">
                ⚡ 后台流水线正在编译 第 {{ props.state.pipelineTargetChapter.value }} 章
              </span>
              <span class="px-2 py-0.5 rounded bg-cyan-900/60 border border-cyan-600/50 text-[11px] font-mono">
                阶段 {{ props.state.pipelineCurrentStageId.value }}/6 · {{ Math.round(props.state.pipelineProgressVal.value * 100) }}%
              </span>
              <span class="text-cyan-400/80 truncate max-w-xs md:max-w-md hidden sm:inline text-[11px]">
                {{ props.state.pipelineStatusMsg.value }}
              </span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-[11px] text-cyan-400/70">
                （当前查阅已与流水线完全隔离，安全无干扰）
              </span>
              <button
                @click="props.state.openPipelineControlRoom()"
                type="button"
                class="px-2 py-0.5 rounded bg-cyan-800 hover:bg-cyan-700 text-white font-medium text-[11px] transition-colors cursor-pointer"
              >
                查看流水线大屏 ↗
              </button>
            </div>
          </div>

          <!-- 2. 控制栏：章节切换胶囊、视图模式选择、核心复制按钮组与关闭 -->
          <header class="px-5 py-3 bg-[#111722] border-b border-stone-800 flex items-center justify-between flex-wrap gap-3">
            <!-- 左侧：章节跳转与翻页 -->
            <div class="flex items-center gap-2 flex-wrap">
              <div class="flex items-center gap-1.5">
                <span class="text-xs text-stone-400 font-medium">查阅章节:</span>
                <button
                  @click="selectReadChapter(currentNum - 1)"
                  :disabled="currentNum <= 1 || loading"
                  class="px-2 py-1 text-xs rounded bg-stone-800 hover:bg-stone-700 disabled:opacity-30 disabled:cursor-not-allowed border border-stone-700 transition-colors cursor-pointer"
                  type="button"
                  title="上一章"
                >
                  ◀
                </button>
                <span class="px-2.5 py-1 text-sm font-bold text-amber-400 bg-black/40 rounded border border-stone-700 font-mono">
                  第 {{ currentNum }} 章
                </span>
                <button
                  @click="selectReadChapter(currentNum + 1)"
                  :disabled="currentNum >= props.state.numChapters.value || loading"
                  class="px-2 py-1 text-xs rounded bg-stone-800 hover:bg-stone-700 disabled:opacity-30 disabled:cursor-not-allowed border border-stone-700 transition-colors cursor-pointer"
                  type="button"
                  title="下一章"
                >
                  ▶
                </button>
              </div>

              <!-- 已有章节胶囊列表（水平滚动） -->
              <div class="flex items-center gap-1 overflow-x-auto max-w-xs md:max-w-md py-0.5 px-2 bg-stone-900/90 rounded-lg border border-stone-800">
                <button
                  v-for="ch in props.state.existingChapters.value"
                  :key="ch.num"
                  @click="selectReadChapter(ch.num)"
                  type="button"
                  class="px-2 py-0.5 rounded text-xs font-mono font-bold transition-all whitespace-nowrap cursor-pointer select-none"
                  :class="ch.num === currentNum
                    ? 'bg-amber-500 text-stone-950 shadow-md ring-2 ring-amber-300'
                    : (ch.num === props.state.pipelineTargetChapter.value && props.state.pipelineRunning.value
                        ? 'bg-cyan-950 text-cyan-300 border border-cyan-500 animate-pulse'
                        : 'bg-stone-800 text-stone-300 hover:bg-stone-700 border border-stone-700/60')"
                  :title="`查看第 ${ch.num} 章${ch.num === props.state.pipelineTargetChapter.value && props.state.pipelineRunning.value ? ' (正在后台生产)' : ''}`"
                >
                  <span v-if="ch.num === props.state.pipelineTargetChapter.value && props.state.pipelineRunning.value">⚡</span>
                  {{ ch.num }}
                </button>
              </div>
            </div>

            <!-- 右侧：视图切换、多功能复制菜单与退出 -->
            <div class="flex items-center gap-2 flex-wrap">
              <!-- 视图模式切换 -->
              <div class="flex items-center p-0.5 bg-stone-900 rounded-lg border border-stone-800 text-xs">
                <button
                  @click="viewMode = 'bilingual'"
                  type="button"
                  class="px-2.5 py-1 rounded-md transition-all font-medium cursor-pointer"
                  :class="viewMode === 'bilingual' ? 'bg-indigo-600 text-white shadow' : 'text-stone-400 hover:text-stone-200'"
                >
                  🪞 双语对照
                </button>
                <button
                  @click="viewMode = 'english'"
                  type="button"
                  class="px-2.5 py-1 rounded-md transition-all font-medium cursor-pointer"
                  :class="viewMode === 'english' ? 'bg-cyan-600 text-white shadow' : 'text-stone-400 hover:text-stone-200'"
                >
                  🇺🇸 纯英文
                </button>
                <button
                  @click="viewMode = 'chinese'"
                  type="button"
                  class="px-2.5 py-1 rounded-md transition-all font-medium cursor-pointer"
                  :class="viewMode === 'chinese' ? 'bg-amber-600 text-white shadow' : 'text-stone-400 hover:text-stone-200'"
                >
                  🇨🇳 纯中文
                </button>
              </div>

              <!-- 🌟 核心高亮复制按钮：直接复制【英文标题+正文】(GoodNovel格式) 🌟 -->
              <button
                @click="copyEnWithTitle()"
                type="button"
                class="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold flex items-center gap-1.5 shadow-[0_0_12px_rgba(16,185,129,0.3)] transition-all cursor-pointer active:scale-95"
                title="一键复制【英文标题 + 整篇正文】，可直接粘到 GoodNovel/Dreame 后台发布"
              >
                <span>📑</span>
                <span>复制英文(含标题)</span>
              </button>

              <button
                @click="copyEnTitleOnly()"
                type="button"
                class="px-2.5 py-1.5 text-xs rounded-lg bg-indigo-950/90 hover:bg-indigo-900 border border-indigo-700/60 text-indigo-200 font-semibold flex items-center gap-1 transition-all cursor-pointer active:scale-95"
                title="仅复制本章英文章名 (如 Chapter 1: The Torn Vow)"
              >
                <span>🏷️</span>
                <span class="hidden sm:inline">英文标题</span>
              </button>

              <button
                @click="copyZhWithTitle()"
                type="button"
                class="px-2.5 py-1.5 text-xs rounded-lg bg-amber-950/80 hover:bg-amber-900 border border-amber-700/60 text-amber-200 font-semibold flex items-center gap-1 transition-all cursor-pointer active:scale-95"
                title="一键复制【中文标题 + 整篇正文】"
              >
                <span>📑</span>
                <span class="hidden sm:inline">中文(含标题)</span>
              </button>

              <!-- 导出纯英文 txt 文件 -->
              <button
                @click="downloadEnTxt()"
                type="button"
                class="p-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300 border border-stone-700 transition-colors cursor-pointer"
                title="导出纯英文 txt 文件（首行已附带英文标题）"
              >
                📥
              </button>

              <!-- 关闭按钮 -->
              <button
                @click="props.state.closeQuickReader()"
                type="button"
                class="p-1.5 rounded-lg bg-stone-800 hover:bg-red-900 text-stone-400 hover:text-red-200 border border-stone-700 transition-colors cursor-pointer ml-1"
                title="关闭查阅窗口 (Esc)"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </header>

          <!-- 3. 本章标题横幅与复制提示条 -->
          <div class="px-5 py-3 bg-gradient-to-r from-[#141b29] via-[#111722] to-[#141b29] border-b border-stone-800 flex items-center justify-between text-xs flex-wrap gap-2">
            <!-- 标题展示与一键点按复制 -->
            <div class="flex items-center gap-3 flex-wrap">
              <div class="flex items-center gap-2">
                <span class="text-[11px] text-stone-400 font-mono">EN:</span>
                <span
                  @click="copyEnTitleOnly()"
                  class="font-bold text-cyan-300 text-base font-serif select-all cursor-pointer hover:underline hover:text-cyan-200 transition-colors tracking-wide"
                  title="点击直接复制此英文标题"
                >
                  {{ currentChapterInfo.titleEn }}
                </span>
              </div>
              <span class="text-stone-600">|</span>
              <div class="flex items-center gap-2">
                <span class="text-[11px] text-stone-400 font-mono">ZH:</span>
                <span
                  @click="copyZhTitleOnly()"
                  class="font-bold text-amber-300 text-sm select-all cursor-pointer hover:underline hover:text-amber-200 transition-colors"
                  title="点击直接复制此中文标题"
                >
                  {{ currentChapterInfo.titleZh }}
                </span>
              </div>
              <span v-if="isCompilingThisChapter" class="px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-500 text-[10px] animate-pulse">
                ⚡ 正在流水线生产中...
              </span>
            </div>

            <div class="flex items-center gap-3 text-stone-400 font-mono text-[11px]">
              <span v-if="enWordCount > 0" class="text-cyan-300/90 font-bold">英文: {{ enWordCount.toLocaleString() }} Words</span>
              <span v-if="zhWordCount > 0" class="text-amber-300/90 font-bold">中文: {{ zhWordCount.toLocaleString() }} 字</span>
              <span v-if="copySuccess" class="text-emerald-400 font-bold animate-bounce text-xs bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-500/50">
                {{ copySuccess }}
              </span>
            </div>
          </div>

          <!-- 4. 正文展示主体区域（首部内嵌标题卡片，确保所见即所得） -->
          <main class="flex-1 overflow-hidden relative">
            <!-- 加载骨架屏 -->
            <div v-if="loading" class="absolute inset-0 flex items-center justify-center bg-black/60 z-10">
              <div class="flex flex-col items-center gap-3 text-amber-400">
                <svg class="w-8 h-8 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span class="text-xs font-medium tracking-wide">正在极速调阅第 {{ currentNum }} 章内容...</span>
              </div>
            </div>

            <!-- 双语分屏模式 (bilingual) -->
            <div v-if="viewMode === 'bilingual'" class="h-full grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-stone-800">
              <!-- 左侧：中文稿 -->
              <section class="h-full flex flex-col overflow-hidden bg-[#0c1017]">
                <div class="px-4 py-2 bg-stone-900/80 border-b border-stone-800 flex items-center justify-between text-xs text-stone-400">
                  <span class="font-semibold text-amber-300 flex items-center gap-1.5">
                    <span>🇨🇳</span>
                    <span>中文原稿 / 定稿</span>
                  </span>
                  <div class="flex items-center gap-1.5">
                    <button
                      @click="copyZhTitleOnly()"
                      class="px-2 py-0.5 text-[11px] rounded bg-stone-800 hover:bg-stone-700 text-stone-300 cursor-pointer transition-colors border border-stone-700"
                    >
                      复制标题
                    </button>
                    <button
                      @click="copyZhWithTitle()"
                      class="px-2 py-0.5 text-[11px] rounded bg-amber-900/80 hover:bg-amber-800 text-amber-200 cursor-pointer transition-colors font-medium border border-amber-700/60"
                    >
                      复制标题+正文
                    </button>
                  </div>
                </div>
                <div class="flex-1 p-5 overflow-y-auto leading-relaxed text-stone-300 text-sm select-text font-serif">
                  <!-- 正文顶部内嵌章节标题卡片（支持划选） -->
                  <div class="mb-5 p-3.5 rounded-xl bg-amber-950/30 border border-amber-700/40 flex items-center justify-between flex-wrap gap-2">
                    <div>
                      <div class="text-[10px] font-mono text-amber-500 font-semibold">【中文章节标题】</div>
                      <h2
                        @click="copyZhTitleOnly()"
                        class="text-lg font-bold text-amber-200 mt-0.5 select-all hover:text-amber-100 cursor-pointer transition-colors"
                        title="点击复制中文标题"
                      >
                        {{ currentChapterInfo.titleZh }}
                      </h2>
                    </div>
                    <button
                      @click="copyZhWithTitle()"
                      class="px-2.5 py-1 rounded bg-amber-600 hover:bg-amber-500 text-stone-950 text-xs font-bold transition-all cursor-pointer shadow-sm active:scale-95"
                    >
                      📑 复制本章(含标题)
                    </button>
                  </div>
                  <div class="whitespace-pre-wrap leading-relaxed">
                    {{ chineseContent }}
                  </div>
                </div>
              </section>

              <!-- 右侧：英文译稿 -->
              <section class="h-full flex flex-col overflow-hidden bg-[#0a0e14]">
                <div class="px-4 py-2 bg-stone-900/80 border-b border-stone-800 flex items-center justify-between text-xs text-stone-400">
                  <span class="font-semibold text-cyan-300 flex items-center gap-1.5">
                    <span>🇺🇸</span>
                    <span>英文终稿译文 (Native English)</span>
                  </span>
                  <div class="flex items-center gap-1.5">
                    <button
                      @click="copyEnTitleOnly()"
                      class="px-2 py-0.5 text-[11px] rounded bg-stone-800 hover:bg-stone-700 text-stone-300 cursor-pointer transition-colors border border-stone-700"
                    >
                      复制标题
                    </button>
                    <button
                      @click="copyEnWithTitle()"
                      class="px-2 py-0.5 text-[11px] rounded bg-emerald-900/90 hover:bg-emerald-800 text-emerald-200 cursor-pointer transition-colors font-bold border border-emerald-600/60 shadow"
                    >
                      📑 复制标题+正文
                    </button>
                  </div>
                </div>
                <div class="flex-1 p-5 overflow-y-auto leading-relaxed text-stone-200 text-sm select-text font-serif">
                  <!-- 正文顶部内嵌章节标题卡片（支持划选） -->
                  <div class="mb-5 p-3.5 rounded-xl bg-gradient-to-r from-cyan-950/60 via-indigo-950/40 to-transparent border border-cyan-600/40 flex items-center justify-between flex-wrap gap-2">
                    <div>
                      <div class="text-[10px] font-mono text-cyan-400 font-semibold tracking-wider">【OFFICIAL CHAPTER TITLE】</div>
                      <h2
                        @click="copyEnTitleOnly()"
                        class="text-lg font-bold text-white tracking-wide mt-0.5 select-all hover:text-cyan-200 cursor-pointer transition-colors"
                        title="点击复制英文标题"
                      >
                        {{ currentChapterInfo.titleEn }}
                      </h2>
                    </div>
                    <button
                      @click="copyEnWithTitle()"
                      class="px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all cursor-pointer shadow-[0_0_12px_rgba(16,185,129,0.3)] active:scale-95"
                    >
                      📑 复制英文(含标题)
                    </button>
                  </div>
                  <div class="whitespace-pre-wrap leading-relaxed">
                    {{ englishContent }}
                  </div>
                </div>
              </section>
            </div>

            <!-- 纯英文模式 (english) -->
            <div v-else-if="viewMode === 'english'" class="h-full flex flex-col overflow-hidden bg-[#0a0e14]">
              <div class="px-5 py-2.5 bg-stone-900/80 border-b border-stone-800 flex items-center justify-between text-xs text-stone-400">
                <span class="font-semibold text-cyan-300">🇺🇸 英文终稿译文 (Native English)</span>
                <div class="flex items-center gap-2">
                  <button
                    @click="copyEnTitleOnly()"
                    class="px-2.5 py-1 text-xs rounded bg-stone-800 hover:bg-stone-700 text-stone-300 cursor-pointer transition-colors border border-stone-700"
                  >
                    复制英文标题
                  </button>
                  <button
                    @click="copyEnWithTitle()"
                    class="px-3 py-1 text-xs rounded-lg bg-emerald-600 hover:bg-emerald-500 font-bold text-white shadow cursor-pointer transition-all active:scale-95"
                  >
                    📑 复制标题 + 正文
                  </button>
                </div>
              </div>
              <div class="flex-1 p-6 sm:p-10 max-w-4xl mx-auto w-full overflow-y-auto leading-loose text-stone-100 text-base select-text font-serif">
                <!-- 顶部醒目大标题 -->
                <div class="mb-8 pb-4 border-b border-stone-800 flex items-center justify-between flex-wrap gap-3">
                  <div>
                    <span class="text-xs font-mono text-cyan-400 uppercase tracking-widest font-semibold block mb-1">Chapter Header</span>
                    <h1
                      @click="copyEnTitleOnly()"
                      class="text-2xl sm:text-3xl font-bold text-white tracking-wide select-all hover:text-cyan-200 cursor-pointer"
                      title="点击复制标题"
                    >
                      {{ currentChapterInfo.titleEn }}
                    </h1>
                  </div>
                  <button
                    @click="copyEnWithTitle()"
                    class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow transition-all cursor-pointer active:scale-95"
                  >
                    📑 一键复制整章(含标题)
                  </button>
                </div>
                <div class="whitespace-pre-wrap">
                  {{ englishContent }}
                </div>
              </div>
            </div>

            <!-- 纯中文模式 (chinese) -->
            <div v-else class="h-full flex flex-col overflow-hidden bg-[#0c1017]">
              <div class="px-5 py-2.5 bg-stone-900/80 border-b border-stone-800 flex items-center justify-between text-xs text-stone-400">
                <span class="font-semibold text-amber-300">🇨🇳 中文原稿 / 定稿</span>
                <div class="flex items-center gap-2">
                  <button
                    @click="copyZhTitleOnly()"
                    class="px-2.5 py-1 text-xs rounded bg-stone-800 hover:bg-stone-700 text-stone-300 cursor-pointer transition-colors border border-stone-700"
                  >
                    复制中文标题
                  </button>
                  <button
                    @click="copyZhWithTitle()"
                    class="px-3 py-1 text-xs rounded-lg bg-amber-600 hover:bg-amber-500 font-bold text-stone-950 shadow cursor-pointer transition-all active:scale-95"
                  >
                    📑 复制标题 + 正文
                  </button>
                </div>
              </div>
              <div class="flex-1 p-6 sm:p-10 max-w-4xl mx-auto w-full overflow-y-auto leading-loose text-stone-200 text-base select-text font-serif">
                <!-- 顶部醒目大标题 -->
                <div class="mb-8 pb-4 border-b border-stone-800 flex items-center justify-between flex-wrap gap-3">
                  <div>
                    <span class="text-xs font-mono text-amber-500 font-semibold block mb-1">章节标题</span>
                    <h1
                      @click="copyZhTitleOnly()"
                      class="text-2xl sm:text-3xl font-bold text-amber-200 select-all hover:text-amber-100 cursor-pointer"
                      title="点击复制标题"
                    >
                      {{ currentChapterInfo.titleZh }}
                    </h1>
                  </div>
                  <button
                    @click="copyZhWithTitle()"
                    class="px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-stone-950 text-xs font-bold shadow transition-all cursor-pointer active:scale-95"
                  >
                    📑 一键复制整章(含标题)
                  </button>
                </div>
                <div class="whitespace-pre-wrap">
                  {{ chineseContent }}
                </div>
              </div>
            </div>
          </main>

          <!-- 5. 底部栏：快捷翻页与提示 -->
          <footer class="px-5 py-2.5 bg-[#111722] border-t border-stone-800 flex items-center justify-between text-xs text-stone-400">
            <span class="text-[11px] text-stone-500">
              💡 提示：点击任意标题直接复制纯标题；点击「复制英文(含标题)」可直接粘贴投稿至 GoodNovel 平台。
            </span>
            <div class="flex items-center gap-2">
              <button
                @click="selectReadChapter(currentNum - 1)"
                :disabled="currentNum <= 1"
                class="px-3 py-1 rounded bg-stone-800 hover:bg-stone-700 text-stone-300 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
                type="button"
              >
                ◀ 上一章
              </button>
              <button
                @click="selectReadChapter(currentNum + 1)"
                :disabled="currentNum >= props.state.numChapters.value"
                class="px-3 py-1 rounded bg-stone-800 hover:bg-stone-700 text-stone-300 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
                type="button"
              >
                下一章 ▶
              </button>
            </div>
          </footer>
        </div>
      </div>
    </transition>
  </Teleport>
</template>
