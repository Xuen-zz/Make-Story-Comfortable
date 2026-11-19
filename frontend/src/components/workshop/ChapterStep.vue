<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'
import StepCard from '@/components/StepCard.vue'
import StreamOutput from '@/components/StreamOutput.vue'

const props = defineProps<{ state: ReturnType<typeof useWorkshopState> }>()

const showSpanRepair = ref(false)
const showContinuityDetails = ref(false)

const nextNewChapter = computed(() => {
  const nums = props.state.existingChapters.value.map(c => c.num)
  return nums.length > 0 ? Math.max(...nums) + 1 : 1
})

onMounted(async () => {
  await props.state.loadExistingChapters()
  if (!props.state.chapter.value.result) {
    await props.state.loadChapterDraft(props.state.chapterNum.value)
  }
})

async function selectAndLoadChapter(num: number) {
  await props.state.selectChapter(num)
}

function selectNewChapter() {
  props.state.selectChapter(nextNewChapter.value)
}
</script>

<template>
  <StepCard :step="3" title="生成章节草稿" description="根据蓝图逐章生成正文">
    <div class="space-y-3">
      <!-- 已保存章节切换栏 -->
      <div v-if="state.existingChapters.value.length > 0" class="flex items-center gap-2 flex-wrap p-2.5 bg-emerald-50/80 border border-emerald-200 rounded-lg text-xs text-emerald-950">
        <span class="font-semibold text-emerald-900 flex items-center gap-1">
          <span>📚 已保存章节：</span>
        </span>
        <button
          v-for="ch in state.existingChapters.value"
          :key="ch.num"
          @click="selectAndLoadChapter(ch.num)"
          class="px-2.5 py-1 rounded border text-xs transition-colors flex items-center gap-1 cursor-pointer"
          :class="state.chapterNum.value === ch.num
            ? 'bg-emerald-700 text-white border-emerald-800 font-semibold shadow-sm'
            : 'bg-white text-emerald-800 border-emerald-300 hover:bg-emerald-100'"
          type="button"
        >
          <span>第 {{ ch.num }} 章</span>
          <span class="text-[10px] opacity-80">{{ ch.has_final ? '(已定稿)' : '(草稿)' }}</span>
        </button>
        <button
          @click="selectNewChapter()"
          class="px-2.5 py-1 rounded border border-dashed border-emerald-500 text-emerald-800 hover:bg-emerald-100 text-xs font-medium ml-auto cursor-pointer"
          type="button"
        >
          ➕ 新建第 {{ nextNewChapter }} 章草稿
        </button>
      </div>
      <!-- 剧情参数快捷智能装配控制栏 -->
      <div class="flex items-center justify-between p-2.5 bg-gradient-to-r from-amber-50/90 to-amber-100/60 border border-amber-200/90 rounded-lg text-xs flex-wrap gap-2">
        <div class="flex items-center gap-2">
          <span class="text-base">🪄</span>
          <div>
            <span class="font-bold text-amber-950">第 {{ state.chapterNum.value }} 章剧情生成参数</span>
            <span class="text-[11px] text-amber-800 ml-1.5 hidden sm:inline">（切章时已自动从大纲与细纲装配）</span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="state.autoFillChapterParams()"
            class="px-2.5 py-1 bg-white border border-amber-300 rounded shadow-sm text-xs font-semibold text-amber-900 hover:bg-amber-50 hover:border-amber-400 flex items-center gap-1 cursor-pointer transition-all"
            type="button"
            title="重新从大纲和细纲中提取人物、物品、地点、时限与指导"
          >
            <span>✨ 重新自动填充</span>
          </button>
          <button
            @click="state.clearChapterParams()"
            class="px-2 py-1 bg-white border border-stone-200 rounded text-xs text-stone-600 hover:bg-stone-50 hover:text-stone-900 cursor-pointer transition-all"
            type="button"
            title="清空当前 5 项参数输入框"
          >
            🧹 清空
          </button>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">章节号</label>
          <input v-model.number="state.chapterNum.value" type="number" min="1" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">文风（文笔层）</label>
          <select v-model="state.chStyle.value" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
            <option v-for="s in state.styleList.value" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">叙事DNA（叙事层）</label>
          <select v-model="state.chNarrativeStyle.value" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm">
            <option v-for="s in state.styleList.value" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">涉及人物</label>
          <input v-model="state.charactersInvolved.value" :placeholder="`从大纲自动提取，如：艾拉、达米安…`" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">关键物品</label>
          <input v-model="state.keyItems.value" :placeholder="`从细纲提取的道具/信物，如：圣化药剂、暗金狼纹…`" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">场景地点</label>
          <input v-model="state.sceneLocation.value" :placeholder="`场景路径，如：后山药房 ➔ 圣殿祭坛…`" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">时间约束</label>
          <input v-model="state.timeConstraint.value" :placeholder="`如：成年礼仪式进行时、暴雨深夜至黎明…`" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />
        </div>
        <div class="sm:col-span-2">
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">章节指导（覆盖全局）</label>
          <input v-model="state.chGuidance.value" :placeholder="`本章核心主线事件与冲突张力要点…`" class="w-full border border-[var(--color-parchment-darker)] rounded-md px-3 py-2 text-sm" />
        </div>
        <div class="flex items-center gap-4 flex-wrap">
          <div class="flex items-center gap-1.5">
            <input id="inject-world" v-model="state.injectWorldBuilding.value" type="checkbox" class="rounded border-[var(--color-parchment-darker)]" />
            <label for="inject-world" class="text-xs text-[var(--color-ink-light)] select-none">注入世界观设定</label>
          </div>
          <div class="flex items-center gap-1.5">
            <input id="scene-by-scene" v-model="state.sceneByScene.value" type="checkbox" class="rounded border-[var(--color-parchment-darker)]" />
            <label for="scene-by-scene" class="text-xs text-[var(--color-ink-light)] select-none">按场景分段生成（需细纲，高强度场景浓墨重彩/普通场景简练清晰）</label>
          </div>
        </div>
      </div>

      <!-- 细纲关联状态 -->
      <div v-if="state.currentChapterOutline.value" class="p-2.5 bg-amber-50/80 border border-amber-200 rounded-md text-xs text-amber-900">
        <details>
          <summary class="cursor-pointer font-medium flex items-center gap-1.5 select-none text-[var(--color-leather)]">
            <span>📋</span>
            <span>已成功关联【第 {{ state.chapterNum.value }} 章细纲】（点击可展开查看场景要点）</span>
            <span class="text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded ml-auto">按场景分段生成时将自动注入</span>
          </summary>
          <pre class="mt-2 text-[11px] font-mono whitespace-pre-wrap text-[var(--color-ink)] bg-white p-2.5 rounded border border-amber-200 max-h-52 overflow-y-auto">{{ state.currentChapterOutline.value }}</pre>
        </details>
      </div>
      <div v-else-if="state.sceneByScene.value" class="p-2 bg-yellow-50 border border-yellow-200 rounded-md text-xs text-yellow-800 flex items-center gap-1.5">
        <span>⚠️</span>
        <span>提示：当前第 {{ state.chapterNum.value }} 章尚未在「生成章节细纲」中找到细纲。建议先在上一步生成细纲以获取最佳分段效果。</span>
      </div>
      <!-- ── 因果连续性与幕间交接（Semantic Handoff & Continuity Engine）控制卡片 ── -->
      <div class="p-3 bg-gradient-to-r from-indigo-50/90 via-sky-50/80 to-indigo-100/60 border border-indigo-200/90 rounded-lg text-xs space-y-2.5 shadow-sm">
        <div class="flex items-center justify-between flex-wrap gap-2">
          <div class="flex items-center gap-2">
            <span class="text-base">🔗</span>
            <div>
              <span class="font-bold text-indigo-950">第 {{ state.chapterNum.value }} 章因果连续性与交接契约 (Semantic Handoff)</span>
              <span class="text-[11px] text-indigo-700 ml-1.5 hidden sm:inline">（防止开篇水字数交代前情、消除新老章节割裂感）</span>
            </div>
          </div>
          <div class="flex items-center gap-1.5 flex-wrap">
            <button
              @click="state.doPreWriteGateCheck()"
              :disabled="state.preWriteGateLoading.value || !state.llmConfig.value"
              class="px-2.5 py-1 bg-white border border-indigo-300 text-indigo-900 rounded font-semibold hover:bg-indigo-50 flex items-center gap-1 cursor-pointer transition-all disabled:opacity-50"
              type="button"
              title="动笔前对当前大纲进行逻辑门禁体检，低成本拦截设定冲突与逻辑漏洞"
            >
              <span>{{ state.preWriteGateLoading.value ? '体检中…' : '🩺 大纲前置门禁体检' }}</span>
            </button>
            <button
              @click="state.doColdStartBackfill()"
              :disabled="state.coldStartLoading.value || !state.llmConfig.value"
              class="px-2.5 py-1 bg-gradient-to-r from-amber-500 to-orange-500 text-white rounded font-semibold hover:from-amber-600 hover:to-orange-600 shadow-sm flex items-center gap-1 cursor-pointer transition-all disabled:opacity-50"
              type="button"
              title="已有前文章节？一键从历史正文提炼正史底册与接续因果，彻底扫除新旧章节割裂！"
            >
              <span>{{ state.coldStartLoading.value ? '萃取中…' : '⚡ 一键历史冷启动回溯' }}</span>
            </button>
            <button
              @click="showSpanRepair = !showSpanRepair"
              class="px-2.5 py-1 bg-white border border-stone-300 text-stone-700 rounded font-medium hover:bg-stone-50 flex items-center gap-1 cursor-pointer transition-all"
              type="button"
              title="无需推翻整章，针对瑕疵句子进行外科手术式精准修补替换"
            >
              <span>✂️ {{ showSpanRepair ? '收起修补' : '句子级修补' }}</span>
            </button>
            <button
              @click="showContinuityDetails = !showContinuityDetails"
              class="px-2 py-1 bg-indigo-100/70 border border-indigo-200 text-indigo-800 rounded text-xs hover:bg-indigo-200/70 cursor-pointer"
              type="button"
            >
              {{ showContinuityDetails ? '收起详情 ▲' : '查看交接契约 ▼' }}
            </button>
          </div>
        </div>

        <!-- 门禁体检结果展示 -->
        <div v-if="state.preWriteGateResult.value" class="p-2.5 bg-white/95 rounded border text-xs" :class="state.preWriteGateResult.value.passed ? 'border-emerald-300 text-emerald-950' : 'border-amber-300 text-amber-950'">
          <div class="flex items-center gap-1.5 font-bold mb-1">
            <span>{{ state.preWriteGateResult.value.passed ? '✅ 门禁体检结论：' : '⚠️ 门禁体检提示：' }}</span>
            <span>{{ state.preWriteGateResult.value.summary }}</span>
          </div>
          <div v-if="state.preWriteGateResult.value.contradictions && state.preWriteGateResult.value.contradictions.length > 0" class="text-rose-700 space-y-0.5 mt-1">
            <div class="font-semibold">设定矛盾点：</div>
            <div v-for="(c, ci) in state.preWriteGateResult.value.contradictions" :key="ci" class="pl-2">• {{ c }}</div>
          </div>
          <div v-if="state.preWriteGateResult.value.continuity_warnings && state.preWriteGateResult.value.continuity_warnings.length > 0" class="text-amber-800 space-y-0.5 mt-1">
            <div class="font-semibold">衔接薄弱/水字数风险：</div>
            <div v-for="(w, wi) in state.preWriteGateResult.value.continuity_warnings" :key="wi" class="pl-2">• {{ w }}</div>
          </div>
          <div v-if="state.preWriteGateResult.value.repair_suggestions" class="mt-1 text-stone-700 bg-stone-50 p-1.5 rounded border border-stone-200">
            <span class="font-semibold text-stone-900">💡 优化建议：</span>
            <span>{{ state.preWriteGateResult.value.repair_suggestions }}</span>
          </div>
        </div>

        <!-- 冷启动提取结果提示 -->
        <div v-if="state.coldStartResult.value" class="p-2 bg-emerald-50 border border-emerald-300 rounded text-xs text-emerald-900 flex items-center justify-between">
          <span>🎉 {{ state.coldStartResult.value.message }}</span>
          <button @click="state.coldStartResult.value = null" class="text-xs text-stone-400 hover:text-stone-700 ml-2">✕</button>
        </div>

        <!-- 句子级修补工作区 -->
        <div v-if="showSpanRepair" class="p-2.5 bg-white rounded-lg border border-indigo-200 space-y-2">
          <div class="font-bold text-indigo-950 flex items-center gap-1">
            <span>✂️ 局部句子级外科手术式修补（Span Repair）</span>
            <span class="text-[11px] font-normal text-stone-500">仅重写选中的句子，100%保持原稿其余段落稳定</span>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div>
              <label class="block text-[11px] text-stone-600 mb-0.5">原稿中需要被替换的句子（必须完全匹配原句）：</label>
              <textarea
                v-model="state.spanRepairTarget.value"
                rows="2"
                placeholder="在此粘贴原稿中需要修改的那句话（如：他嘴角勾起一丝冷笑…）"
                class="w-full border border-stone-300 rounded p-1.5 text-xs font-mono"
              ></textarea>
            </div>
            <div>
              <label class="block text-[11px] text-stone-600 mb-0.5">修补要求与修改指示：</label>
              <textarea
                v-model="state.spanRepairInstruction.value"
                rows="2"
                placeholder="写明修改意图（如：去除油腻套路，改为克制的眼神描写并增加警惕感）"
                class="w-full border border-stone-300 rounded p-1.5 text-xs"
              ></textarea>
            </div>
          </div>
          <div class="flex items-center justify-between">
            <span v-if="state.spanRepairResult.value" :class="state.spanRepairResult.value.success ? 'text-emerald-700 font-semibold' : 'text-rose-600'">
              {{ state.spanRepairResult.value.message }}
            </span>
            <span v-else></span>
            <button
              @click="state.doSpanRepair()"
              :disabled="state.spanRepairLoading.value || !state.spanRepairTarget.value.trim()"
              class="px-3 py-1 bg-indigo-600 text-white rounded text-xs font-semibold hover:bg-indigo-700 cursor-pointer disabled:opacity-50 ml-auto"
              type="button"
            >
              {{ state.spanRepairLoading.value ? '精准重写合入中…' : '⚡ 仅重写该句并合入原稿' }}
            </button>
          </div>
        </div>

        <!-- 展开的 Handoff 详情 -->
        <div v-if="showContinuityDetails" class="p-2.5 bg-white/90 rounded border border-indigo-200 text-xs space-y-1.5">
          <div v-if="state.handoffData.value">
            <div class="font-bold text-indigo-900 mb-1">📋 当前幕间因果交接（已自动注入正文生成 Prompt）：</div>
            <div class="text-stone-700"><strong>核心前情转变：</strong>{{ state.handoffData.value.what_changed || '（待定）' }}</div>
            <div class="text-stone-700"><strong>本章即时意图：</strong>{{ state.handoffData.value.active_intentions || '（待定）' }}</div>
            <div v-if="state.handoffData.value.must_not_restate && state.handoffData.value.must_not_restate.length" class="text-rose-700">
              <strong>🚫 开篇禁令（读者已知，严禁旁白重复解释）：</strong>
              <div v-for="(item, i) in state.handoffData.value.must_not_restate" :key="i" class="pl-2">• {{ item }}</div>
            </div>
            <div v-if="state.handoffData.value.worn_phrases && state.handoffData.value.worn_phrases.length" class="text-amber-800">
              <strong>🚫 跨章高频套路词禁令：</strong>{{ state.handoffData.value.worn_phrases.join('、') }}
            </div>
            <div v-if="state.handoffData.value.chapter_tail" class="text-stone-500 text-[11px] font-mono bg-stone-50 p-1.5 rounded mt-1">
              <strong>前章物理结尾接续锚点：</strong>"...{{ state.handoffData.value.chapter_tail.slice(-200) }}"
            </div>
          </div>
          <div v-else class="text-stone-500 py-1">
            暂无已保存的交接包。写完上一章定稿后将自动提炼，或点击上方【⚡ 一键历史冷启动回溯】从已写章节提取。
          </div>
        </div>
      </div>

      <div class="flex items-center justify-end gap-2.5 flex-wrap">
        <button
          @click="state.openPipelineControlRoom()"
          type="button"
          class="px-3.5 py-1.5 text-xs font-bold rounded-lg bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white shadow-md hover:shadow-cyan-500/25 transition-all flex items-center gap-1.5 cursor-pointer active:scale-95"
          title="打开工厂级全链路自动生产大屏：一键连贯完成起草、润色、英译、独立质检与全书记忆归档"
        >
          <span>🚀</span>
          <span>全链路自动生产控制舱</span>
        </button>
        <button @click="state.doGenerateChapter()" :disabled="state.chapter.value.running || !state.llmConfig.value" class="btn-primary" type="button">
          {{ state.chapter.value.running ? '生成中…' : '▶ 生成章节' }}
        </button>
      </div>
      <StreamOutput
        :key="state.chapterNum.value"
        :progress="state.chapter.value.progress"
        :result="state.chapter.value.result"
        :error="state.chapter.value.error"
        :running="state.chapter.value.running"
        :editable="true"
        :progress-value="state.chapter.value.progressValue"
        :cancelable="true"
        :placeholder="`第 ${state.chapterNum.value} 章本地暂无草稿内容。点击上方【▶ 生成章节】开始创作，或在此直接手动输入…`"
        @update:result="state.chapter.value.result = $event"
        @cancel="state.cancelSSE(state.chapter.value)"
      />
      <div v-if="state.chapter.value.result && !state.chapter.value.running" class="flex justify-end">
        <button @click="state.saveChapter()" class="btn-primary" type="button">💾 保存章节</button>
      </div>
    </div>
  </StepCard>
</template>
