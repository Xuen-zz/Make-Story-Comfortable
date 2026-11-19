# -*- coding: utf-8 -*-

# 1. Update PipelineVisualCard.vue
with open("frontend/src/components/workshop/PipelineVisualCard.vue", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("\r\n", "\n")

# A. handleNodeClick
old_click = """    case 4:
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
      break
    case 5: activeTab.value = 'audit'; break
    case 6:
      activeTab.value = 'continuity'
      await props.state.loadHandoff(props.state.chapterNum.value)
      await fetchCanonHistory()
      break"""

new_click = """    case 4:
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
      break"""

if old_click in text:
    text = text.replace(old_click, new_click, 1)
    print("APPLIED_PVC_CLICK")
else:
    print("FAILED_PVC_CLICK")

# B. Header description
old_desc = """            <span class="text-stone-600">|</span>
            <span class="text-stone-300">分场景起草 ➔ 中文去套话润色 ➔ 美式英译 ➔ 独立双语质检 ➔ 记忆同步归档</span>"""

new_desc = """            <span class="text-stone-600">|</span>
            <span class="text-stone-300">
              {{ state.pipelineMode.value === 'fast_zh'
                  ? '细纲装配 ➔ Gemini Low极速起草 ➔ 朱雀自检&GPT审校 ➔ 正史记忆同步 (番茄极速 4 步 · 跳过英译)'
                  : '细纲装配 ➔ 中文起草 ➔ 朱雀自检&GPT审校 ➔ 美式英译 ➔ 独立双语质检 ➔ 记忆同步归档 (出海完整 6 步)' }}
            </span>"""

if old_desc in text:
    text = text.replace(old_desc, new_desc, 1)
    print("APPLIED_PVC_DESC")
else:
    print("FAILED_PVC_DESC")

# C. Actions: Add Mode Switcher
old_actions = """        <!-- 核心动作按钮组合 -->
        <div class="flex items-center gap-2.5">
          <!-- 运行 / 终止 -->"""

new_actions = """        <!-- 核心动作按钮组合 -->
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
              title="切换至番茄/纯中文模式（极速 4 步：草稿 ➔ 朱雀自检与GPT审校 ➔ 正史归档，跳过英文译制，提速100%）"
            >
              <span>🍅</span>
              <span>番茄/纯中文 (极速4步)</span>
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
              title="切换至出海双语模式（完整 6 步：含美式英文翻译与双语审计）"
            >
              <span>🌐</span>
              <span>出海双语 (完整6步)</span>
            </button>
          </div>

          <!-- 运行 / 终止 -->"""

if old_actions in text:
    text = text.replace(old_actions, new_actions, 1)
    print("APPLIED_PVC_ACTIONS")
else:
    print("FAILED_PVC_ACTIONS")

# D. Grid columns
old_grid = """      <!-- 6 节点流程拓扑卡片链条 -->
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 relative">"""

new_grid = """      <!-- 流程拓扑卡片链条 (自适应 4 步 vs 6 步) -->
      <div :class="['grid grid-cols-2 md:grid-cols-3 gap-3 relative', state.pipelineMode.value === 'fast_zh' ? 'lg:grid-cols-4' : 'lg:grid-cols-6']">"""

if old_grid in text:
    text = text.replace(old_grid, new_grid, 1)
    print("APPLIED_PVC_GRID")
else:
    print("FAILED_PVC_GRID")

# E. Badge for Stage 6 / Stage 4
old_badge = """            <div v-if="stage.id === 6" class="mt-1.5 flex items-center gap-1 text-[10px] font-mono">
              <span class="px-1.5 py-0.5 rounded bg-purple-950/90 border border-purple-600/60 font-semibold text-purple-200 flex items-center gap-1">
                <span>📜</span><span>正史演进与归档</span>
              </span>
            </div>"""

new_badge = """            <div v-if="(state.pipelineMode.value === 'fast_zh' ? stage.id === 4 : stage.id === 6)" class="mt-1.5 flex items-center gap-1 text-[10px] font-mono">
              <span class="px-1.5 py-0.5 rounded bg-purple-950/90 border border-purple-600/60 font-semibold text-purple-200 flex items-center gap-1">
                <span>📜</span><span>正史演进与归档</span>
              </span>
            </div>"""

if old_badge in text:
    text = text.replace(old_badge, new_badge, 1)
    print("APPLIED_PVC_BADGE")
else:
    print("FAILED_PVC_BADGE")

# F. Metric text
old_metrics = """            <span v-else-if="stage.id === 4 && englishWordCount > 0" class="text-indigo-300 font-mono font-semibold">
              {{ englishWordCount }} 词英译
            </span>"""

new_metrics = """            <span v-else-if="state.pipelineMode.value === 'fast_zh' && stage.id === 4 && (displaySummary || state.pipelineData.value.summary)" class="text-cyan-300 font-mono">
              ✓ 记忆与正史已同步
            </span>
            <span v-else-if="stage.id === 4 && englishWordCount > 0" class="text-indigo-300 font-mono font-semibold">
              {{ englishWordCount }} 词英译
            </span>"""

if old_metrics in text:
    text = text.replace(old_metrics, new_metrics, 1)
    print("APPLIED_PVC_METRICS")
else:
    print("FAILED_PVC_METRICS")

# G. Conduit arrow
old_arrow = """          <!-- 右向流程导管箭头指示器 (桌面端展示) -->
          <div
            v-if="idx < 5" """

new_arrow = """          <!-- 右向流程导管箭头指示器 (桌面端展示) -->
          <div
            v-if="idx < state.pipelineStages.value.length - 1" """

if old_arrow in text:
    text = text.replace(old_arrow, new_arrow, 1)
    print("APPLIED_PVC_ARROW")
else:
    print("FAILED_PVC_ARROW")

# H. Tab Polish button label
old_tab_polish = """          <button
            @click="activeTab = 'polish'"
            :class="[
              'px-3 py-1.5 rounded-lg font-medium transition-colors cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
              activeTab === 'polish' ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/80 shadow-[0_0_10px_rgba(6,182,212,0.2)]' : 'text-stone-400 hover:text-stone-200 hover:bg-stone-900'
            ]"
          >
            <span>🎯</span>
            <span>润色正文与清单</span>
            <span v-if="polishedWordCount > 0" class="font-mono text-emerald-400">({{ polishedWordCount }})</span>
          </button>"""

new_tab_polish = """          <button
            @click="activeTab = 'polish'"
            :class="[
              'px-3 py-1.5 rounded-lg font-medium transition-colors cursor-pointer flex items-center gap-1.5 whitespace-nowrap',
              activeTab === 'polish' ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/80 shadow-[0_0_10px_rgba(6,182,212,0.2)]' : 'text-stone-400 hover:text-stone-200 hover:bg-stone-900'
            ]"
          >
            <span>🛡️</span>
            <span>朱雀与GPT审校</span>
            <span v-if="polishedWordCount > 0" class="font-mono text-emerald-400">({{ polishedWordCount }})</span>
          </button>"""

if old_tab_polish in text:
    text = text.replace(old_tab_polish, new_tab_polish, 1)
    print("APPLIED_PVC_TAB_POLISH")
else:
    print("FAILED_PVC_TAB_POLISH")

# I. Tab translation and audit visibility
old_tabs_en = """          <button
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
            @click="activeTab = 'audit'" """

new_tabs_en = """          <button
            v-if="state.pipelineMode.value === 'bilingual' || englishWordCount > 0"
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
            v-if="state.pipelineMode.value === 'bilingual' || Boolean(displayAudit || state.pipelineData.value.auditPass)"
            @click="activeTab = 'audit'" """

if old_tabs_en in text:
    text = text.replace(old_tabs_en, new_tabs_en, 1)
    print("APPLIED_PVC_TABS_EN")
else:
    print("FAILED_PVC_TABS_EN")

# J. Zhuque AI score banner inside Polish Tab
old_polish_view = """          <div v-if="!displayPolished" class="text-stone-500 italic font-mono">润色产物待生成...</div>
          <template v-else>
            <div class="p-3.5 bg-stone-900/70 rounded-xl border border-stone-800">"""

new_polish_view = """          <div v-if="!displayPolished" class="text-stone-500 italic font-mono">润色产物待生成...</div>
          <template v-else>
            <!-- 腾讯朱雀 AI 味雷达仪表盘 -->
            <div v-if="state.pipelineData.value.zhuque && state.pipelineData.value.zhuque.pre_ai_rate !== undefined" class="p-3 bg-stone-900/90 border border-purple-900/50 rounded-xl flex items-center justify-between text-xs shadow-inner mb-3">
              <div class="flex items-center gap-3 flex-wrap">
                <span class="px-2 py-0.5 rounded text-xs font-bold bg-purple-950 text-purple-300 border border-purple-800">
                  腾讯云朱雀自检
                </span>
                <span class="text-stone-300">初检 AI 率: <strong class="text-rose-400 font-mono">{{ state.pipelineData.value.zhuque.pre_ai_rate }}%</strong></span>
                <span class="text-stone-500">➔</span>
                <span class="text-stone-300">Codex (GPT) 改写后: <strong class="text-emerald-400 font-mono">{{ state.pipelineData.value.zhuque.post_ai_rate }}%</strong></span>
                <span v-if="state.pipelineData.value.zhuque.rate_drop > 0" class="text-emerald-400 font-semibold font-mono">
                  (↓ 降幅 {{ state.pipelineData.value.zhuque.rate_drop }}%)
                </span>
              </div>
              <div class="flex items-center gap-2">
                <span v-if="state.pipelineData.value.zhuque.post_ai_rate !== null && state.pipelineData.value.zhuque.post_ai_rate <= 25" class="px-2.5 py-1 rounded text-xs font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                  🟢 质检放行合格
                </span>
                <span v-else-if="state.pipelineData.value.zhuque.post_ai_rate !== null" class="px-2.5 py-1 rounded text-xs font-bold bg-amber-950 text-amber-400 border border-amber-800">
                  🟡 AI率偏高
                </span>
              </div>
            </div>

            <div class="p-3.5 bg-stone-900/70 rounded-xl border border-stone-800">"""

if old_polish_view in text:
    text = text.replace(old_polish_view, new_polish_view, 1)
    print("APPLIED_PVC_POLISH_BANNER")
else:
    print("FAILED_PVC_POLISH_BANNER")

with open("frontend/src/components/workshop/PipelineVisualCard.vue", "w", encoding="utf-8") as f:
    f.write(text.replace("\n", "\r\n"))

# 2. Update WorkshopView.vue to conditionally display PipelineTranslationCard
with open("frontend/src/views/WorkshopView.vue", "r", encoding="utf-8") as f:
    w_text = f.read()

w_text = w_text.replace("\r\n", "\n")

old_w_card = """          <!-- 专属独立展示区域：出海美式英文译稿与双语对照阅读专区 -->
          <PipelineTranslationCard :state="state" />"""

new_w_card = """          <!-- 专属独立展示区域：出海美式英文译稿与双语对照阅读专区（仅在出海模式或已存在译文时显示） -->
          <PipelineTranslationCard v-if="state.pipelineMode.value === 'bilingual' || Boolean(state.translateResult.value)" :state="state" />"""

if old_w_card in w_text:
    w_text = w_text.replace(old_w_card, new_w_card, 1)
    print("APPLIED_WORKSHOP_VIEW_CARD")
else:
    print("FAILED_WORKSHOP_VIEW_CARD")

with open("frontend/src/views/WorkshopView.vue", "w", encoding="utf-8") as f:
    f.write(w_text.replace("\n", "\r\n"))
