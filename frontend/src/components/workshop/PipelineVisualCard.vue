<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'

const props = defineProps<{
  state: ReturnType<typeof useWorkshopState>
}>()

const activeTab = ref<'terminal' | 'draft' | 'polish' | 'translation' | 'audit' | 'archive' | 'continuity'>('terminal')
const isExpanded = ref(true)
const copyToast = ref('')
const showAdvancedParams = ref(false)
const showIncubatorManual = ref(false)

// 是否需要展示极速孵化通道 (项目完全未建立大纲时自动激活)
const isNewBookWithoutOutline = computed(() => {
  return !props.state.bp.value.result && !props.state.arch.value.result
})

// 番茄爽点指令插入器
function appendGuidance(text: string) {
  if (!props.state.chGuidance.value || !props.state.chGuidance.value.trim()) {
    props.state.chGuidance.value = text
  } else {
    props.state.chGuidance.value = props.state.chGuidance.value.trimEnd() + '\n' + text
  }
  showToast('✅ 已插入爽点预设指令')
}

// 一键填入番茄写作法则
function fillTomatoGuidance() {
  props.state.userGuidance.value = `【番茄小说专属爆款规则】
1. 黄金三章法则：前三章节奏拉满。第1章主角陷入绝境并觉醒核心金手指/系统；第2章立刻给予即时正反馈（当场打脸/初试神通）；第3章引入外部主线危机并留下巨大悬念。
2. 爽点与情绪：反派挑衅具体直接，主角反击果断干脆，不憋屈过夜；战斗与升级提供极致情绪拉扯与震撼反馈。
3. 行文风格：语言通俗接地气，多用快节奏对话和动作细节，拒绝空洞说教和拖沓景物描写。
4. 章末留钩（核心）：每章结尾必须卡在关键节点（危机迫近/重大奖励未拆/强敌出现），严禁总结性大团圆断章！`
  showToast('✅ 番茄爆款法则已装填入创作者指导！')
}

// 快速填入热门脑洞
function pickPresetTopic(topicStr: string, genreStr = '玄幻') {
  props.state.topic.value = topicStr
  props.state.genre.value = genreStr
  fillTomatoGuidance()
  showToast('✅ 已载入经典番茄开局设定与规则！')
}

function handleFastIncubate() {
  if (!props.state.topic.value || !props.state.topic.value.trim()) {
    showToast('⚠️ 请先输入故事脑洞，或点击上方任一【番茄热梗预设】！')
    alert('请先输入故事核心脑洞，或点击上方任一【🔥 番茄热梗预设】（如“万倍返还”、“隐忍苟道”）！')
    return
  }
  props.state.doFastIncubateBook()
}

function showToast(msg: string) {
  copyToast.value = msg
  setTimeout(() => { copyToast.value = '' }, 2500)
}

function copyText(text: string, label: string) {
  if (!text) return
  navigator.clipboard.writeText(text).then(() => {
    showToast(`✅ ${label} 已复制`)
  }).catch(() => {
    showToast(`❌ 复制失败`)
  })
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

// 动态兜底数据计算（优先使用实时流水线数据，其次使用本地持久化加载数据）
const displayTranslation = computed(() => {
  return props.state.pipelineData.value.translation || props.state.translateResult.value || props.state.translateState.value.result || ''
})

const displayDraft = computed(() => {
  return props.state.pipelineData.value.draft || props.state.chapter.value.result || ''
})

const displayPolished = computed(() => {
  return props.state.pipelineData.value.polished || props.state.expandNew.value || props.state.chapter.value.result || ''
})

const displayChecklist = computed(() => {
  return props.state.pipelineData.value.checklist || ''
})

const displayAudit = computed(() => {
  return props.state.pipelineData.value.audit || props.state.auditState.value.result || ''
})

const displaySummary = computed(() => {
  return props.state.pipelineData.value.summary || ''
})

const displayCharState = computed(() => {
  return props.state.pipelineData.value.characterState || ''
})

const canonHistoryText = ref('')

async function fetchCanonHistory() {
  try {
    const fp = props.state.projectStore.activeProjectData?.filepath
    if (!fp) return
    const res = await fetch(`/api/generate/canon_history?filepath=${encodeURIComponent(fp)}`)
    if (res.ok) {
      const data = await res.json()
      canonHistoryText.value = data.canon || ''
    }
  } catch (e) {
    console.error('Failed to fetch canon history:', e)
  }
}

onMounted(() => {
  fetchCanonHistory()
})

watch(() => props.state.projectStore.activeProjectData?.filepath, () => {
  fetchCanonHistory()
})

// 当生成定稿完成后，自动切换到正式定稿视图
watch(() => props.state.pipelineRunning.value, (running, prev) => {
  if (prev && !running && displayPolished.value) {
    activeTab.value = 'polish'
  }
})

const displayCanon = computed(() => {
  return props.state.pipelineData.value.canonHistory || canonHistoryText.value || ''
})

const draftWordCount = computed(() => {
  return displayDraft.value.length
})

const polishedWordCount = computed(() => {
  return displayPolished.value.length
})

const englishWordCount = computed(() => {
  const t = displayTranslation.value
  if (!t.trim()) return 0
  return t.trim().split(/\s+/).length
})

const overallPercentage = computed(() => {
  return Math.round(props.state.pipelineProgressVal.value * 100)
})

const activeTargetChapter = computed(() => {
  return props.state.pipelineRunning.value && props.state.pipelineTargetChapter.value
    ? props.state.pipelineTargetChapter.value
    : props.state.chapterNum.value
})

async function handleNodeClick(stageId: number) {
  isExpanded.value = true
  switch (stageId) {
    case 1:
      activeTab.value = 'continuity'
      await props.state.loadHandoff(props.state.chapterNum.value > 1 ? props.state.chapterNum.value - 1 : 1)
      await fetchCanonHistory()
      break
    case 2: activeTab.value = 'draft'; break
    case 3: activeTab.value = 'polish'; break
    case 4:
      if (props.state.pipelineMode?.value === 'fast_zh') {
        activeTab.value = 'continuity'
        await props.state.loadHandoff(props.state.chapterNum.value)
        await fetchCanonHistory()
      } else {
        activeTab.value = 'translation'
        if (!displayTranslation.value) {
          await props.state.loadChapterEn(props.state.chapterNum.value)
        }
        setTimeout(() => {
          const el = document.getElementById('pipeline-translation-reader')
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' })
            el.classList.add('ring-4', 'ring-indigo-400', 'shadow-[0_0_35px_rgba(99,102,241,0.6)]')
            setTimeout(() => {
              el.classList.remove('ring-4', 'ring-indigo-400', 'shadow-[0_0_35px_rgba(99,102,241,0.6)]')
            }, 2500)
          }
        }, 50)
      }
      break
    case 5: activeTab.value = 'audit'; break
    case 6:
      activeTab.value = 'continuity'
      await props.state.loadHandoff(props.state.chapterNum.value)
      await fetchCanonHistory()
      break
    default: activeTab.value = 'terminal'
  }
}

// 组件挂载与章节变动时，自动加载该章快照（流水线运行时屏蔽外界切换污染）
onMounted(async () => {
  if (!props.state.pipelineRunning.value) {
    await props.state.loadChapterArtifacts(props.state.chapterNum.value)
    await props.state.loadHandoff(props.state.chapterNum.value > 1 ? props.state.chapterNum.value - 1 : 1)
    if (props.state.pipelineMode.value === 'bilingual') {
      await props.state.loadFixedTerms()
    }
  }
  fetchCanonHistory()
})

watch(() => props.state.chapterNum.value, async (newVal) => {
  if (newVal && !props.state.pipelineRunning.value) {
    await props.state.loadChapterArtifacts(newVal)
  }
})
</script>

