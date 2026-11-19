<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'
import StepCard from '@/components/StepCard.vue'
import StreamOutput from '@/components/StreamOutput.vue'

const props = defineProps<{ state: ReturnType<typeof useWorkshopState> }>()

const activeTab = ref<'directory' | 'chapter' | 'audit'>('directory')
const copyMsg = ref('')
const singleCopyMsg = ref<Record<number, string>>({})
const searchQuery = ref('')
const customBatchGuidance = ref('')

// 当前章节译文展示
const activeEnContent = computed(() => {
  if (props.state.translateState.value.running) {
    return props.state.translateState.value.result
  }
  return props.state.translateResult.value || ''
})

const wordCount = computed(() => {
  const text = activeEnContent.value
  if (!text.trim()) return 0
  return text.trim().split(/\s+/).length
})

const charCount = computed(() => {
  return activeEnContent.value.length
})

// 当前选中章节对应的英文章名
const currentChapterEnTitle = computed(() => {
  const list = props.state.directoryEnChapters.value || []
  const found = list.find(c => c.num === props.state.chapterNum.value)
  return found?.title_en || ''
})

// 过滤后的目录列表
const filteredChapters = computed(() => {
  const list = props.state.directoryEnChapters.value || []
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return list
  return list.filter(item => {
    const numMatch = String(item.num).includes(q) || `第${item.num}章`.includes(q) || `ch.${item.num}`.toLowerCase().includes(q) || `ch ${item.num}`.toLowerCase().includes(q)
    const zhMatch = item.title_zh?.toLowerCase().includes(q)
    const enMatch = item.title_en?.toLowerCase().includes(q)
    return numMatch || zhMatch || enMatch
  })
})

onMounted(() => {
  props.state.loadDirectoryEn()
  props.state.loadChapterEn(props.state.chapterNum.value)
})

function showCopyToast(msg: string) {
  copyMsg.value = msg
  setTimeout(() => { copyMsg.value = '' }, 3500)
}

async function copyEnglishText() {
  const text = activeEnContent.value
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    showCopyToast('✅ 英文正文已复制到剪贴板！')
  } catch {
    showCopyToast('❌ 复制失败，请手动选中文本复制')
  }
}

// 复制单个章节标题
async function copySingleTitle(num: number, title: string) {
  if (!title) return
  try {
    await navigator.clipboard.writeText(title)
    singleCopyMsg.value[num] = '已复制'
    setTimeout(() => {
      delete singleCopyMsg.value[num]
    }, 2000)
  } catch {
    // fallback
  }
}

// 批量复制全书目录
async function copyAllDirectory(format: 'full' | 'clean' | 'bilingual') {
  const list = props.state.directoryEnChapters.value || []
  if (!list.length) {
    showCopyToast('⚠️ 暂无英文章名可复制')
    return
  }

  let text = ''
  if (format === 'full') {
    text = list.map(c => c.title_en || `Chapter ${c.num}: ${c.title_zh}`).join('\n')
  } else if (format === 'clean') {
    text = list.map(c => c.title_en_clean || c.title_en?.replace(/^Chapter\s*\d+:\s*/i, '') || c.title_zh).join('\n')
  } else if (format === 'bilingual') {
    text = list.map(c => `${c.title_en || `Chapter ${c.num}`} | ${c.title_zh}`).join('\n')
  }

  try {
    await navigator.clipboard.writeText(text)
    const formatLabel = format === 'full' ? '标准格式 (Chapter X: Title)' : (format === 'clean' ? '纯标题格式' : '中英双语对照格式')
    showCopyToast(`✅ 全书 50 章英文目录已复制到剪贴板（${formatLabel}）！`)
  } catch {
    showCopyToast('❌ 复制失败，请重试')
  }
}

// 跳转到该章正文译制
function jumpToChapterTranslate(num: number) {
  props.state.chapterNum.value = num
  props.state.loadChapterEn(num)
  activeTab.value = 'chapter'
}
</script>

