<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'

const props = defineProps<{
  state: ReturnType<typeof useWorkshopState>
}>()

const readerMode = ref<'english' | 'bilingual'>('english')
const isModalOpen = ref(false)
const copyToast = ref('')
const fontSize = ref(15) // px

function showToast(msg: string) {
  copyToast.value = msg
  setTimeout(() => { copyToast.value = '' }, 2500)
}

function copyText(text: string, label: string) {
  if (!text) return
  navigator.clipboard.writeText(text).then(() => {
    showToast(`✅ ${label} 已复制到剪贴板`)
  }).catch(() => {
    showToast(`❌ 复制失败`)
  })
}

// 对应章节的英文与中文标题解析
const currentChapterEnItem = computed(() => {
  const num = props.state.chapterNum.value
  return props.state.directoryEnChapters.value.find(item => item.num === num)
})

const currentTitleZh = computed(() => {
  if (currentChapterEnItem.value?.title_zh) {
    return currentChapterEnItem.value.title_zh
  }
  // 兜底：从 blueprint 中解析 "第 X 章 - 标题"
  const bpText = props.state.bp.value.result || props.state.generateStore.blueprintContent || ''
  const m = bpText.match(new RegExp(`第\\s*${props.state.chapterNum.value}\\s*章\\s*[-:：]\\s*([^\\n]+)`))
  return m ? m[1].trim() : ''
})

const currentTitleEnClean = computed(() => {
  if (currentChapterEnItem.value?.title_en_clean) {
    return currentChapterEnItem.value.title_en_clean
  }
  if (currentChapterEnItem.value?.title_en) {
    return currentChapterEnItem.value.title_en.replace(/^Chapter\s*\d+\s*:\s*/i, '').trim()
  }
  return ''
})

// 规范化的英文章节全名（例如 "Chapter 1: The Torn Vow"）
const currentFullTitleEn = computed(() => {
  const item = currentChapterEnItem.value
  if (item?.title_en) {
    return item.title_en.startsWith('Chapter') ? item.title_en : `Chapter ${item.num}: ${item.title_en}`
  }
  if (currentTitleEnClean.value) {
    return `Chapter ${props.state.chapterNum.value}: ${currentTitleEnClean.value}`
  }
  return currentTitleZh.value
    ? `Chapter ${props.state.chapterNum.value}: ${currentTitleZh.value}`
    : `Chapter ${props.state.chapterNum.value}`
})

// 双语对照标题（例如 "Chapter 1: The Torn Vow | 撕毁的誓约"）
const currentFullTitleBilingual = computed(() => {
  const en = currentFullTitleEn.value
  const zh = currentTitleZh.value
  return zh ? `${en} | ${zh}` : en
})

// 动态兜底数据
const displayTranslation = computed(() => {
  return props.state.pipelineData.value.translation || props.state.translateResult.value || props.state.translateState.value.result || ''
})

const displayPolished = computed(() => {
  return props.state.pipelineData.value.polished || props.state.expandNew.value || props.state.chapter.value.result || ''
})

const englishWordCount = computed(() => {
  const t = displayTranslation.value
  if (!t.trim()) return 0
  return t.trim().split(/\s+/).length
})

const polishedWordCount = computed(() => {
  return displayPolished.value.length
})

// 一键复制【标题 + 英文正文】，方便直接粘贴至海外书站后台发布
function copyTitleAndProse() {
  const title = currentFullTitleEn.value
  const text = displayTranslation.value
  if (!text) {
    copyText(title, '英文标题')
    return
  }
  const fullContent = `${title}\n\n${text}`
  navigator.clipboard.writeText(fullContent).then(() => {
    showToast(`✅ 已复制【英文标题 + 正文】`)
  }).catch(() => {
    showToast(`❌ 复制失败`)
  })
}