<template>
  <div class="rounded-2xl border-2 border-cyan-800/70 bg-gradient-to-br from-[#0b121c] via-[#101725] to-[#0c131e] text-stone-200 shadow-2xl overflow-hidden mb-6 transition-all duration-300">
    <!-- 顶部状态与控制栏 -->
    <div class="px-5 py-4 border-b border-cyan-900/50 bg-[#0d1624]/95 flex items-center justify-between flex-wrap gap-4">
      <!-- 标题与章节指示 -->
      <div class="flex items-center gap-3.5">
        <div class="relative w-11 h-11 rounded-xl bg-gradient-to-br from-cyan-500/25 to-blue-600/35 border border-cyan-400/60 flex items-center justify-center text-2xl shadow-[0_0_20px_rgba(6,182,212,0.35)]">
          <span>🏭</span>
          <span v-if="state.pipelineRunning.value" class="absolute -top-1 -right-1 flex h-3 w-3">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-3 w-3 bg-cyan-500"></span>
          </span>
        </div>
        <div>
          <div class="flex items-center gap-2.5">
            <h3 class="text-base sm:text-lg font-bold text-cyan-200 tracking-wide flex items-center gap-2">
              全链路自动化生产中枢
              <span class="text-xs px-2.5 py-0.5 rounded-full bg-cyan-950/90 text-cyan-300 border border-cyan-500/50 font-mono shadow-[0_0_8px_rgba(6,182,212,0.3)]">
                全链路可视化看板
              </span>
            </h3>
          </div>
          <div class="text-xs text-stone-400 mt-0.5 flex items-center gap-2 flex-wrap">
            <span>生产靶标：</span>
            <strong class="text-amber-300 font-bold bg-amber-950/60 px-2 py-0.5 rounded border border-amber-600/40">
              第 {{ activeTargetChapter }} 章
              <span v-if="state.pipelineRunning.value" class="ml-1 text-[11px] text-cyan-300 font-normal">
                (生产锁定中 🔒)
              </span>
            </strong>
            <span class="text-stone-600">|</span>
            <span class="text-stone-300">
              {{ state.pipelineMode.value === 'fast_zh'
                  ? '细纲装配 ➔ 3.8 Flash Low起草 ➔ 4 Hydrogen Medium审校 ➔ 正史记忆同步 (极速4步)'
                  : '细纲装配 ➔ 3.8 Flash起草 ➔ 4 Hydrogen审校 ➔ 美式英译 ➔ 双语质检 ➔ 记忆归档 (出海6步)' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 实时状态胶囊与倒计时 -->
      <div class="flex items-center gap-3 flex-wrap">
        <!-- 运行中胶囊 -->
        <div
          v-if="state.pipelineRunning.value"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-cyan-950/90 border border-cyan-400 text-cyan-300 text-xs shadow-[0_0_15px_rgba(6,182,212,0.45)] animate-pulse"
        >
          <span class="relative flex h-2.5 w-2.5">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-500"></span>
          </span>
          <span class="font-bold">流水线全力运转中 · [阶段 {{ state.pipelineCurrentStageId.value }}/6]</span>
          <span class="font-mono text-cyan-200 bg-cyan-900/60 px-1.5 py-0.2 rounded border border-cyan-500/40">
            {{ overallPercentage }}%
          </span>
        </div>

        <!-- 质检合格胶囊 -->
        <div
          v-else-if="state.pipelineData.value.auditPass || (state.pipelineMode.value === 'bilingual' && englishWordCount > 0)"
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-950/90 border border-emerald-400 text-emerald-300 text-xs shadow-[0_0_15px_rgba(16,185,129,0.35)] animate-stamp"
        >
          <span>🛡️</span>
          <span class="font-bold">全链路产物就绪 · 独立质检合格</span>
          <span class="font-mono text-emerald-200">100%</span>
        </div>

        <!-- 待命中胶囊 -->
        <div
          v-else
          class="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-stone-900 border border-stone-700 text-stone-400 text-xs"
        >
          <span class="w-2.5 h-2.5 rounded-full bg-stone-500"></span>
          <span>待命准备就绪</span>
        </div>

        <!-- 计时器 -->
        <div class="px-3 py-1.5 rounded-lg bg-black/60 border border-stone-800 text-xs font-mono text-cyan-400 flex items-center gap-1.5 shadow-inner">
          <span class="text-stone-500">⏱️</span>
          <span class="font-bold">{{ formatElapsed(state.pipelineElapsed.value) }}</span>
        </div>

        <!-- 核心动作按钮组合 -->
        <div class="flex items-center gap-2.5 flex-wrap">
          <!-- 🍅 番茄/纯中文极速模式 VS 🌐 出海双语模式 胶囊切换 -->
          <div class="flex items-center bg-stone-950/90 border border-stone-800 p-0.5 rounded-lg text-xs shadow-inner">
            <button
              @click="state.setPipelineMode('fast_zh')"
              :class="[
                'px-2.5 py-1 rounded font-bold transition-all cursor-pointer flex items-center gap-1 select-none',
                state.pipelineMode.value === 'fast_zh'
                  ? 'bg-rose-950 text-rose-300 border border-rose-800/80 shadow-[0_0_12px_rgba(244,63,94,0.35)]'
                  : 'text-stone-400 hover:text-stone-200'
              ]"
              type="button"
              title="切换至纯中文出稿流水线（4 步：细纲装配 ➔ 3.8 Flash 起草 ➔ 4 Hydrogen 审校 ➔ 正史归档）"
            >
              <span>🇨🇳</span>
              <span>中文出稿 (4步)</span>
            </button>
            <button
              @click="state.setPipelineMode('bilingual')"
              :class="[
                'px-2.5 py-1 rounded font-bold transition-all cursor-pointer flex items-center gap-1 select-none',
                state.pipelineMode.value === 'bilingual'
                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/80 shadow-[0_0_12px_rgba(6,182,212,0.35)]'
                  : 'text-stone-400 hover:text-stone-200'
              ]"
              type="button"
              title="切换至英文出海双语流水线（完整 6 步：含美式英文翻译、固定词表与双语质检）"
            >
              <span>🌐</span>
              <span>英文出海 (6步)</span>
            </button>
          </div>

          <!-- 自动顺延下一章复选框 -->
          <label class="flex items-center gap-1.5 cursor-pointer text-xs text-stone-300 hover:text-white select-none mr-1" title="开启后，单章生产完毕将自动前进至下一章并同步大纲规划">
            <input
              type="checkbox"
              v-model="state.pipelineAutoAdvance.value"
              class="rounded border-stone-700 bg-stone-900 text-cyan-500 focus:ring-0 cursor-pointer"
            />
            <span class="text-[11px] font-mono">🔄 完工顺延下一章</span>
          </label>

          <!-- 运行 / 终止 -->
          <button
            v-if="state.pipelineRunning.value"
            @click="state.cancelPipeline()"
            type="button"
            class="px-3.5 py-1.5 rounded-lg bg-red-950 hover:bg-red-900 border border-red-500 text-red-200 text-xs font-bold transition-all cursor-pointer shadow-lg active:scale-95"
            title="强行终止当前生产流水线"
          >
            ⏹️ 终止运行
          </button>
          <button
            v-else
            @click="state.doRunPipeline()"
            type="button"
            class="px-4 py-1.5 rounded-lg bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 border border-cyan-400/80 text-white text-xs font-bold transition-all cursor-pointer shadow-[0_0_18px_rgba(6,182,212,0.4)] active:scale-95 flex items-center gap-1.5"
            :title="state.pipelineMode.value === 'fast_zh' ? '一键启动第 ' + state.chapterNum.value + ' 章 4 步极速生产' : '一键启动第 ' + state.chapterNum.value + ' 章 6 步出海生产'"
          >
            <span class="text-sm">⚡</span>
            <span>启动第 {{ state.chapterNum.value }} 章全自动生产</span>
          </button>

          <!-- 重新推演大纲/新书孵化入口（如果已有大纲，可随时重新展开） -->
          <button
            v-if="!isNewBookWithoutOutline"
            @click="showIncubatorManual = !showIncubatorManual"
            type="button"
            class="px-2.5 py-1.5 rounded-lg bg-stone-900 hover:bg-stone-800 border border-stone-700 text-amber-300 hover:text-amber-200 text-xs font-semibold transition-all cursor-pointer flex items-center gap-1 shadow-sm"
            title="展开/收起全书大纲与核心脑洞孵化面板"
          >
            <span>⚡</span>
            <span>{{ showIncubatorManual ? '收起大纲孵化' : '脑洞/大纲孵化' }}</span>
          </button>

          <!-- 跨章查阅其他章节 -->
          <button
            @click="state.openQuickReader(state.pipelineTargetChapter.value ? Math.max(1, state.pipelineTargetChapter.value - 1) : 1)"
            type="button"
            class="px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 border border-stone-600 text-amber-300 hover:text-amber-200 text-xs font-semibold transition-all cursor-pointer flex items-center gap-1.5 active:scale-95 shadow-md hover:border-amber-400"
            title="在流水线生产期间查阅其他章节的中英文内容（绝不影响后台编译）"
          >
            <span>📖</span>
            <span>查阅其他章</span>
          </button>

          <!-- 规则迭代白皮书与全书留底台账 -->
          <button
            @click="state.openWhitepaperModal()"
            type="button"
            class="px-3 py-1.5 rounded-lg bg-amber-950/80 hover:bg-amber-900 border border-amber-600/60 text-amber-300 text-xs font-semibold transition-all cursor-pointer flex items-center gap-1.5 active:scale-95 shadow-md"
            title="查看全书生成留底全景台账与审校记录白皮书"
          >
            <span>📘</span>
            <span>规则迭代白皮书</span>
          </button>

          <!-- 展开全屏控制舱大屏 -->
          <button
            @click="state.openPipelineControlRoom()"
            type="button"
            class="px-3 py-1.5 rounded-lg bg-[#141e2d] hover:bg-[#1a283d] border border-cyan-700/60 text-cyan-300 text-xs font-semibold transition-all cursor-pointer flex items-center gap-1.5 active:scale-95 shadow-md"
            title="打开专属全屏大屏监控舱"
          >
            <span>⛶</span>
            <span>大屏控制舱</span>
          </button>
        </div>
      </div>
    </div>

    <!-- ⚡ 新书零大纲极速孵化中枢 (当检测到当前项目尚未建立大纲时激活，或手动展开) -->
    <div
      v-if="isNewBookWithoutOutline || showIncubatorManual"
      class="p-5 bg-gradient-to-br from-amber-950/40 via-stone-900/95 to-[#0e1726] border-b-2 border-amber-500/50 space-y-4"
    >
      <div class="flex items-center justify-between flex-wrap gap-2">
        <div class="flex items-center gap-2.5">
          <span class="text-2xl">⚡</span>
          <div>
            <h4 class="text-sm sm:text-base font-bold text-amber-300 flex items-center gap-2">
              {{ state.pipelineMode.value === 'fast_zh' ? '🇨🇳 中文网文极速起航 · 零大纲一键推演中心' : '🌐 出海英文小说 · 零大纲一键推演中心' }}
              <span class="text-[11px] px-2 py-0.5 rounded-full bg-amber-900/80 text-amber-200 border border-amber-600/60 font-mono">
                雪花写作法全自动引擎
              </span>
            </h4>
            <p class="text-xs text-stone-400 mt-0.5">
              检测到当前《{{ state.projectStore.activeProjectData?.name || '新书' }}》尚未生成全书大纲与架构。只需输入核心脑洞，即可一键自动推演出完整骨架并解锁{{ state.pipelineMode.value === 'fast_zh' ? '纯中文' : '出海双语' }}流水线！
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button
            v-if="!isNewBookWithoutOutline"
            @click="showIncubatorManual = false"
            type="button"
            class="px-2.5 py-1 text-xs rounded bg-stone-800 text-stone-400 hover:text-stone-200 cursor-pointer"
          >
            收起
          </button>
        </div>
      </div>

      <!-- 核心输入：一句话脑洞/金手指与题材 -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div class="md:col-span-2 space-y-1.5">
          <label class="block text-xs font-semibold text-amber-200 flex items-center justify-between">
            <span>💡 故事核心脑洞 / 金手指主题 (Topic)</span>
            <span class="text-[11px] text-stone-400 font-normal">一句话描述主角、金手指与核心爽点</span>
          </label>
          <input
            v-model="state.topic.value"
            placeholder="例如：穿越高武世界，觉醒百倍暴击系统，别人苦修我靠吃席突破..."
            class="w-full bg-black/60 border border-amber-600/50 focus:border-amber-400 rounded-xl px-3.5 py-2 text-xs sm:text-sm text-stone-100 placeholder-stone-500 font-sans focus:outline-none transition-all shadow-inner"
          />
          <!-- 中文网文热梗预设 vs 出海英文题材预设 -->
          <div v-if="state.pipelineMode.value === 'fast_zh'" class="flex items-center gap-1.5 flex-wrap pt-1 text-[11px]">
            <span class="text-stone-400">🔥 中文热梗预设：</span>
            <button
              @click="pickPresetTopic('穿越修仙界，觉醒万倍返还系统，赠送道侣劣质灵石暴击返还极品灵脉', '仙侠')"
              type="button"
              class="px-2 py-0.5 rounded bg-stone-900 hover:bg-amber-950 border border-stone-700 hover:border-amber-500 text-stone-300 hover:text-amber-200 cursor-pointer transition-all"
            >
              🎁 万倍返还
            </button>
            <button
              @click="pickPresetTopic('穿越万族战场高武世界，觉醒饕餮吃席系统，吞噬凶兽肉直接暴击气血暴涨', '玄幻')"
              type="button"
              class="px-2 py-0.5 rounded bg-stone-900 hover:bg-amber-950 border border-stone-700 hover:border-amber-500 text-stone-300 hover:text-amber-200 cursor-pointer transition-all"
            >
              ⚔️ 吃席高武
            </button>
            <button
              @click="pickPresetTopic('觉醒因果伤害反弹系统，受到的致命攻击全额转化为突破修为什么也不用做就能无敌', '玄幻')"
              type="button"
              class="px-2 py-0.5 rounded bg-stone-900 hover:bg-amber-950 border border-stone-700 hover:border-amber-500 text-stone-300 hover:text-amber-200 cursor-pointer transition-all"
            >
              🛡️ 伤害反弹
            </button>
            <button
              @click="pickPresetTopic('长生不死苟道流，在落魄小宗门默默签到一千年，冷眼坐看万古帝皇起伏', '玄幻')"
              type="button"
              class="px-2 py-0.5 rounded bg-stone-900 hover:bg-amber-950 border border-stone-700 hover:border-amber-500 text-stone-300 hover:text-amber-200 cursor-pointer transition-all"
            >
              ⏳ 隐忍苟道
            </button>
          </div>
          <div v-else class="flex items-center gap-1.5 flex-wrap pt-1 text-[11px]">
            <span class="text-stone-400">🌐 出海爆款题材预设：</span>
            <button
              @click="state.topic.value = '被未婚夫与妹妹背叛逐出狼群的女医师，觉醒远古银月血脉后与帝国冷血狼皇缔结血契复仇'; state.genre.value = 'Paranormal Romance'"
              type="button"
              class="px-2 py-0.5 rounded bg-stone-900 hover:bg-cyan-950 border border-stone-700 hover:border-cyan-500 text-stone-300 hover:text-cyan-200 cursor-pointer transition-all"
            >
              🐺 Rejected Mate
            </button>
            <button
              @click="state.topic.value = '暗黑豪门契约婚姻，隐忍复仇女主利用冷峻掌权者反杀家族夺回遗产'; state.genre.value = 'Dark Romance'"
              type="button"
              class="px-2 py-0.5 rounded bg-stone-900 hover:bg-cyan-950 border border-stone-700 hover:border-cyan-500 text-stone-300 hover:text-cyan-200 cursor-pointer transition-all"
            >
              🖤 Billionaire / Dark Romance
            </button>
          </div>
        </div>

        <div class="space-y-1.5">
          <div class="flex items-center justify-between">
            <label class="block text-xs font-semibold text-stone-300">题材类型与目标篇幅</label>
            <span class="text-[11px] font-mono text-amber-300">
              预计总字数：{{ ((state.numChapters.value * state.wordNumber.value) / 10000).toFixed(1) }} 万字
            </span>
          </div>
          <div class="grid grid-cols-3 gap-2">
            <select
              v-model="state.genre.value"
              class="bg-black/60 border border-stone-700 rounded-xl px-2.5 py-2 text-xs text-stone-200 focus:outline-none"
            >
              <option value="玄幻">玄幻</option>
              <option value="都市脑洞">都市脑洞</option>
              <option value="仙侠">仙侠</option>
              <option value="科幻末世">科幻末世</option>
              <option value="悬疑惊悚">悬疑惊悚</option>
              <option value="历史脑洞">历史脑洞</option>
            </select>
            <div class="flex items-center gap-1 bg-black/60 border border-stone-700 rounded-xl px-2 py-1 text-xs">
              <span class="text-stone-400 shrink-0">章数:</span>
              <input
                v-model.number="state.numChapters.value"
                type="number"
                min="10"
                max="2000"
                step="10"
                class="w-full bg-transparent text-amber-300 font-bold font-mono focus:outline-none text-center"
              />
            </div>
            <div class="flex items-center justify-between bg-black/60 border border-stone-700 rounded-xl px-2 py-1 text-xs">
              <button
                @click="state.wordNumber.value = 2000"
                :class="state.wordNumber.value === 2000 ? 'text-amber-300 font-bold' : 'text-stone-500'"
                type="button"
              >2k</button>
              <span class="text-stone-600">/</span>
              <button
                @click="state.wordNumber.value = 2500"
                :class="state.wordNumber.value === 2500 ? 'text-amber-300 font-bold' : 'text-stone-500'"
                type="button"
              >2.5k</button>
              <span class="text-stone-600">/</span>
              <button
                @click="state.wordNumber.value = 3000"
                :class="state.wordNumber.value === 3000 ? 'text-amber-300 font-bold' : 'text-stone-500'"
                type="button"
              >3k</button>
            </div>
          </div>
          <!-- 快捷长篇目标字数预设 -->
          <div class="flex items-center gap-1.5 flex-wrap pt-1 text-[11px]">
            <span class="text-stone-400">📏 目标篇幅：</span>
            <button
              @click="state.numChapters.value = 120; state.wordNumber.value = 2500"
              type="button"
              :class="state.numChapters.value === 120 ? 'border-amber-400 text-amber-300 bg-amber-950/60' : 'border-stone-700 text-stone-300 bg-stone-900'"
              class="px-2 py-0.5 rounded border hover:border-amber-500 cursor-pointer transition-all"
            >
              30万字 (120章)
            </button>
            <button
              @click="state.numChapters.value = 200; state.wordNumber.value = 2500"
              type="button"
              :class="state.numChapters.value === 200 ? 'border-amber-400 text-amber-300 bg-amber-950/60 font-bold' : 'border-stone-700 text-stone-300 bg-stone-900'"
              class="px-2 py-0.5 rounded border hover:border-amber-500 cursor-pointer transition-all"
            >
              50万字 (200章·推荐)
            </button>
            <button
              @click="state.numChapters.value = 340; state.wordNumber.value = 3000"
              type="button"
              :class="state.numChapters.value === 340 ? 'border-amber-400 text-amber-300 bg-amber-950/60' : 'border-stone-700 text-stone-300 bg-stone-900'"
              class="px-2 py-0.5 rounded border hover:border-amber-500 cursor-pointer transition-all"
            >
              102万字 (340章)
            </button>
          </div>
        </div>
      </div>

      <!-- 番茄爆款法则 -->
      <div class="space-y-1">
        <div class="flex items-center justify-between text-xs">
          <label class="font-semibold text-stone-300 flex items-center gap-1.5">
            <span>📜 番茄创作指导与核心法则 (User Guidance)</span>
          </label>
          <button
            @click="fillTomatoGuidance()"
            type="button"
            class="text-[11px] text-amber-400 hover:text-amber-300 flex items-center gap-1 cursor-pointer"
          >
            <span>✨ 一键装填番茄爆款法则 (黄金三章/爽点/断章钩子)</span>
          </button>
        </div>
        <textarea
          v-model="state.userGuidance.value"
          rows="2"
          class="w-full bg-black/40 border border-stone-700 focus:border-amber-500 rounded-xl p-2.5 text-xs text-stone-200 font-mono placeholder-stone-500 leading-relaxed focus:outline-none"
          placeholder="可在此写入黄金三章规则、系统设定口径、禁词与文风要求..."
        ></textarea>
      </div>

      <!-- 孵化触发按钮与实时进度 -->
      <div class="flex items-center justify-between flex-wrap gap-3 pt-1">
        <div class="text-xs text-stone-400 flex items-center gap-2">
          <span v-if="state.fastIncubating.value" class="text-amber-300 font-bold animate-pulse flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping"></span>
            <span>{{ state.fastIncubateProgress.value }}</span>
          </span>
          <span v-else class="text-stone-400">
            准备完毕后点击右侧按钮，AI 将分块自动生成 5 项雪花架构与 {{ state.numChapters.value }} 章大纲蓝图（目标 {{ ((state.numChapters.value * state.wordNumber.value) / 10000).toFixed(1) }} 万字）。
          </span>
        </div>

        <button
          @click="handleFastIncubate()"
          :disabled="state.fastIncubating.value"
          type="button"
          class="px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-600 via-orange-600 to-amber-700 hover:from-amber-500 hover:to-orange-500 text-white font-bold text-xs sm:text-sm shadow-[0_0_20px_rgba(245,158,11,0.4)] disabled:opacity-40 disabled:cursor-not-allowed transition-all active:scale-95 flex items-center gap-2 cursor-pointer"
        >
          <span>🚀</span>
          <span>{{ state.fastIncubating.value ? '全自动推演中...' : '一键全自动孵化大纲与蓝图' }}</span>
        </button>
      </div>
    </div>

    <!-- 6 阶段可视化动态流程拓扑链与进度条 (Interactive Stage Pipeline Flow) -->
    <div class="px-5 py-4 bg-[#0a0f19] border-b border-stone-800/80">
      <div class="flex items-center justify-between text-xs text-stone-400 mb-3 flex-wrap gap-2">
        <span class="font-semibold text-stone-300 flex items-center gap-2">
          <span>🔗</span>
          <span>工艺流程拓扑图（实时量化进度与质检，点击节点查看对应产物）</span>
        </span>
        <div class="flex items-center gap-3">
          <span class="text-[11px] font-mono text-cyan-300 bg-cyan-950/80 px-2 py-0.5 rounded border border-cyan-800/50">
            {{ state.pipelineStatusMsg.value || '系统就绪' }}
          </span>
          <span class="text-xs font-mono font-bold text-amber-300">
            总进度: {{ overallPercentage }}%
          </span>
        </div>
      </div>

      <!-- 流程拓扑卡片链条 (自适应 4 步 vs 6 步) -->
      <div :class="['grid grid-cols-2 md:grid-cols-3 gap-3 relative', state.pipelineMode.value === 'fast_zh' ? 'lg:grid-cols-4' : 'lg:grid-cols-6']">
        <div
          v-for="(stage, idx) in state.pipelineStages.value"
          :key="stage.id"
          @click="handleNodeClick(stage.id)"
          :class="[
            'p-3.5 rounded-xl border transition-all cursor-pointer select-none flex flex-col justify-between relative group overflow-hidden',
            stage.status === 'running'
              ? 'bg-cyan-950/70 border-cyan-400 glow-active-node shadow-[0_0_20px_rgba(6,182,212,0.35)]'
              : stage.status === 'retrying'
              ? 'bg-amber-950/70 border-amber-400 shadow-[0_0_15px_rgba(245,158,11,0.3)] ring-1 ring-amber-400'
              : stage.status === 'completed'
              ? 'bg-emerald-950/30 border-emerald-500/70 hover:border-emerald-400 hover:bg-emerald-950/45'
              : stage.status === 'error'
              ? 'bg-red-950/40 border-red-500/80'
              : 'bg-[#101724]/75 border-stone-800/90 hover:border-stone-700 opacity-80'
          ]"
        >
          <!-- 节点顶部：图标、声波均衡器与量化百分比 -->
          <div class="flex items-center justify-between gap-1.5 mb-2">
            <!-- 图标与雷达环 -->
            <div class="relative w-8 h-8 rounded-lg bg-stone-900/80 border border-stone-800 flex items-center justify-center flex-shrink-0">
              <div
                v-if="stage.status === 'running'"
                class="absolute inset-0 rounded-lg border-2 border-cyan-400 border-t-transparent animate-radar shadow-[0_0_10px_rgba(6,182,212,0.6)]"
              ></div>
              <span class="text-lg relative z-10">{{ stage.icon }}</span>
            </div>

            <!-- 声波均衡器动画 (仅在 active running 时显示) -->
            <div v-if="stage.status === 'running'" class="flex items-end gap-0.5 h-3.5 px-1 py-0.5 rounded bg-cyan-950/90 border border-cyan-500/50" title="AI 推理流中">
              <span class="w-0.5 bg-cyan-400 rounded-sm animate-eq-1"></span>
              <span class="w-0.5 bg-cyan-400 rounded-sm animate-eq-2"></span>
              <span class="w-0.5 bg-cyan-300 rounded-sm animate-eq-3"></span>
              <span class="w-0.5 bg-cyan-200 rounded-sm animate-eq-4"></span>
            </div>

            <!-- 量化百分比微标 -->
            <span
              :class="[
                'text-[11px] font-mono font-bold px-2 py-0.5 rounded-full border transition-all',
                stage.status === 'running' ? 'bg-cyan-900 text-cyan-200 border-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.5)] animate-pulse' :
                stage.status === 'retrying' ? 'bg-amber-900 text-amber-200 border-amber-400' :
                stage.status === 'completed' ? 'bg-emerald-950 text-emerald-300 border-emerald-500/70' :
                stage.status === 'error' ? 'bg-red-950 text-red-300 border-red-500' :
                'text-stone-500 bg-stone-900/90 border-stone-800'
              ]"
            >
              {{
                stage.status === 'completed' ? '✓ 100%' :
                stage.status === 'running' ? `${Math.round(stage.progress || 0)}%` :
                stage.status === 'retrying' ? `⚠️ ${Math.round(stage.progress || 0)}%` :
                stage.status === 'error' ? '✕ 异常' : '0%'
              }}
            </span>
          </div>

          <!-- 节点名称与副标题 -->
          <div>
            <h4 class="text-xs font-bold text-stone-200 truncate group-hover:text-cyan-300 transition-colors">
              {{ stage.name }}
            </h4>
            <p class="text-[11px] text-stone-400 mt-0.5 line-clamp-1 leading-snug">
              {{ stage.subtitle }}
            </p>
            <!-- 契约与正史直达微标 -->
            <div v-if="stage.id === 1" class="mt-1.5 flex items-center gap-1 text-[10px] font-mono">
              <span class="px-1.5 py-0.5 rounded bg-sky-950/90 border border-sky-600/60 font-semibold text-sky-300 flex items-center gap-1">
                <span>🔗</span><span>交接契约(Handoff)</span>
              </span>
            </div>
            <div v-if="(state.pipelineMode.value === 'fast_zh' ? stage.id === 4 : stage.id === 6)" class="mt-1.5 flex items-center gap-1 text-[10px] font-mono">
              <span class="px-1.5 py-0.5 rounded bg-purple-950/90 border border-purple-600/60 font-semibold text-purple-200 flex items-center gap-1">
                <span>📜</span><span>正史演进与归档</span>
              </span>
            </div>
          </div>

          <!-- 阶段独立微型进度条 (动态进度展示) -->
          <div class="w-full bg-stone-900/90 rounded-full h-1.5 mt-2.5 overflow-hidden border border-stone-800/80">
            <div
              class="h-full transition-all duration-300 rounded-full"
              :class="[
                stage.status === 'completed' ? 'bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.7)]' :
                stage.status === 'running' ? 'bg-gradient-to-r from-cyan-400 via-indigo-400 to-cyan-300 conduit-laser-active shadow-[0_0_10px_rgba(6,182,212,0.8)]' :
                stage.status === 'retrying' ? 'bg-amber-400' :
                stage.status === 'error' ? 'bg-red-500' :
                'bg-stone-800'
              ]"
              :style="{ width: `${stage.progress || 0}%` }"
            ></div>
          </div>

          <!-- 节点产物指标微标 -->
          <div class="mt-2 text-[10px] flex items-center justify-between text-stone-400">
            <span v-if="stage.id === 2 && draftWordCount > 0" class="text-cyan-300 font-mono font-semibold">
              {{ draftWordCount }} 字初稿
            </span>
            <span v-else-if="stage.id === 3 && polishedWordCount > 0" class="text-emerald-300 font-mono font-semibold">
              {{ polishedWordCount }} 字润色
            </span>
            <span v-else-if="state.pipelineMode.value === 'fast_zh' && stage.id === 4 && (displaySummary || state.pipelineData.value.summary)" class="text-cyan-300 font-mono">
              ✓ 记忆与正史已同步
            </span>
            <span v-else-if="stage.id === 4 && englishWordCount > 0" class="text-indigo-300 font-mono font-semibold">
              {{ englishWordCount }} 词英译
            </span>
            <span v-else-if="stage.id === 5 && (displayAudit || state.pipelineData.value.auditPass)" :class="state.pipelineData.value.auditPass ? 'text-emerald-400 font-bold' : 'text-amber-400'">
              {{ state.pipelineData.value.auditPass ? '🛡️ 质检与哨兵合格' : '⚠️ 质检提示' }}
            </span>
            <span v-else-if="stage.id === 6 && (displaySummary || state.pipelineData.value.summary)" class="text-cyan-300 font-mono">
              ✓ 记忆已同步
            </span>
            <span v-else class="text-stone-500 font-mono">
              阶段 0{{ stage.id }}
            </span>

            <span
              :class="[
                'flex items-center gap-1 font-semibold transition-all px-2 py-0.5 rounded text-[11px]',
                stage.id === 4 && state.pipelineMode.value === 'bilingual'
                  ? 'text-indigo-200 bg-indigo-950/90 border border-indigo-500/70 opacity-100 shadow-[0_0_8px_rgba(99,102,241,0.4)]'
                  : 'text-cyan-400 opacity-0 group-hover:opacity-100'
              ]"
            >
              <span>{{ stage.id === 4 && state.pipelineMode.value === 'bilingual' ? '📖 查看译文' : '查看' }}</span>
              <span>➔</span>
            </span>
          </div>

          <!-- 右向流程导管箭头指示器 (桌面端展示) -->
          <div
            v-if="idx < state.pipelineStages.value.length - 1"
            class="hidden lg:flex absolute -right-3 top-1/2 -translate-y-1/2 z-20 w-5 h-5 rounded-full bg-[#0a0f19] border border-stone-800 items-center justify-center pointer-events-none shadow-md"
          >
            <span
              :class="[
                'text-[10px] font-bold transition-all',
                stage.status === 'completed' ? 'text-emerald-400 drop-shadow-[0_0_5px_rgba(16,185,129,0.8)]' :
                stage.status === 'running' ? 'text-cyan-300 animate-pulse drop-shadow-[0_0_6px_rgba(6,182,212,0.9)]' :
                'text-stone-600'
              ]"
            >
              ➔
            </span>
          </div>
        </div>
      </div>

      <!-- 全局大进度光带 (带平滑光流粒子动画) -->
      <div class="mt-4 relative">
        <div class="w-full bg-stone-900 rounded-full h-2 overflow-hidden border border-stone-800 shadow-inner">
          <div
            class="h-full bg-gradient-to-r from-cyan-500 via-indigo-500 to-emerald-400 transition-all duration-300 rounded-full conduit-laser-active shadow-[0_0_12px_rgba(6,182,212,0.5)]"
            :style="{ width: `${overallPercentage}%` }"
          ></div>
        </div>
      </div>
    </div>

    <!-- 🎬 章节导演指令舱 (流水线生产前置输入与控制台) -->
    <div class="px-5 py-3.5 bg-gradient-to-r from-[#0d1624] via-[#101b2c] to-[#0d1624] border-b border-cyan-900/50 space-y-3">
      <div class="flex items-center justify-between flex-wrap gap-2.5">
        <div class="flex items-center gap-2.5">
          <div class="w-7 h-7 rounded-lg bg-cyan-950 border border-cyan-500/50 flex items-center justify-center text-sm shadow-[0_0_10px_rgba(6,182,212,0.3)]">
            🎬
          </div>
          <div>
            <div class="flex items-center gap-2">
              <span class="font-bold text-xs sm:text-sm text-cyan-200">章节导演指令舱 · 前置输入台</span>
              <span class="text-[10px] px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-300 border border-cyan-700 font-mono">
                第 {{ state.chapterNum.value }} 章
              </span>
            </div>
            <span class="text-[11px] text-stone-400">
              在此直接设定当前章的核心剧情、金手指展现与爽点反转（流水线将严格遵照指令起草与审校）
            </span>
          </div>
        </div>

        <div class="flex items-center gap-2 flex-wrap">
          <!-- 切换章节 -->
          <div class="flex items-center bg-black/60 border border-stone-800 rounded-lg p-0.5 text-xs">
            <button
              @click="state.prevChapter()"
              :disabled="state.chapterNum.value <= 1 || state.pipelineRunning.value"
              class="px-2 py-1 rounded text-stone-300 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              type="button"
              title="切换至上一章"
            >
              ◀
            </button>
            <span class="px-2 font-mono font-bold text-amber-300">第 {{ state.chapterNum.value }} 章</span>
            <button
              @click="state.nextChapter()"
              :disabled="state.chapterNum.value >= state.numChapters.value || state.pipelineRunning.value"
              class="px-2 py-1 rounded text-stone-300 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              type="button"
              title="切换至下一章"
            >
              ▶
            </button>
          </div>

          <!-- 自动同步参数 -->
          <button
            @click="state.autoFillChapterParams(state.chapterNum.value, true)"
            :disabled="state.pipelineRunning.value"
            type="button"
            class="px-2.5 py-1 rounded-lg bg-cyan-950 hover:bg-cyan-900 border border-cyan-700/70 text-cyan-300 text-xs font-medium flex items-center gap-1 transition-all cursor-pointer shadow-sm"
            title="从已有大纲和细纲中重新提取本章剧情与角色"
          >
            <span>✨</span>
            <span>从大纲同步</span>
          </button>

          <!-- 清空 -->
          <button
            @click="state.chGuidance.value = ''"
            :disabled="state.pipelineRunning.value"
            type="button"
            class="px-2 py-1 rounded-lg bg-stone-900 hover:bg-stone-800 border border-stone-700 text-stone-400 hover:text-stone-200 text-xs cursor-pointer transition-all"
            title="清空本章指令输入"
          >
            🧹 清空
          </button>
        </div>
      </div>

      <!-- 核心多行输入框 -->
      <div class="space-y-1.5">
        <textarea
          v-model="state.chGuidance.value"
          :disabled="state.pipelineRunning.value"
          rows="2"
          class="w-full bg-black/60 border border-cyan-900/80 focus:border-cyan-400 rounded-xl p-3 text-xs sm:text-sm text-stone-100 placeholder-stone-500 font-sans leading-relaxed focus:outline-none transition-all shadow-inner"
          placeholder="💡 在此输入本章导演指令（例如：开局主角被退婚，金手指百倍暴击觉醒，当场反杀挑衅的管家，章末留家主即将出关的致命悬念）... 留空则完全按照细纲自动推演。"
        ></textarea>

        <!-- 快捷导演芯片（按纯中文 / 出海双语隔离） -->
        <div class="flex items-center gap-1.5 flex-wrap text-xs text-stone-400">
          <template v-if="state.pipelineMode.value === 'fast_zh'">
            <span class="text-[11px] text-amber-400 font-semibold flex items-center gap-1">🇨🇳 中文爽点芯片：</span>
            <button
              @click="appendGuidance('【黄金开局·受辱觉醒】开篇展现主角绝境压迫，生死关头金手指觉醒，反差震撼！')"
              type="button"
              class="px-2 py-0.5 rounded bg-stone-900 border border-stone-700 hover:border-amber-500 hover:text-amber-300 text-[11px] transition-all cursor-pointer"
            >
              ⚡ 受辱觉醒
            </button>
            <button
              @click="appendGuidance('【当面反杀·打脸爽点】反派极度嚣张挑衅，主角雷霆出手干脆秒杀，路人震惊目瞪口呆！')"
              type="button"
              class="px-2 py-0.5 rounded bg-stone-900 border border-stone-700 hover:border-amber-500 hover:text-amber-300 text-[11px] transition-all cursor-pointer"
            >
              💥 当面反杀
            </button>
            <button
              @click="appendGuidance('【暴击结算·超额收获】战斗或事件结束，系统结算超额万倍奖励，实力暴涨！')"
              type="button"
              class="px-2 py-0.5 rounded bg-stone-900 border border-stone-700 hover:border-amber-500 hover:text-amber-300 text-[11px] transition-all cursor-pointer"
            >
              🎁 暴击结算
            </button>
            <button
              @click="appendGuidance('【绝命断章·极限卡点】章末在危机爆发或巨大利益揭晓的最顶峰处掐断，留下抓心钩子！')"
              type="button"
              class="px-2 py-0.5 rounded bg-stone-900 border border-stone-700 hover:border-amber-500 hover:text-amber-300 text-[11px] transition-all cursor-pointer"
            >
              🪝 绝命卡点
            </button>
          </template>
          <template v-else>
            <span class="text-[11px] text-cyan-400 font-semibold flex items-center gap-1">🌐 出海张力芯片：</span>
            <button
              @click="appendGuidance('【Public Humiliation & Counter】公开羞辱后用精准证据或冷硬台词反击，强化张力。')"
              type="button"
              class="px-2 py-0.5 rounded bg-stone-900 border border-stone-700 hover:border-cyan-500 hover:text-cyan-300 text-[11px] transition-all cursor-pointer"
            >
              ⚔️ 反击打脸
            </button>
            <button
              @click="appendGuidance('【Cliffhanger Hook】章末卡在致命反转或新身份揭晓的瞬间，留强烈悬念。')"
              type="button"
              class="px-2 py-0.5 rounded bg-stone-900 border border-stone-700 hover:border-cyan-500 hover:text-cyan-300 text-[11px] transition-all cursor-pointer"
            >
              🪝 悬念断章
            </button>
          </template>

          <button
            @click="showAdvancedParams = !showAdvancedParams"
            type="button"
            class="ml-auto text-cyan-400 hover:text-cyan-300 text-[11px] flex items-center gap-1 cursor-pointer font-medium"
          >
            <span>{{ showAdvancedParams ? '▲ 折叠高阶参数' : '▼ 展开高阶参数 (角色/道具/场景/字数)' }}</span>
          </button>
        </div>

        <!-- 高阶参数面板（可折叠） -->
        <div v-show="showAdvancedParams" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 pt-2 border-t border-stone-800/80">
          <div>
            <label class="block text-[11px] text-stone-400 mb-1">登场角色</label>
            <input
              v-model="state.charactersInvolved.value"
              :disabled="state.pipelineRunning.value"
              placeholder="如：林枫、林管家、苏清歌"
              class="w-full bg-black/40 border border-stone-700 focus:border-cyan-500 rounded px-2.5 py-1.5 text-xs text-stone-200 focus:outline-none"
            />
          </div>
          <div>
            <label class="block text-[11px] text-stone-400 mb-1">关键道具/金手指</label>
            <input
              v-model="state.keyItems.value"
              :disabled="state.pipelineRunning.value"
              placeholder="如：暴击系统面板、退婚契约"
              class="w-full bg-black/40 border border-stone-700 focus:border-cyan-500 rounded px-2.5 py-1.5 text-xs text-stone-200 focus:outline-none"
            />
          </div>
          <div>
            <label class="block text-[11px] text-stone-400 mb-1">场景地点</label>
            <input
              v-model="state.sceneLocation.value"
              :disabled="state.pipelineRunning.value"
              placeholder="如：林家正厅 ➔ 演武场"
              class="w-full bg-black/40 border border-stone-700 focus:border-cyan-500 rounded px-2.5 py-1.5 text-xs text-stone-200 focus:outline-none"
            />
          </div>
          <div>
            <label class="block text-[11px] text-stone-400 mb-1">单章字数期望</label>
            <div class="flex items-center gap-1">
              <button
                @click="state.wordNumber.value = 2000"
                :class="state.wordNumber.value === 2000 ? 'bg-amber-600 text-white font-bold' : 'bg-stone-900 text-stone-400 hover:text-stone-200'"
                type="button"
                class="flex-1 py-1 text-xs rounded border border-stone-700 cursor-pointer transition-all"
              >
                2000字
              </button>
              <button
                @click="state.wordNumber.value = 2500"
                :class="state.wordNumber.value === 2500 ? 'bg-amber-600 text-white font-bold' : 'bg-stone-900 text-stone-400 hover:text-stone-200'"
                type="button"
                class="flex-1 py-1 text-xs rounded border border-stone-700 cursor-pointer transition-all"
              >
                2500字
              </button>
              <button
                @click="state.wordNumber.value = 3000"
                :class="state.wordNumber.value === 3000 ? 'bg-amber-600 text-white font-bold' : 'bg-stone-900 text-stone-400 hover:text-stone-200'"
                type="button"
                class="flex-1 py-1 text-xs rounded border border-stone-700 cursor-pointer transition-all"
              >
                3000字
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 产物实时监视器与快速抽屉 (可折叠) -->
    <div v-show="isExpanded" class="p-4 bg-[#080d15]">
      <!-- 监视器 Tab 栏与合格印章 -->
      <div class="flex items-center justify-between border-b border-stone-800 pb-2.5 mb-3 flex-wrap gap-2 text-xs">
        <div class="flex items-center gap-1.5 overflow-x-auto">
          <button
            @click="activeTab = 'terminal'"
            :class="[
              'px-3 py-1.5 rounded-lg font-medium transition-colors cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
              activeTab === 'terminal' ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/80 shadow-[0_0_10px_rgba(6,182,212,0.2)]' : 'text-stone-400 hover:text-stone-200 hover:bg-stone-900'
            ]"
          >
            <span>🖥️</span>
            <span>实时日志</span>
          </button>
          <button
            @click="activeTab = 'continuity'"
            :class="[
              'px-3 py-1.5 rounded-lg font-bold transition-all cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
              activeTab === 'continuity' ? 'bg-sky-950 text-sky-300 border border-sky-500 shadow-[0_0_12px_rgba(14,165,233,0.35)]' : 'text-sky-400 hover:text-sky-200 hover:bg-sky-950/40 border border-sky-900/60'
            ]"
          >
            <span>🔗</span>
            <span>正史因果交接 (Handoff)</span>
            <span class="px-1.5 py-0.2 rounded text-[10px] bg-sky-900/90 text-sky-200 font-mono border border-sky-600/60">连贯核心</span>
            <span v-if="displayCanon || props.state.handoffData.value" class="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
          </button>
          <button
            @click="activeTab = 'draft'"
            :class="[
              'px-3 py-1.5 rounded-lg font-medium transition-colors cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
              activeTab === 'draft' ? 'bg-amber-950/80 text-amber-300 border border-amber-800/80 shadow-[0_0_10px_rgba(245,158,11,0.2)]' : 'text-stone-500 hover:text-stone-300 hover:bg-stone-900'
            ]"
          >
            <span>📝</span>
            <span>初始生稿 (未去AI味)</span>
            <span v-if="draftWordCount > 0" class="font-mono text-amber-400">({{ draftWordCount }})</span>
          </button>
          <button
            @click="activeTab = 'polish'"
            :class="[
              'px-3.5 py-1.5 rounded-lg font-bold transition-colors cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
              activeTab === 'polish' ? 'bg-emerald-950 text-emerald-300 border border-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.3)]' : 'text-emerald-400 hover:text-emerald-200 hover:bg-emerald-950/50 border border-emerald-900/40'
            ]"
          >
            <span>🛡️</span>
            <span>正式定稿 (已去AI味·最终正文)</span>
            <span v-if="polishedWordCount > 0" class="font-mono text-emerald-300">({{ polishedWordCount }})</span>
          </button>
          <button
            v-if="state.pipelineMode.value === 'bilingual'"
            @click="activeTab = 'translation'"
            :class="[
              'px-3 py-1.5 rounded-lg font-medium transition-colors cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
              activeTab === 'translation' ? 'bg-indigo-950 text-indigo-300 border border-indigo-800/80 shadow-[0_0_10px_rgba(99,102,241,0.2)]' : 'text-stone-400 hover:text-stone-200 hover:bg-stone-900'
            ]"
          >
            <span>🇺🇸</span>
            <span>美式英文译稿</span>
            <span v-if="englishWordCount > 0" class="font-mono text-indigo-300">({{ englishWordCount }}w)</span>
          </button>
          <button
            v-if="state.pipelineMode.value === 'bilingual'"
            @click="activeTab = 'audit'"
            :class="[
              'px-3 py-1.5 rounded-lg font-medium transition-colors cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
              activeTab === 'audit' ? 'bg-amber-950 text-amber-300 border border-amber-800/80 shadow-[0_0_10px_rgba(245,158,11,0.2)]' : 'text-stone-400 hover:text-stone-200 hover:bg-stone-900'
            ]"
          >
            <span>🛡️</span>
            <span>双语质检审校</span>
          </button>
          <button
            @click="activeTab = 'archive'"
            :class="[
              'px-3 py-1.5 rounded-lg font-medium transition-colors cursor-pointer flex items-center gap-1.5',
              activeTab === 'archive' ? 'bg-stone-800 text-stone-200 border border-stone-700' : 'text-stone-400 hover:text-stone-200 hover:bg-stone-900'
            ]"
          >
            <span>📦</span>
            <span>记忆归档</span>
          </button>
        </div>

        <!-- 质检合格全息徽章与操作 -->
        <div class="flex items-center gap-2.5">
          <div
            v-if="state.pipelineData.value.auditPass || englishWordCount > 0"
            class="px-2.5 py-1 rounded-md bg-emerald-950/80 border border-emerald-400/80 text-emerald-300 text-xs font-bold flex items-center gap-1.5 shadow-[0_0_10px_rgba(16,185,129,0.3)] animate-stamp"
          >
            <span>🛡️</span>
            <span>质检严格合格</span>
            <span v-if="state.pipelineData.value.retryOccurred" class="text-[10px] text-amber-300 font-mono">(已自纠1次)</span>
          </div>

          <span v-if="copyToast" class="text-emerald-400 font-semibold text-xs animate-pulse">
            {{ copyToast }}
          </span>
          <button
            v-if="displayPolished"
            @click="copyText(displayPolished, '正式定稿正文')"
            class="px-3 py-1 rounded-lg bg-emerald-900 hover:bg-emerald-800 border border-emerald-500 text-emerald-100 text-xs font-bold cursor-pointer transition-colors flex items-center gap-1 shadow-[0_0_10px_rgba(16,185,129,0.3)]"
          >
            <span>📋</span>
            <span>一键复制正式定稿(已去AI味)</span>
          </button>
          <button
            @click="state.openPipelineControlRoom()"
            class="px-3 py-1 rounded-lg bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-700/60 text-cyan-300 text-xs font-semibold cursor-pointer transition-colors flex items-center gap-1"
          >
            <span>⛶</span>
            <span>大屏展开</span>
          </button>
        </div>
      </div>

      <!-- 视口内容展示 -->
      <div class="max-h-72 overflow-y-auto rounded-xl bg-black/70 p-4 border border-stone-800/90 font-mono text-xs text-stone-300 shadow-inner">
        <!-- 终端日志 -->
        <div v-show="activeTab === 'terminal'" class="space-y-1.5">
          <div v-if="state.pipelineTerminalLogs.value.length === 0" class="text-stone-500 italic">
            尚未启动全链路生产，点击上方「⚡ 启动全链路生产」开始单章全自动生产运作。
          </div>
          <div
            v-for="(log, i) in state.pipelineTerminalLogs.value"
            :key="i"
            :class="[
              log.includes('✅') || log.includes('通过') || log.includes('圆满完成') ? 'text-emerald-400 font-medium' :
              log.includes('❌') ? 'text-red-400 font-bold' :
              log.includes('⚠️') ? 'text-amber-400' :
              log.includes('🚀') ? 'text-cyan-300 font-semibold' : 'text-stone-300'
            ]"
          >
            {{ log }}
          </div>
        </div>

        <!-- 中文草稿 -->
        <div v-show="activeTab === 'draft'" class="whitespace-pre-wrap font-serif text-xs leading-relaxed text-stone-200">
          <div class="p-2.5 bg-amber-950/60 border border-amber-800/80 rounded-lg text-amber-300 text-xs mb-3 flex items-center justify-between">
            <span class="flex items-center gap-1.5">
              <span>⚠️</span>
              <strong>【重要提示】：当前展示的是 3.8 Flash 原始生稿（未经 4 Hydrogen 审校润色，仅供内部对照）。请勿直接发布此生稿！</strong>
            </span>
            <button @click="activeTab = 'polish'" class="px-2 py-0.5 rounded bg-emerald-900 hover:bg-emerald-800 text-emerald-200 text-xs font-semibold cursor-pointer border border-emerald-700">
              ➔ 切换至【正式定稿】
            </button>
          </div>
          <div class="flex justify-end mb-2">
            <button @click="copyText(displayDraft, '未审校草稿')" class="px-2.5 py-1 rounded bg-stone-800 hover:bg-stone-700 text-[11px] cursor-pointer text-stone-400 border border-stone-700">
              📋 复制草稿(仅供对比)
            </button>
          </div>
          <div v-if="!displayDraft" class="text-stone-500 italic">草稿内容待生成...</div>
          <template v-else>{{ displayDraft }}</template>
        </div>

        <!-- 润色与修改清单 -->
        <div v-show="activeTab === 'polish'" class="space-y-3 font-serif text-xs leading-relaxed">
          <div class="flex justify-end gap-2 mb-2 font-mono">
            <button @click="copyText(displayPolished, '润色正文')" class="px-2.5 py-1 rounded bg-stone-800 hover:bg-stone-700 text-[11px] cursor-pointer text-stone-300 border border-stone-700">
              📋 复制润色正文
            </button>
            <button v-if="displayChecklist" @click="copyText(displayChecklist, '修改清单')" class="px-2.5 py-1 rounded bg-stone-800 hover:bg-stone-700 text-[11px] cursor-pointer text-stone-300 border border-stone-700">
              📋 复制修改清单
            </button>
          </div>
          <div v-if="!displayPolished" class="text-stone-500 italic font-mono">润色产物待生成...</div>
          <template v-else>
            <div class="p-3.5 bg-stone-900/70 rounded-xl border border-stone-800">
              <h5 class="text-cyan-300 font-bold mb-1.5 font-sans flex items-center gap-1.5">
                <span>🎯</span>
                <span>【4 Hydrogen 审校定稿正文】</span>
              </h5>
              <div class="whitespace-pre-wrap text-stone-200 font-serif leading-relaxed">{{ displayPolished }}</div>
            </div>
            <div v-if="displayChecklist" class="p-3.5 bg-emerald-950/30 rounded-xl border border-emerald-900/50 text-emerald-300 font-mono">
              <h5 class="font-bold mb-1.5 font-sans text-emerald-200 flex items-center gap-1.5">
                <span>📋</span>
                <span>【修改清单明细】</span>
              </h5>
              <div class="whitespace-pre-wrap">{{ displayChecklist }}</div>
            </div>
          </template>
        </div>

        <!-- 美式英文 -->
        <div v-show="activeTab === 'translation'" class="whitespace-pre-wrap font-sans text-xs leading-relaxed text-stone-200">
          <div class="flex justify-end mb-2">
            <button @click="copyText(displayTranslation, '美式英文')" class="px-2.5 py-1 rounded bg-indigo-900 hover:bg-indigo-800 text-[11px] text-indigo-200 cursor-pointer border border-indigo-700 font-mono">
              📋 复制英文译文
            </button>
          </div>
          <div v-if="!displayTranslation" class="text-stone-500 italic font-mono flex items-center justify-between">
            <span>美式英文译稿待生成...</span>
            <button
              @click="state.loadChapterEn(state.chapterNum.value)"
              class="px-2.5 py-1 rounded bg-stone-800 hover:bg-stone-700 text-stone-300 text-[11px] cursor-pointer border border-stone-700"
            >
              🔄 重新从磁盘读取
            </button>
          </div>
          <template v-else>{{ displayTranslation }}</template>
        </div>

        <!-- 独立双语质检审校 -->
        <div v-show="activeTab === 'audit'" class="whitespace-pre-wrap font-mono text-xs leading-relaxed text-amber-200/90">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-amber-300/90 font-bold flex items-center gap-1.5">
              <span>🛡️</span><span>双语语义对照质检报告 (Gemini 4 Hydrogen Medium)</span>
            </span>
            <button @click="copyText(displayAudit, '双语质检报告')" class="px-2.5 py-1 rounded bg-stone-800 hover:bg-stone-700 text-[11px] cursor-pointer text-stone-300 border border-stone-700">
              📋 复制质检报告
            </button>
          </div>
          <div v-if="!displayAudit" class="text-stone-500 italic">独立双语质检审查报告待生成...</div>
          <template v-else>{{ displayAudit }}</template>
        </div>

        <!-- 正史与因果交接 -->
        <div v-show="activeTab === 'continuity'" class="space-y-3 font-sans text-xs">
          <!-- 快捷操作工具条 -->
          <div class="flex items-center justify-between p-2.5 bg-sky-950/30 border border-sky-800/40 rounded-xl flex-wrap gap-2">
            <div class="flex items-center gap-2">
              <span class="text-sky-300 font-bold flex items-center gap-1">
                <span>🔗</span><span>因果交接与正史控制中心</span>
              </span>
              <span class="text-[11px] text-stone-400 font-mono">(NovelGenerator 引擎)</span>
            </div>
            <div class="flex items-center gap-1.5 flex-wrap">
              <button
                @click="props.state.doColdStartBackfill()"
                :disabled="props.state.coldStartLoading.value"
                class="px-2.5 py-1 rounded bg-sky-900/60 hover:bg-sky-800/80 border border-sky-600/60 text-sky-200 text-xs font-semibold cursor-pointer flex items-center gap-1 transition-all"
                title="依据前文正文提取生成因果交接契约"
              >
                <span>⚡</span>
                <span>{{ props.state.coldStartLoading.value ? '提炼中...' : '冷启动一键回溯交接' }}</span>
              </button>
              <button
                @click="props.state.doPreWriteGateCheck()"
                :disabled="props.state.preWriteGateLoading.value"
                class="px-2.5 py-1 rounded bg-indigo-900/60 hover:bg-indigo-800/80 border border-indigo-600/60 text-indigo-200 text-xs font-semibold cursor-pointer flex items-center gap-1 transition-all"
                title="检查本章细纲与草稿是否违背前文交接与套话禁令"
              >
                <span>🛡️</span>
                <span>{{ props.state.preWriteGateLoading.value ? '门禁自检中...' : '因果门禁自检' }}</span>
              </button>
              <button
                @click="props.state.loadHandoff(props.state.chapterNum.value > 1 ? props.state.chapterNum.value - 1 : 1); fetchCanonHistory()"
                class="px-2 py-1 rounded bg-stone-800 hover:bg-stone-700 border border-stone-700 text-stone-300 text-xs cursor-pointer flex items-center gap-1 transition-all"
                title="从磁盘重新载入当前契约与正史"
              >
                <span>🔄</span>
                <span>刷新</span>
              </button>
            </div>
          </div>

          <!-- 门禁检查结果横幅 (若已执行自检) -->
          <div v-if="props.state.preWriteGateResult.value" class="p-2.5 rounded-lg border text-xs" :class="props.state.preWriteGateResult.value.passed ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-200' : 'bg-rose-950/40 border-rose-500/60 text-rose-200'">
            <div class="font-bold flex items-center justify-between">
              <span>{{ props.state.preWriteGateResult.value.passed ? '✅ 门禁检验通过：无因果冲突与违禁套话' : '⚠️ 门禁拦截到潜在套话或重复陈述' }}</span>
              <span class="text-[10px] opacity-75 font-mono">第 {{ props.state.chapterNum.value }} 章前置门禁</span>
            </div>
            <ul v-if="props.state.preWriteGateResult.value.violations && props.state.preWriteGateResult.value.violations.length" class="mt-1 list-disc list-inside space-y-0.5">
              <li v-for="(v, vi) in props.state.preWriteGateResult.value.violations" :key="vi">{{ v }}</li>
            </ul>
          </div>

          <!-- 幕间因果交接（Semantic Handoff） -->
          <div class="p-3.5 bg-gradient-to-r from-sky-950/40 via-indigo-950/30 to-sky-950/40 rounded-xl border border-sky-800/40 space-y-2">
            <h5 class="text-sky-300 font-bold mb-1 font-sans flex items-center justify-between">
              <span class="flex items-center gap-1.5">
                <span>📋</span>
                <span>【第 {{ props.state.chapterNum.value > 1 ? props.state.chapterNum.value - 1 : 1 }} 章 ➔ 第 {{ props.state.chapterNum.value > 1 ? props.state.chapterNum.value : 2 }} 章因果交接契约 (本章装配输入)】</span>
              </span>
              <span v-if="props.state.handoffData.value" class="text-[10px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800/40">契约就绪</span>
            </h5>
            <div v-if="props.state.handoffData.value" class="space-y-1.5 text-stone-300 font-sans">
              <div class="p-2 bg-black/40 rounded border border-sky-900/40">
                <span class="text-sky-300 font-semibold">1. 核心实锤事实转变：</span>
                <p class="text-stone-300 mt-0.5">{{ props.state.handoffData.value.what_changed || '已承接本章推进' }}</p>
              </div>
              <div class="p-2 bg-black/40 rounded border border-sky-900/40">
                <span class="text-amber-300 font-semibold">2. 下一章核心即时意图：</span>
                <p class="text-stone-300 mt-0.5">{{ props.state.handoffData.value.active_intentions || '接续当前情节继续推进' }}</p>
              </div>
              <div v-if="props.state.handoffData.value.must_not_restate && props.state.handoffData.value.must_not_restate.length" class="p-2 bg-rose-950/30 rounded border border-rose-900/40 text-rose-200">
                <span class="font-semibold text-rose-300">3. 🚫 开篇绝密禁令（读者已知，严禁下章开篇旁白重复科普）：</span>
                <ul class="list-disc list-inside mt-0.5 pl-1">
                  <li v-for="(m, mi) in props.state.handoffData.value.must_not_restate" :key="mi">{{ m }}</li>
                </ul>
              </div>
              <div v-if="props.state.handoffData.value.worn_phrases && props.state.handoffData.value.worn_phrases.length" class="p-1.5 bg-amber-950/30 rounded border border-amber-900/30 text-amber-200">
                <span class="font-semibold text-amber-300">4. 🚫 跨章套路词黑名单：</span>
                <span>{{ props.state.handoffData.value.worn_phrases.join('、') }}</span>
              </div>
              <div v-if="props.state.handoffData.value.chapter_tail" class="p-2 bg-black/60 rounded border border-stone-800 text-[11px] font-mono text-stone-400">
                <span class="text-stone-500">5. 物理尾声锚点：</span>
                <span>"...{{ props.state.handoffData.value.chapter_tail.slice(-200) }}"</span>
              </div>
            </div>
            <div v-else class="text-stone-500 italic py-2 text-center text-xs">
              暂无当前交接数据。可点击上方【⚡ 冷启动一键回溯交接】从已生成章节提炼契约，或启动全链路生成链运行至 Stage 6 时自动提取。
            </div>
          </div>

          <!-- 正史设定页与事实边界 -->
          <div class="p-3.5 bg-purple-950/20 rounded-xl border border-purple-900/40 space-y-1.5">
            <h5 class="text-purple-300 font-bold mb-1 font-sans flex items-center justify-between">
              <span class="flex items-center gap-1.5">
                <span>📜</span>
                <span>【正史设定页与事实边界 (Novel_canon_history.txt)】</span>
              </span>
              <span class="text-[10px] text-purple-400 font-normal">基于正文定稿事实 · 冲突受控</span>
            </h5>
            <div class="whitespace-pre-wrap text-stone-300 font-mono text-xs leading-relaxed max-h-60 overflow-y-auto pr-2 bg-black/50 p-2.5 rounded border border-stone-800">
              {{ displayCanon || '尚未生成正史设定页。全自动流水线完成 Stage 6.2 时将自动提取更新。' }}
            </div>
          </div>

          <!-- 固定写法表与底层生产规则 (仅英文出海双语模式启用，与纯中文流水线完全隔离) -->
          <div v-if="props.state.pipelineMode.value === 'bilingual'" class="p-3.5 bg-indigo-950/20 rounded-xl border border-indigo-900/40 space-y-2">
            <div class="flex items-center justify-between">
              <h5 class="text-indigo-300 font-bold font-sans flex items-center gap-1.5">
                <span>📖</span>
                <span>【固定写法表 (一词一译专有对照 · 随书增补)】</span>
              </h5>
              <div class="flex items-center gap-2">
                <button
                  @click="props.state.loadFixedTerms()"
                  class="px-2 py-0.5 rounded bg-stone-800 hover:bg-stone-700 text-stone-300 text-[11px] cursor-pointer"
                >
                  刷新词表
                </button>
                <button
                  @click="props.state.saveFixedTerms()"
                  class="px-2 py-0.5 rounded bg-indigo-900/80 hover:bg-indigo-800 text-indigo-200 text-[11px] border border-indigo-700/60 cursor-pointer"
                >
                  保存修改
                </button>
              </div>
            </div>
            <textarea
              v-model="props.state.fixedTermsContent.value"
              rows="5"
              placeholder="载入中或尚未配置固定写法表..."
              class="w-full bg-black/50 border border-stone-800 rounded p-2 text-stone-300 font-mono text-xs leading-relaxed focus:outline-none focus:border-indigo-500"
            ></textarea>
            <div class="text-[10px] text-stone-500 flex items-center justify-between">
              <span>注：严格遵循一词一译（如 Ella Clare, Blackwood Forest, Lycan King 等），生成、翻译与质检全链路自动应用。</span>
              <label class="flex items-center gap-1.5 cursor-pointer text-stone-400 hover:text-stone-200">
                <input
                  type="checkbox"
                  v-model="props.state.adultMode.value"
                  class="rounded border-stone-700 bg-stone-900 text-pink-500 focus:ring-0 cursor-pointer"
                />
                <span :class="props.state.adultMode.value ? 'text-pink-300 font-bold' : ''">成人向亲密模块(规范转场/失控三要素)</span>
              </label>
            </div>
          </div>
        </div>

        <!-- 记忆归档 -->
        <div v-show="activeTab === 'archive'" class="space-y-3 font-sans text-xs">
          <!-- 幕间因果交接（Semantic Handoff） -->
          <div v-if="props.state.handoffData.value" class="p-3.5 bg-sky-950/20 rounded-xl border border-sky-900/40">
            <h5 class="text-sky-300 font-bold mb-1.5 font-sans flex items-center justify-between">
              <span class="flex items-center gap-1.5">
                <span>📋</span>
                <span>【下章因果交接契约 (Semantic Handoff)】</span>
              </span>
              <span class="text-[10px] text-sky-400 font-normal">为第 {{ props.state.chapterNum.value + 1 }} 章装配</span>
            </h5>
            <div class="space-y-1.5 text-stone-300">
              <div><strong class="text-sky-200">核心转变：</strong>{{ props.state.handoffData.value.what_changed }}</div>
              <div><strong class="text-amber-200">下章意图：</strong>{{ props.state.handoffData.value.active_intentions }}</div>
              <div v-if="props.state.handoffData.value.must_not_restate && props.state.handoffData.value.must_not_restate.length" class="text-rose-300">
                <strong>🚫 严禁开篇重复科普：</strong>{{ props.state.handoffData.value.must_not_restate.join('；') }}
              </div>
            </div>
          </div>

          <!-- 正史设定页 -->
          <div class="p-3.5 bg-purple-950/20 rounded-xl border border-purple-900/40">
            <h5 class="text-purple-300 font-bold mb-1.5 font-sans flex items-center justify-between">
              <span class="flex items-center gap-1.5">
                <span>📜</span>
                <span>【正史设定页与事实边界】</span>
              </span>
              <span class="text-[10px] text-purple-400 font-normal">基于正文定稿事实 · 冲突受控</span>
            </h5>
            <div class="whitespace-pre-wrap text-stone-300 font-serif leading-relaxed max-h-80 overflow-y-auto pr-2">{{ displayCanon || '已依据正史规则提取并更新事实边界' }}</div>
          </div>
          <div class="p-3.5 bg-stone-900/70 rounded-xl border border-stone-800">
            <h5 class="text-cyan-300 font-bold mb-1.5 font-sans flex items-center gap-1.5">
              <span>📖</span>
              <span>【全书前文摘要快照】</span>
            </h5>
            <div class="whitespace-pre-wrap text-stone-300 font-serif leading-relaxed">{{ displaySummary || '已将本章摘要同步至全局状态' }}</div>
          </div>
          <div class="p-3.5 bg-stone-900/70 rounded-xl border border-stone-800">
            <h5 class="text-amber-300 font-bold mb-1.5 font-sans flex items-center gap-1.5">
              <span>👤</span>
              <span>【角色心境与动态更新】</span>
            </h5>
            <div class="whitespace-pre-wrap text-stone-300 font-serif leading-relaxed">{{ displayCharState || '已记录角色关系、伏笔与隐患状态' }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 流动激光导管动画 */
@keyframes conduit-flow {
  0% {
    background-position: 0% 50%;
  }
  100% {
    background-position: 200% 50%;
  }
}

.conduit-laser-active {
  background: linear-gradient(90deg, #06b6d4, #6366f1, #10b981, #06b6d4);
  background-size: 200% 100%;
  animation: conduit-flow 1.5s linear infinite;
}

/* 旋转雷达扫描环 */
@keyframes spin-radar {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.animate-radar {
  animation: spin-radar 3s linear infinite;
}

/* 呼吸发光边框 */
@keyframes pulse-glow {
  0%, 100% {
    box-shadow: 0 0 10px rgba(6, 182, 212, 0.35), inset 0 0 8px rgba(6, 182, 212, 0.15);
  }
  50% {
    box-shadow: 0 0 22px rgba(6, 182, 212, 0.65), inset 0 0 14px rgba(6, 182, 212, 0.3);
  }
}

.glow-active-node {
  animation: pulse-glow 2s ease-in-out infinite;
}

/* 4-bar 神经均衡器声波动画 */
@keyframes eq-bar-1 { 0%, 100% { height: 25%; } 50% { height: 95%; } }
@keyframes eq-bar-2 { 0%, 100% { height: 75%; } 50% { height: 35%; } }
@keyframes eq-bar-3 { 0%, 100% { height: 45%; } 50% { height: 100%; } }
@keyframes eq-bar-4 { 0%, 100% { height: 85%; } 50% { height: 20%; } }

.animate-eq-1 { animation: eq-bar-1 0.75s ease-in-out infinite; }
.animate-eq-2 { animation: eq-bar-2 0.65s ease-in-out infinite 0.15s; }
.animate-eq-3 { animation: eq-bar-3 0.85s ease-in-out infinite 0.3s; }
.animate-eq-4 { animation: eq-bar-4 0.7s ease-in-out infinite 0.45s; }

/* 质检合格公章全息光芒 */
@keyframes stamp-ripple {
  0% { transform: scale(0.97); opacity: 0.9; }
  50% { transform: scale(1.02); opacity: 1; box-shadow: 0 0 15px rgba(16, 185, 129, 0.5); }
  100% { transform: scale(0.97); opacity: 0.9; }
}

.animate-stamp {
  animation: stamp-ripple 2.5s ease-in-out infinite;
}
</style>