<template>
  <StepCard :step="7" title="出海本地化译制 & 50章英文目录全集" description="全书50章地道爆款英文目录汇总、中英双语对照表与纯正欧美女性通俗网文正文译制">
    <div class="space-y-4">
      <!-- 顶部一级选项卡切换 -->
      <div class="flex items-center justify-between border-b border-[var(--color-parchment-darker)] pb-2 flex-wrap gap-2">
        <div class="flex items-center gap-2">
          <button
            @click="activeTab = 'directory'"
            class="px-4 py-2 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 shadow-sm"
            :class="activeTab === 'directory'
              ? 'bg-[var(--color-leather)] text-white shadow-md'
              : 'bg-white border border-[var(--color-parchment-darker)] text-[var(--color-ink)] hover:bg-[var(--color-parchment)]'"
            type="button"
          >
            <span>📚 全书 50 章英文章名全集</span>
            <span
              class="text-xs px-2 py-0.5 rounded-full"
              :class="activeTab === 'directory' ? 'bg-amber-800 text-amber-100' : 'bg-emerald-100 text-emerald-800 font-bold'"
            >
              {{ state.directoryEnChapters.value?.length || 50 }} 章已就绪
            </span>
          </button>

          <button
            @click="activeTab = 'chapter'"
            class="px-4 py-2 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 shadow-sm"
            :class="activeTab === 'chapter'
              ? 'bg-[var(--color-leather)] text-white shadow-md'
              : 'bg-white border border-[var(--color-parchment-darker)] text-[var(--color-ink)] hover:bg-[var(--color-parchment)]'"
            type="button"
          >
            <span>✍️ 逐章正文欧美译制</span>
            <span class="text-xs px-2 py-0.5 rounded-full bg-stone-100 text-stone-700">
              第 {{ state.chapterNum.value }} 章
            </span>
          </button>

          <button
            @click="activeTab = 'audit'"
            class="px-4 py-2 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 shadow-sm"
            :class="activeTab === 'audit'
              ? 'bg-[var(--color-leather)] text-white shadow-md'
              : 'bg-white border border-[var(--color-parchment-darker)] text-[var(--color-ink)] hover:bg-[var(--color-parchment)]'"
            type="button"
          >
            <span>🔍 双语质量独立自检</span>
            <span class="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 font-bold">
              第 {{ state.chapterNum.value }} 章
            </span>
          </button>
        </div>

        <!-- 快速通知提示 -->
        <div v-if="copyMsg" class="text-xs font-semibold px-3 py-1 rounded-md" :class="copyMsg.startsWith('✅') ? 'bg-green-100 text-green-800 border border-green-300' : 'bg-amber-100 text-amber-800 border border-amber-300'">
          {{ copyMsg }}
        </div>
      </div>

      <!-- ══════════════════════════════════════════════════════════════════════ -->
      <!-- TAB 1: 全书 50 章英文章名全集 (English Chapter Directory)           -->
      <!-- ══════════════════════════════════════════════════════════════════════ -->
      <div v-if="activeTab === 'directory'" class="space-y-4">
        <!-- 顶部核心工具与格式化复制栏 -->
        <div class="rounded-xl border border-amber-200 bg-gradient-to-r from-amber-50/80 via-stone-50 to-amber-50/50 p-4 shadow-sm">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div>
              <div class="flex items-center gap-2">
                <span class="text-lg">🐺</span>
                <h3 class="text-base font-bold text-stone-900">GoodNovel / Dreame / Galatea 欧美网文发布标准目录</h3>
              </div>
              <p class="text-xs text-stone-600 mt-1 leading-relaxed">
                全书50章已自动本地化重写为高完读率、强悬念钩子的欧美爆款章名规范。支持在线修改任一章名，并支持一键按平台标准格式复制上架。
              </p>
            </div>

            <!-- 批量复制按钮组 -->
            <div class="flex items-center flex-wrap gap-2">
              <button
                @click="copyAllDirectory('full')"
                class="btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5 shadow-sm"
                type="button"
                title="复制如：Chapter 1: The Torn Vow"
              >
                <span>📋</span>
                <span>复制全书英文目录 (带Chapter前缀)</span>
              </button>

              <button
                @click="copyAllDirectory('bilingual')"
                class="px-3 py-1.5 text-xs font-medium bg-white border border-[var(--color-parchment-darker)] rounded-md hover:bg-stone-100 text-stone-800 transition-colors shadow-sm flex items-center gap-1"
                type="button"
                title="复制如：Chapter 1: The Torn Vow | 撕毁的誓约"
              >
                <span>📑</span>
                <span>双语对照表</span>
              </button>

              <button
                @click="copyAllDirectory('clean')"
                class="px-3 py-1.5 text-xs font-medium bg-white border border-[var(--color-parchment-darker)] rounded-md hover:bg-stone-100 text-stone-800 transition-colors shadow-sm flex items-center gap-1"
                type="button"
                title="复制如：The Torn Vow"
              >
                <span>📝</span>
                <span>纯英文标题</span>
              </button>

              <button
                @click="state.saveDirectoryEn()"
                :disabled="state.directoryEnSaving.value"
                class="px-3 py-1.5 text-xs font-semibold bg-emerald-700 hover:bg-emerald-800 text-white rounded-md transition-colors shadow-sm flex items-center gap-1"
                type="button"
              >
                <span>💾</span>
                <span>{{ state.directoryEnSaving.value ? '保存中…' : '保存修改' }}</span>
              </button>
            </div>
          </div>
        </div>

        <!-- 目录检索与过滤工具条 -->
        <div class="flex items-center justify-between gap-3 flex-wrap bg-white p-3 rounded-lg border border-[var(--color-parchment-darker)] shadow-sm">
          <div class="flex-1 min-w-[260px] relative">
            <input
              v-model="searchQuery"
              placeholder="🔍 快速搜索章号或中英关键词（如：第1章、Tempest、Wrath、撕毁）…"
              class="w-full border border-stone-300 rounded-md pl-3 pr-8 py-1.5 text-xs text-stone-800 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
            <button
              v-if="searchQuery"
              @click="searchQuery = ''"
              class="absolute right-2 top-1.5 text-stone-400 hover:text-stone-600 text-xs"
              type="button"
            >
              ✕
            </button>
          </div>

          <div class="text-xs text-stone-500 flex items-center gap-3">
            <span>显示 <b>{{ filteredChapters.length }}</b> / {{ state.directoryEnChapters.value?.length || 0 }} 章</span>
            <button
              @click="state.loadDirectoryEn()"
              :disabled="state.directoryEnLoading.value"
              class="text-amber-800 hover:underline flex items-center gap-1"
              type="button"
            >
              <span>🔄</span>
              <span>{{ state.directoryEnLoading.value ? '刷新中…' : '刷新重载' }}</span>
            </button>
          </div>
        </div>

        <!-- 50章双语对照表格 -->
        <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-white overflow-hidden shadow-sm">
          <div class="max-h-[640px] overflow-y-auto divide-y divide-stone-100">
            <div
              v-for="item in filteredChapters"
              :key="item.num"
              class="p-3.5 hover:bg-amber-50/40 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-3 group"
              :class="state.chapterNum.value === item.num ? 'bg-amber-50/60 border-l-4 border-l-amber-600' : ''"
            >
              <!-- 左侧：章号与中文名 -->
              <div class="flex items-center gap-3 min-w-[220px]">
                <span class="inline-flex items-center justify-center w-12 h-7 rounded-md font-bold text-xs bg-stone-100 text-stone-800 border border-stone-200">
                  Ch. {{ item.num }}
                </span>
                <div>
                  <div class="text-sm font-semibold text-stone-900 flex items-center gap-2">
                    <span>第 {{ item.num }} 章</span>
                    <span class="text-stone-400">·</span>
                    <span class="text-amber-950">{{ item.title_zh }}</span>
                  </div>
                  <div v-if="item.summary" class="text-xs text-stone-500 line-clamp-1 mt-0.5" :title="item.summary">
                    {{ item.summary }}
                  </div>
                </div>
              </div>

              <!-- 中间：英文翻译标题输入框（可直接修改微调） -->
              <div class="flex-1 min-w-[280px]">
                <div class="relative">
                  <input
                    v-model="item.title_en"
                    class="w-full font-serif font-medium text-sm text-stone-900 border border-stone-200 rounded-md px-3 py-1.5 focus:border-amber-600 focus:bg-white focus:outline-none transition-all shadow-inner group-hover:border-stone-300"
                    placeholder="输入该章节的英文翻译标题…"
                  />
                  <span class="absolute right-2.5 top-2 text-[10px] text-stone-400 pointer-events-none uppercase tracking-wider font-sans">
                    EN Title
                  </span>
                </div>
              </div>

              <!-- 右侧：快捷操作按钮 -->
              <div class="flex items-center gap-1.5 flex-shrink-0">
                <!-- 复制单章英文名 -->
                <button
                  @click="copySingleTitle(item.num, item.title_en)"
                  class="px-2.5 py-1.5 text-xs rounded border border-stone-300 hover:bg-stone-100 text-stone-700 transition-colors flex items-center gap-1"
                  type="button"
                  :title="`复制第 ${item.num} 章英文名`"
                >
                  <span>{{ singleCopyMsg[item.num] ? '✅' : '📋' }}</span>
                  <span>{{ singleCopyMsg[item.num] || '复制' }}</span>
                </button>

                <!-- 跳转至正文译制 -->
                <button
                  @click="jumpToChapterTranslate(item.num)"
                  class="px-2.5 py-1.5 text-xs rounded font-medium bg-amber-100 hover:bg-amber-200 text-amber-900 transition-colors flex items-center gap-1"
                  type="button"
                  :title="`前往第 ${item.num} 章进行正文出海本地化译制`"
                >
                  <span>✍️</span>
                  <span>译制正文</span>
                </button>
              </div>
            </div>

            <!-- 空结果提示 -->
            <div v-if="filteredChapters.length === 0" class="p-8 text-center text-sm text-stone-400">
              未找到与 “{{ searchQuery }}” 匹配的章节标题
            </div>
          </div>
        </div>

        <!-- 底部一键保存提示条 -->
        <div class="flex items-center justify-between text-xs text-stone-500 pt-1">
          <span>
            提示：所有英文章名修改后点击右上角 <b>[保存修改]</b>，将自动持久化至 <code>Novel_directory_en.txt</code> 与 <code>Novel_directory_en.json</code>。
          </span>
          <button
            @click="state.saveDirectoryEn()"
            :disabled="state.directoryEnSaving.value"
            class="text-emerald-700 font-semibold hover:underline"
            type="button"
          >
            {{ state.directoryEnSaving.value ? '保存中…' : '💾 立即保存全书英文目录' }}
          </button>
        </div>
      </div>

      <!-- ══════════════════════════════════════════════════════════════════════ -->
      <!-- TAB 2: 逐章正文欧美译制 (Chapter Translation)                         -->
      <!-- ══════════════════════════════════════════════════════════════════════ -->
      <div v-show="activeTab === 'chapter'" class="space-y-3">
        <!-- 顶部控制条 -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">译制章节号</label>
            <div class="flex items-center gap-2">
              <input
                v-model.number="state.chapterNum.value"
                type="number"
                min="1"
                class="w-24 border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm"
              />
              <button
                @click="state.loadChapterEn(state.chapterNum.value)"
                class="px-2 py-1 text-xs border border-[var(--color-parchment-darker)] rounded hover:bg-[var(--color-parchment)]"
                type="button"
                title="载入该章节已保存的英文版"
              >
                🔄 载入英文版
              </button>
            </div>
            <!-- 显示该章英文章名 -->
            <div v-if="currentChapterEnTitle" class="mt-1 text-xs text-amber-900 font-serif italic truncate" :title="currentChapterEnTitle">
              📖 {{ currentChapterEnTitle }}
            </div>
          </div>

          <div class="sm:col-span-2">
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">欧美出海发布风格</label>
            <select
              v-model="state.translateStyle.value"
              class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm"
            >
              <option value="Alpha Romance (GoodNovel / Dreame / Galatea 爆款狼人言情标准)">
                🐺 Alpha/Lycan King Romance (GoodNovel / Dreame / Galatea 爆款狼人言情)
              </option>
              <option value="Dark Romance / High Tension (极虐高压强占有 / 修罗场对峙)">
                🥀 Dark Romance / High Tension (极虐高压对峙 / 强情绪拉扯)
              </option>
              <option value="Amazon / Kindle Bestseller (出版级沉浸叙事)">
                📖 Amazon / Kindle Bestseller (出版级沉浸叙事 / 细腻心理)
              </option>
              <option value="Fast-Paced ReelShort (短剧式强节奏短平快)">
                ⚡ Fast-Paced ReelShort (短平快 / 冲突秒出)
              </option>
            </select>
          </div>
        </div>

        <!-- 额外定制要求 -->
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">出海本土化微调指导（可选）</label>
          <input
            v-model="state.translateGuidance.value"
            placeholder="如：增强狼皇亚历山大的低沉威压、突出艾拉向死而生的眼神戏、强化结尾锁喉悬念钩子…"
            class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm"
          />
        </div>

        <!-- 操作与状态横幅 -->
        <div class="flex items-center justify-between flex-wrap gap-2 pt-1">
          <div class="text-xs text-[var(--color-ink-light)] flex items-center gap-2">
            <span>来源：<code>chapters/chapter_{{ state.chapterNum.value }}.txt</code></span>
            <span v-if="wordCount > 0" class="text-emerald-700 font-medium">
              | 英文词数：{{ wordCount }} words ({{ charCount }} 字符)
            </span>
          </div>

          <button
            @click="state.doTranslateChapter()"
            :disabled="state.translateState.value.running || !state.llmConfig.value"
            class="btn-primary"
            type="button"
          >
            {{ state.translateState.value.running ? '欧美地道本土化译制中…' : `▶ 本地化重写为地道美式英文 (第 ${state.chapterNum.value} 章)` }}
          </button>
        </div>

        <!-- 英文输出展示区 -->
        <StreamOutput
          :key="state.chapterNum.value"
          :progress="state.translateState.value.progress"
          :result="activeEnContent"
          :error="state.translateState.value.error"
          :running="state.translateState.value.running"
          :editable="true"
          :cancelable="true"
          placeholder="点击上方按钮，系统将自动把中文正文本地化重写为地道欧美畅销小说英文，输出将在此显示…"
          @update:result="state.translateResult.value = $event"
          @cancel="state.cancelSSE(state.translateState.value)"
        />

        <!-- 底部保存与复制栏 -->
        <div v-if="activeEnContent && !state.translateState.value.running" class="flex items-center justify-between flex-wrap gap-2 pt-1">
          <span v-if="copyMsg" class="text-xs font-medium" :class="copyMsg.startsWith('✅') ? 'text-green-600' : 'text-red-500'">
            {{ copyMsg }}
          </span>
          <span v-else class="text-xs text-stone-500">
            保存后文件存放于 <code>chapters_en/chapter_{{ state.chapterNum.value }}_en.txt</code>，可直接用于海外平台排版发布。
          </span>

          <div class="flex items-center gap-2">
            <button
              @click="copyEnglishText()"
              class="btn-sm"
              type="button"
            >
              📋 复制英文正文
            </button>
            <button
              @click="activeTab = 'audit'; state.doAuditTranslation(state.chapterNum.value)"
              :disabled="state.auditState.value.running"
              class="px-3 py-1.5 text-xs font-semibold bg-blue-50 text-blue-800 border border-blue-200 rounded-md hover:bg-blue-100 transition-colors shadow-sm flex items-center gap-1"
              type="button"
              title="对照中英文原文启动第 4 条独立质量审计"
            >
              <span>🔍</span>
              <span>独立质检审查</span>
            </button>
            <button
              @click="state.saveChapterEn()"
              :disabled="state.translateSaving.value"
              class="btn-primary"
              type="button"
            >
              {{ state.translateSaving.value ? '保存中…' : '💾 保存欧美英文版' }}
            </button>
          </div>
        </div>
      </div>

      <!-- ══════════════════════════════════════════════════════════════════════ -->
      <!-- TAB 3: 双语质量独立自检审计 (Rule 4: Dual-language Independent Audit)-->
      <!-- ══════════════════════════════════════════════════════════════════════ -->
      <div v-show="activeTab === 'audit'" class="space-y-4">
        <div class="rounded-xl border border-blue-200 bg-blue-50/60 p-4 shadow-sm">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div>
              <div class="flex items-center gap-2">
                <span class="text-lg">🛡️</span>
                <h3 class="text-base font-bold text-stone-900">第 {{ state.chapterNum.value }} 章双语质量独立自检与朱雀英文哨兵审计</h3>
              </div>
              <p class="text-xs text-stone-600 mt-1 leading-relaxed">
                严格对照【中文原稿】与【英文译文】，独立审计段落对应、修仙禁词、套话反应、限定词计数、术语一致性，并联动腾讯朱雀雷达客观扫描 AIGC 痕迹。
              </p>
            </div>

            <div class="flex items-center gap-2 flex-shrink-0">
              <button
                @click="state.doAuditTranslation(state.chapterNum.value)"
                :disabled="state.auditState.value.running || !state.llmConfig.value"
                class="btn-primary flex items-center gap-1.5 shadow-sm"
                type="button"
              >
                <span>🔍</span>
                <span>{{ state.auditState.value.running ? '正在严格逐行自检中…' : `启动第 ${state.chapterNum.value} 章独立质检` }}</span>
              </button>
            </div>
          </div>
        </div>

        <!-- 独立自检输出展示区 -->
        <StreamOutput
          :key="state.chapterNum.value"
          :progress="state.auditState.value.progress"
          :result="state.auditState.value.result"
          :error="state.auditState.value.error"
          :running="state.auditState.value.running"
          :editable="false"
          :cancelable="true"
          placeholder="点击上方「启动第 X 章独立质检」，系统将化身挑剔审校编辑，逐行对照中英原文，输出段落对应、限定词计数清单、术语一致性核对与最终通过/重译结论…"
          @cancel="state.cancelSSE(state.auditState.value)"
        />
      </div>
    </div>
  </StepCard>
</template>