function downloadEnTxt() {
  const title = currentFullTitleEn.value
  const text = displayTranslation.value
  if (!text) return
  const fullContent = `${title}\n\n${text}`
  const blob = new Blob([fullContent], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `chapter_${props.state.chapterNum.value}_en.txt`
  a.click()
  URL.revokeObjectURL(url)
  showToast(`📥 已导出带标题的 chapter_${props.state.chapterNum.value}_en.txt`)
}

async function reloadTranslation() {
  await props.state.loadChapterEn(props.state.chapterNum.value)
  await props.state.loadChapterArtifacts(props.state.chapterNum.value)
  if (props.state.directoryEnChapters.value.length === 0) {
    await props.state.loadDirectoryEn()
  }
  showToast(`🔄 已重新从本地磁盘读取第 ${props.state.chapterNum.value} 章译文与目录`)
}

// 格式化英文段落
const englishParagraphs = computed(() => {
  const raw = displayTranslation.value.trim()
  if (!raw) return []
  return raw.split(/\n\s*\n/).map(p => p.trim()).filter(Boolean)
})

// 格式化中文段落
const polishedParagraphs = computed(() => {
  const raw = displayPolished.value.trim()
  if (!raw) return []
  return raw.split(/\n+/).map(p => p.trim()).filter(Boolean)
})

onMounted(async () => {
  if (!displayTranslation.value) {
    await props.state.loadChapterEn(props.state.chapterNum.value)
  }
  if (props.state.directoryEnChapters.value.length === 0) {
    await props.state.loadDirectoryEn()
  }
})

watch(() => props.state.chapterNum.value, async (newVal) => {
  if (newVal) {
    await props.state.loadChapterEn(newVal)
  }
})
</script>

<template>
  <div
    id="pipeline-translation-reader"
    class="rounded-2xl border-2 border-indigo-900/60 bg-gradient-to-br from-[#0c121e] via-[#101728] to-[#0c121e] text-stone-200 shadow-2xl overflow-hidden mb-6 transition-all duration-300"
  >
    <!-- 头部工具栏 -->
    <div class="px-5 py-4 border-b border-indigo-950/80 bg-[#0d1526]/95 flex items-center justify-between flex-wrap gap-4">
      <!-- 标题与状态标签 -->
      <div class="flex items-center gap-3.5">
        <div class="w-11 h-11 rounded-xl bg-gradient-to-br from-indigo-500/25 to-cyan-600/35 border border-indigo-400/60 flex items-center justify-center text-2xl shadow-[0_0_20px_rgba(99,102,241,0.35)]">
          🇺🇸
        </div>
        <div>
          <div class="flex items-center gap-2.5 flex-wrap">
            <h3 class="text-base sm:text-lg font-bold text-indigo-200 tracking-wide flex items-center gap-2">
              出海美式英文译文展示专区
              <span class="text-xs px-2.5 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-500/60 font-mono shadow-sm">
                第 {{ state.chapterNum.value }} 章
              </span>
            </h3>
            <span
              v-if="englishWordCount > 0"
              class="text-xs font-mono font-bold px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-500/60 flex items-center gap-1"
            >
              <span>✓ 就绪</span>
              <span>({{ englishWordCount }} Words)</span>
            </span>
            <span
              v-else
              class="text-xs font-mono px-2 py-0.5 rounded bg-stone-900 text-stone-500 border border-stone-800"
            >
              待生成 / 未就绪
            </span>
          </div>
          <div class="text-xs text-stone-400 mt-0.5 flex items-center gap-2 flex-wrap">
            <span>标准：</span>
            <span class="text-indigo-300 font-semibold">{{ state.translateStyle.value }}</span>
            <span class="text-stone-600">|</span>
            <span class="text-stone-300">纯正母语语感 · 动作微反应还原 · 零仙侠杂质词</span>
          </div>
        </div>
      </div>

      <!-- 右侧阅读模式与操作按钮组 -->
      <div class="flex items-center gap-2.5 flex-wrap">
        <!-- 阅读模式切换器 -->
        <div class="flex items-center bg-stone-900/90 border border-stone-800 p-0.5 rounded-lg text-xs font-semibold">
          <button
            @click="readerMode = 'english'"
            :class="[
              'px-3 py-1.5 rounded-md transition-all cursor-pointer flex items-center gap-1',
              readerMode === 'english' ? 'bg-indigo-600 text-white shadow-md' : 'text-stone-400 hover:text-stone-200'
            ]"
          >
            <span>🇺🇸</span>
            <span>英文专注</span>
          </button>
          <button
            @click="readerMode = 'bilingual'"
            :class="[
              'px-3 py-1.5 rounded-md transition-all cursor-pointer flex items-center gap-1',
              readerMode === 'bilingual' ? 'bg-indigo-600 text-white shadow-md' : 'text-stone-400 hover:text-stone-200'
            ]"
          >
            <span>🇨🇳/🇺🇸</span>
            <span>双语对照</span>
          </button>
        </div>

        <!-- 提示信息 -->
        <span v-if="copyToast" class="text-emerald-400 font-semibold text-xs animate-pulse">
          {{ copyToast }}
        </span>

        <!-- 复制英文正文 -->
        <button
          @click="copyText(displayTranslation, '美式英文正文')"
          :disabled="!displayTranslation"
          class="px-3 py-1.5 rounded-lg bg-indigo-950/80 hover:bg-indigo-900 border border-indigo-700/60 text-indigo-200 text-xs font-semibold transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5 active:scale-95"
          title="一键复制当前章整篇英文正文（不含标题）"
        >
          <span>📋</span>
          <span>复制正文</span>
        </button>

        <!-- 导出 .txt -->
        <button
          @click="downloadEnTxt"
          :disabled="!displayTranslation"
          class="px-3 py-1.5 rounded-lg bg-[#141d2e] hover:bg-[#1b263b] border border-stone-700 text-stone-300 text-xs font-semibold transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5 active:scale-95"
          title="导出当前章纯英文 txt 文件（首行已包含英文标题）"
        >
          <span>📥</span>
          <span>导出.txt</span>
        </button>

        <!-- 重新从磁盘读取 -->
        <button
          @click="reloadTranslation"
          class="p-1.5 rounded-lg bg-stone-900 hover:bg-stone-800 border border-stone-700 text-stone-300 text-xs transition-colors cursor-pointer"
          title="强制重新从磁盘读取当前章译文与目录"
        >
          🔄
        </button>

        <!-- 弹窗全屏阅读 -->
        <button
          @click="isModalOpen = true"
          :disabled="!displayTranslation"
          class="px-3 py-1.5 rounded-lg bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-600/60 text-cyan-300 text-xs font-semibold transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5 active:scale-95"
          title="全屏弹窗专注沉浸式阅读"
        >
          <span>⛶</span>
          <span>弹窗阅读</span>
        </button>
      </div>
    </div>

    <!-- 🌟 专设：对应章节名字展示与一键复制横幅 🌟 -->
    <div class="px-5 py-3.5 bg-gradient-to-r from-[#12192c] via-[#161d33] to-[#12192c] border-b border-indigo-950/70 flex items-center justify-between flex-wrap gap-3">
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 rounded-lg bg-indigo-900/50 border border-indigo-600/40 flex items-center justify-center text-sm shadow">
          🏷️
        </div>
        <div>
          <div class="flex items-center gap-2 flex-wrap">
            <!-- 英文全标题，大字号、高亮、支持划选或一键点击复制 -->
            <span
              @click="copyText(currentFullTitleEn, '英文标题')"
              class="text-base sm:text-lg font-bold font-serif text-white hover:text-indigo-200 transition-colors cursor-pointer select-all tracking-wide"
              title="点击标题即可直接复制"
            >
              {{ currentFullTitleEn }}
            </span>
            <!-- 中文对照标签 -->
            <span
              v-if="currentTitleZh"
              class="text-xs px-2.5 py-0.5 rounded-full bg-indigo-950/90 text-indigo-300 border border-indigo-700/60 font-sans flex items-center gap-1"
            >
              <span>🇨🇳</span>
              <span>{{ currentTitleZh }}</span>
            </span>
          </div>
          <p class="text-[11px] text-stone-400 mt-0.5 font-sans">
            对应海外出版规范英文章名 · 支持独立复制标题，或一键打包复制【标题+正文】
          </p>
        </div>
      </div>

      <!-- 快捷复制按钮组 -->
      <div class="flex items-center gap-2 flex-wrap">
        <button
          @click="copyText(currentFullTitleEn, '英文标题')"
          class="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow transition-all cursor-pointer active:scale-95"
          title="仅复制英文章名（如 Chapter 1: The Torn Vow）"
        >
          <span>📋 复制英文标题</span>
        </button>
        <button
          v-if="currentTitleZh"
          @click="copyText(currentFullTitleBilingual, '双语标题')"
          class="px-2.5 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300 text-xs font-semibold flex items-center gap-1 border border-stone-700 transition-all cursor-pointer active:scale-95"
          title="复制英汉双语标题（如 Chapter 1: The Torn Vow | 撕毁的誓约）"
        >
          <span>📋 复制双语标题</span>
        </button>
        <button
          @click="copyTitleAndProse()"
          :disabled="!displayTranslation"
          class="px-3 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-semibold flex items-center gap-1.5 shadow transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed active:scale-95"
          title="一键复制【英文标题 + 整篇英文正文】，可直接粘贴至海外书站后台发布"
        >
          <span>📑 复制标题+正文</span>
        </button>
      </div>
    </div>

    <!-- 主展示内容区 -->
    <div class="p-5 bg-[#090e18]">
      <!-- 尚无译文时的空态提示 -->
      <div
        v-if="!displayTranslation"
        class="py-12 px-4 rounded-xl border border-dashed border-stone-800 bg-[#070b13] flex flex-col items-center justify-center text-center text-stone-400"
      >
        <span class="text-4xl mb-3">🇺🇸</span>
        <h4 class="text-base font-bold text-stone-300 mb-1">
          第 {{ state.chapterNum.value }} 章美式英文译文尚未生成
        </h4>
        <p class="text-xs text-stone-500 max-w-md mb-4 leading-relaxed">
          全自动流水线会自动将中文草稿经过润色后直接译制为纯正出海英文。请点击上方【⚡ 启动全链路生产】开始单章自动闭环生产。
        </p>
        <div class="flex items-center gap-3">
          <button
            @click="state.doRunPipeline()"
            :disabled="state.pipelineRunning.value"
            class="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-600 to-indigo-600 text-white text-xs font-bold shadow-lg hover:brightness-110 transition-all cursor-pointer"
          >
            ⚡ 立即启动全链路生产
          </button>
          <button
            @click="reloadTranslation"
            class="px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300 text-xs font-semibold border border-stone-700 transition-colors cursor-pointer"
          >
            🔄 从本地磁盘重新扫描
          </button>
        </div>
      </div>

      <!-- 模式 1: 纯英文专注阅读模式 (English Only) -->
      <div v-else-if="readerMode === 'english'" class="space-y-4">
        <!-- 章节大标题与指标栏 -->
        <div class="flex items-center justify-between pb-3 border-b border-indigo-950/60 text-xs text-stone-400">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="font-serif text-indigo-300 text-sm font-bold">{{ currentFullTitleEn }}</span>
            <span v-if="currentTitleZh" class="text-stone-500 font-sans text-xs">({{ currentTitleZh }})</span>
            <span class="text-stone-600">/</span>
            <span class="font-mono text-stone-400">{{ englishWordCount }} Words</span>
          </div>
          <div class="flex items-center gap-2 font-mono text-[11px] text-stone-400">
            <span>字号:</span>
            <button @click="fontSize = Math.max(13, fontSize - 1)" class="w-6 h-6 rounded bg-stone-800 hover:bg-stone-700 flex items-center justify-center text-stone-200">A-</button>
            <span class="w-6 text-center text-stone-300">{{ fontSize }}</span>
            <button @click="fontSize = Math.min(22, fontSize + 1)" class="w-6 h-6 rounded bg-stone-800 hover:bg-stone-700 flex items-center justify-center text-stone-200">A+</button>
          </div>
        </div>

        <!-- 英文正文正文卡片 -->
        <div
          class="rounded-xl bg-[#0b101c] p-6 sm:p-8 border border-indigo-900/40 text-stone-100 font-sans shadow-inner selection:bg-indigo-600/40 selection:text-white max-h-[600px] overflow-y-auto space-y-4"
          :style="{ fontSize: `${fontSize}px`, lineHeight: '1.85' }"
        >
          <!-- 英文正文首部章节大标题 -->
          <div class="text-center pb-4 mb-4 border-b border-indigo-950/60">
            <h2 class="text-lg sm:text-xl font-bold font-serif text-indigo-200 tracking-wide select-all">
              {{ currentFullTitleEn }}
            </h2>
            <p v-if="currentTitleZh" class="text-xs text-stone-400 mt-1 font-sans">
              第 {{ state.chapterNum.value }} 章 · {{ currentTitleZh }}
            </p>
          </div>

          <p
            v-for="(para, i) in englishParagraphs"
            :key="i"
            class="leading-relaxed tracking-wide text-stone-200/90 hover:text-stone-100 transition-colors"
          >
            {{ para }}
          </p>
        </div>
      </div>

      <!-- 模式 2: 双语左右并排对照阅读模式 (Bilingual Split Screen) -->
      <div v-else class="space-y-3">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <!-- 左栏：中文润色正式正文 -->
          <div class="flex flex-col rounded-xl bg-[#0e1420] border border-stone-800 overflow-hidden shadow-md">
            <div class="px-4 py-2.5 bg-[#121a2a] border-b border-stone-800 flex items-center justify-between text-xs">
              <span class="font-bold text-cyan-300 flex items-center gap-1.5">
                <span>🇨🇳</span>
                <span>中文润色正式稿 (第 {{ state.chapterNum.value }} 章{{ currentTitleZh ? ` · ${currentTitleZh}` : '' }})</span>
              </span>
              <span class="font-mono text-stone-400">{{ polishedWordCount }} 字</span>
            </div>
            <div class="p-5 max-h-[550px] overflow-y-auto font-serif text-xs sm:text-sm leading-relaxed text-stone-200 space-y-3 selection:bg-cyan-500/30">
              <div v-if="!displayPolished" class="text-stone-500 italic">中文润色正文待载入...</div>
              <p v-for="(p, i) in polishedParagraphs" :key="i" class="indent-6 leading-relaxed">
                {{ p }}
              </p>
            </div>
          </div>

          <!-- 右栏：美式英文译稿 -->
          <div class="flex flex-col rounded-xl bg-[#0d1322] border border-indigo-900/50 overflow-hidden shadow-md">
            <div class="px-4 py-2.5 bg-[#141b2f] border-b border-indigo-900/60 flex items-center justify-between text-xs">
              <span class="font-bold text-indigo-300 flex items-center gap-1.5">
                <span>🇺🇸</span>
                <span>美式出海英文译文 ({{ currentFullTitleEn }})</span>
              </span>
              <span class="font-mono text-indigo-300">{{ englishWordCount }} Words</span>
            </div>
            <div class="p-5 max-h-[550px] overflow-y-auto font-sans text-xs sm:text-sm leading-relaxed text-stone-200 space-y-3 selection:bg-indigo-600/40">
              <p v-for="(para, i) in englishParagraphs" :key="i" class="leading-relaxed text-stone-200/90">
                {{ para }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 弹窗全屏专注沉浸式阅读 Modal -->
    <div
      v-if="isModalOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 sm:p-6 animate-fadeIn"
    >
      <div class="w-full max-w-4xl max-h-[92vh] bg-[#0c121d] border border-indigo-700/60 rounded-2xl shadow-2xl flex flex-col overflow-hidden text-stone-200">
        <!-- 弹窗顶部栏 -->
        <header class="px-6 py-4 bg-[#0f1624] border-b border-indigo-900/50 flex items-center justify-between flex-wrap gap-3">
          <div class="flex items-center gap-3">
            <span class="text-2xl">📖</span>
            <div>
              <div class="flex items-center gap-2 flex-wrap">
                <h2 class="text-base sm:text-lg font-bold text-indigo-200 font-serif">
                  {{ currentFullTitleEn }}
                </h2>
                <span v-if="currentTitleZh" class="text-xs px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800/60">
                  {{ currentTitleZh }}
                </span>
              </div>
              <div class="text-xs text-stone-400 mt-0.5">
                {{ englishWordCount }} Words · {{ state.translateStyle.value }}
              </div>
            </div>
          </div>

          <div class="flex items-center gap-2 flex-wrap">
            <button
              @click="copyText(currentFullTitleEn, '英文标题')"
              class="px-2.5 py-1.5 rounded-lg bg-indigo-900/80 hover:bg-indigo-800 text-indigo-200 border border-indigo-700/60 text-xs font-semibold cursor-pointer"
            >
              📋 复制标题
            </button>
            <button
              @click="copyTitleAndProse()"
              class="px-2.5 py-1.5 rounded-lg bg-emerald-800/80 hover:bg-emerald-700 text-emerald-200 border border-emerald-600/60 text-xs font-semibold cursor-pointer"
            >
              📑 复制标题+正文
            </button>
            <button
              @click="copyText(displayTranslation, '全篇英文正文')"
              class="px-2.5 py-1.5 rounded-lg bg-indigo-950 hover:bg-indigo-900 text-indigo-200 border border-indigo-700/60 text-xs font-semibold cursor-pointer"
            >
              📋 复制正文
            </button>
            <button
              @click="downloadEnTxt"
              class="px-2.5 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300 border border-stone-700 text-xs font-semibold cursor-pointer"
            >
              📥 导出 TXT
            </button>
            <button
              @click="isModalOpen = false"
              class="p-1.5 rounded-lg hover:bg-stone-800 text-stone-400 hover:text-stone-200 cursor-pointer ml-1"
              title="关闭弹窗"
            >
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </header>

        <!-- 弹窗正文滚动区 -->
        <div class="p-8 sm:p-12 overflow-y-auto font-sans leading-loose text-stone-100 max-h-[calc(92vh-130px)] space-y-5 selection:bg-indigo-600/40 text-base">
          <div class="text-center pb-5 mb-5 border-b border-indigo-950/60">
            <h1 class="text-xl sm:text-2xl font-bold font-serif text-indigo-200 tracking-wide select-all">
              {{ currentFullTitleEn }}
            </h1>
            <p v-if="currentTitleZh" class="text-xs text-stone-400 mt-1 font-sans">
              第 {{ state.chapterNum.value }} 章 · {{ currentTitleZh }}
            </p>
          </div>

          <p v-for="(para, i) in englishParagraphs" :key="i" class="leading-relaxed">
            {{ para }}
          </p>
        </div>
      </div>
    </div>
  </div>
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
