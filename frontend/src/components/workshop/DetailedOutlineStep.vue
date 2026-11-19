<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'
import StepCard from '@/components/StepCard.vue'

const props = defineProps<{ state: ReturnType<typeof useWorkshopState> }>()

const activeTab = ref<'chapter' | 'full'>('chapter')
const showBatchControls = ref(false)

onMounted(async () => {
  if (!props.state.outlineText.value) {
    await props.state.loadOutlineText()
  }
  props.state.extractChapterToEdit(props.state.chapterNum.value || 1)
})

// 监听章节号变动，若切到了空章节或有细纲章节，保持实时抽取同步
watch(() => props.state.chapterNum.value, (newNum) => {
  if (newNum && props.state.outlineText.value) {
    props.state.extractChapterToEdit(newNum)
  }
})
</script>

<template>
  <StepCard :step="'2.5'" title="生成章节细纲" description="场景分解、节奏曲线、对话要点 — 在蓝图和正文之间的精细控制层">
    <div class="space-y-3">
      <!-- 模式与标签切换栏 -->
      <div class="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-parchment-darker)] pb-2">
        <div class="flex items-center gap-1.5 bg-[var(--color-parchment)] p-1 rounded-lg">
          <button
            @click="activeTab = 'chapter'"
            type="button"
            class="px-3 py-1.5 rounded-md text-xs font-semibold transition-all flex items-center gap-1.5"
            :class="activeTab === 'chapter'
              ? 'bg-[var(--color-leather)] text-[var(--color-parchment)] shadow-sm'
              : 'text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
          >
            <span>📌 第 {{ state.chapterNum.value }} 章细纲</span>
            <span
              class="text-[10px] px-1.5 py-0.2 rounded-full"
              :class="activeTab === 'chapter'
                ? 'bg-amber-100/20 text-amber-200'
                : 'bg-stone-200 text-stone-600'"
            >
              {{ state.outlineBatchResult.value ? state.outlineBatchResult.value.length + ' 字' : '无' }}
            </span>
          </button>

          <button
            @click="activeTab = 'full'"
            type="button"
            class="px-3 py-1.5 rounded-md text-xs font-semibold transition-all flex items-center gap-1.5"
            :class="activeTab === 'full'
              ? 'bg-[var(--color-leather)] text-[var(--color-parchment)] shadow-sm'
              : 'text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
          >
            <span>📚 全书总细纲</span>
            <span
              class="text-[10px] px-1.5 py-0.2 rounded-full"
              :class="activeTab === 'full'
                ? 'bg-amber-100/20 text-amber-200'
                : 'bg-emerald-100 text-emerald-800'"
            >
              {{ state.outlineText.value ? state.outlineText.value.length + ' 字' : '0' }}
            </span>
          </button>
        </div>

        <div class="flex items-center gap-2">
          <button
            @click="showBatchControls = !showBatchControls"
            type="button"
            class="text-xs px-2.5 py-1 rounded border border-[var(--color-parchment-darker)] hover:bg-[var(--color-parchment)] text-[var(--color-ink-light)] flex items-center gap-1"
          >
            <span>{{ showBatchControls ? '▲ 收起生成器' : '▼ 展开批量生成设置' }}</span>
          </button>
        </div>
      </div>

      <!-- 批量生成与模式控制折叠面板 -->
      <div v-if="showBatchControls" class="p-3 bg-[var(--color-parchment)] rounded-lg border border-[var(--color-parchment-darker)] space-y-3">
        <div class="flex items-center gap-2">
          <span class="text-xs font-medium text-[var(--color-ink)]">细纲模式：</span>
          <button @click="state.outlineMode.value = 'concise'"
            class="px-2.5 py-1 rounded text-xs transition-colors"
            :class="state.outlineMode.value === 'concise'
              ? 'bg-[var(--color-leather)] text-[var(--color-parchment)]'
              : 'bg-white border border-[var(--color-parchment-darker)] text-[var(--color-ink-light)] hover:bg-[var(--color-parchment)]'"
            type="button">精简（1000-2000字/章）</button>
          <button @click="state.outlineMode.value = 'detailed'"
            class="px-2.5 py-1 rounded text-xs transition-colors"
            :class="state.outlineMode.value === 'detailed'
              ? 'bg-[var(--color-leather)] text-[var(--color-parchment)]'
              : 'bg-white border border-[var(--color-parchment-darker)] text-[var(--color-ink-light)] hover:bg-[var(--color-parchment)]'"
            type="button">详细（3000-5000字/章）</button>
          <span class="text-xs text-[var(--color-ink-light)] italic ml-2">
            {{ state.outlineMode.value === 'detailed' ? '适合高张力、官能与心理细节规划' : '骨架式细纲，事件与行为要点' }}
          </span>
        </div>

        <div class="flex flex-wrap gap-3 items-end pt-1">
          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">起始章节</label>
            <input v-model.number="state.outlineBatchStart.value" type="number" min="1"
              class="w-20 bg-white border border-[var(--color-parchment-darker)] rounded-md px-2.5 py-1 text-sm" />
          </div>
          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">每批章数</label>
            <input v-model.number="state.outlineBatchSize.value" type="number" min="1" max="10"
              class="w-20 bg-white border border-[var(--color-parchment-darker)] rounded-md px-2.5 py-1 text-sm" />
          </div>
          <div class="flex-1 text-xs text-[var(--color-ink-light)] self-center">
            目标范围：第 {{ state.outlineBatchStart.value }} - {{ Math.min(state.outlineBatchStart.value + state.outlineBatchSize.value - 1, state.numChapters.value) }} 章
            （全书共 {{ state.numChapters.value }} 章）
          </div>
          <button
            @click="state.doGenerateOutlineBatch()"
            :disabled="state.detailedOutline.value.running || !state.llmConfig.value || state.outlineBatchStart.value > state.numChapters.value"
            class="btn-primary text-xs"
            type="button"
          >
            {{ state.detailedOutline.value.running ? '生成中…' : `▶ 生成第${state.outlineBatchStart.value}-${Math.min(state.outlineBatchStart.value + state.outlineBatchSize.value - 1, state.numChapters.value)}章细纲` }}
          </button>
        </div>
      </div>

      <!-- ── TAB 1: 当前选中章节细纲 ────────────────────────────────────── -->
      <div v-show="activeTab === 'chapter'" class="space-y-3">
        <!-- 章节细纲头部信息栏 -->
        <div class="flex items-center justify-between text-xs px-3 py-2 rounded-lg"
          :class="state.outlineBatchResult.value ? 'bg-amber-50/80 border border-amber-200 text-amber-900' : 'bg-stone-50 border border-stone-200 text-stone-600'">
          <div class="flex items-center gap-2">
            <span class="text-base">{{ state.outlineBatchResult.value ? '📝' : 'ℹ️' }}</span>
            <div>
              <span class="font-bold">第 {{ state.chapterNum.value }} 章分场细纲</span>
              <span v-if="state.outlineBatchResult.value" class="ml-2 font-mono text-amber-800">
                ({{ state.outlineBatchResult.value.length }} 字 · 本地已同步)
              </span>
              <span v-else class="ml-2 text-stone-500 italic">
                (当前章节暂无细纲内容，可直接在下方编辑或由 AI 生成)
              </span>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button
              v-if="state.outlineBatchResult.value"
              @click="state.saveBatchOutline()"
              class="px-2.5 py-1 bg-white border border-amber-300 rounded shadow-sm text-xs font-medium hover:bg-amber-100 text-amber-900 flex items-center gap-1"
              type="button"
            >
              <span>💾 保存本章细纲修改</span>
            </button>
            <button
              @click="state.extractChapterToEdit(state.chapterNum.value)"
              class="px-2.5 py-1 bg-white border border-stone-300 rounded shadow-sm text-xs text-stone-700 hover:bg-stone-100"
              title="从全书细纲中重新提取本章"
              type="button"
            >
              🔄 重新提取
            </button>
          </div>
        </div>

        <!-- 运行状态条 -->
        <div v-if="state.detailedOutline.value.running"
          class="text-xs px-3 py-1 flex items-center gap-2 bg-[var(--color-leather)] text-[var(--color-gold-light)] rounded-lg">
          <span class="inline-block w-2 h-2 rounded-full bg-[var(--color-gold)] animate-pulse" />
          <span class="italic flex-1">{{ state.detailedOutline.value.progress || '正在生成细纲...' }}</span>
          <button @click="state.cancelSSE(state.detailedOutline.value)"
            class="ml-2 px-2 py-0.5 rounded text-xs font-semibold bg-red-600 text-white hover:bg-red-700" type="button">停止</button>
        </div>

        <!-- 编辑区 -->
        <div class="relative rounded-lg border border-[var(--color-parchment-darker)] bg-white shadow-inner">
          <textarea
            v-model="state.outlineBatchResult.value"
            rows="15"
            :disabled="state.detailedOutline.value.running"
            class="w-full border-0 rounded-lg px-4 py-3 text-sm font-mono leading-relaxed resize-y disabled:opacity-60 focus:ring-1 focus:ring-[var(--color-leather)]"
            style="min-height: 260px"
            :placeholder="`第 ${state.chapterNum.value} 章本地暂无细纲。你可以展开上方【批量生成设置】点击【生成细纲】，或在此直接手动输入场景安排…\n\n标准格式参考：\n【第${state.chapterNum.value}章细纲】章节标题\n场景分解：\n  场景1（地点/人物）：起承转合…\n  场景2（地点/人物）：冲突升级…`"
          />
          <p v-if="state.detailedOutline.value.error" class="px-3 pb-2 text-xs text-red-500">{{ state.detailedOutline.value.error }}</p>
        </div>

        <!-- 修订面板 -->
        <details v-if="state.outlineBatchResult.value && !state.detailedOutline.value.running" class="border border-dashed border-[var(--color-parchment-darker)] rounded-lg bg-[var(--color-parchment)]/30">
          <summary class="px-3 py-2 cursor-pointer text-xs font-medium text-[var(--color-leather)] select-none">✏️ 基于建议对本章细纲进行 AI 修订</summary>
          <div class="px-3 pb-3 pt-1 space-y-2">
            <div class="flex flex-wrap gap-x-3 gap-y-1 text-xs text-[var(--color-ink-light)]">
              <span>注入上下文：</span>
              <label class="inline-flex items-center gap-1 cursor-pointer"><input type="checkbox" v-model="state.revisionContext.value.include_core_seed" class="rounded" />种子</label>
              <label class="inline-flex items-center gap-1 cursor-pointer"><input type="checkbox" v-model="state.revisionContext.value.include_characters" class="rounded" />角色</label>
              <label class="inline-flex items-center gap-1 cursor-pointer"><input type="checkbox" v-model="state.revisionContext.value.include_world_building" class="rounded" />世界观</label>
              <label class="inline-flex items-center gap-1 cursor-pointer"><input type="checkbox" v-model="state.revisionContext.value.include_plot" class="rounded" />剧情</label>
            </div>
            <input v-model="state.outlineRevisionGuidance.value" placeholder="输入修改建议，如：增加艾拉与亚历山大的眼神博弈、强化场景3的退路封死绝望感…"
              class="w-full bg-white border border-[var(--color-parchment-darker)] rounded px-2.5 py-1.5 text-sm" />
            <div class="flex items-center gap-2">
              <button @click="state.doReviseOutlineBatch()"
                :disabled="state.outlineRevision.value.running || !state.outlineRevisionGuidance.value || !state.llmConfig.value"
                class="btn-sm" type="button">
                {{ state.outlineRevision.value.running ? '修订中…' : '▶ 执行修订' }}
              </button>
              <button v-if="state.outlineBatchBackup.value && !state.outlineRevision.value.running"
                @click="state.revertOutlineBatch()"
                class="btn-sm" type="button"
                title="回退到修订前的版本">
                ↩ 回退原版
              </button>
              <span v-if="state.outlineRevision.value.progress" class="text-xs text-[var(--color-ink-light)] italic">{{ state.outlineRevision.value.progress }}</span>
              <span v-if="state.outlineRevision.value.error" class="text-xs text-red-500">{{ state.outlineRevision.value.error }}</span>
            </div>
          </div>
        </details>
      </div>

      <!-- ── TAB 2: 全书总细纲存储库 ───────────────────────────────────── -->
      <div v-show="activeTab === 'full'" class="space-y-3">
        <div class="p-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center justify-between text-xs text-emerald-900">
          <div class="flex items-center gap-2">
            <span class="text-base">📚</span>
            <div>
              <span class="font-bold">全书总细纲库 (Novel_detailed_outline.txt)</span>
              <span class="text-emerald-700 ml-1">· 共 {{ state.outlineText.value ? state.outlineText.value.length : 0 }} 字</span>
              <p class="text-[11px] text-emerald-600 mt-0.5">所有已保存章节的场景细纲都会按顺序沉淀在此。正文写作时会自动从中读取对应章节。</p>
            </div>
          </div>
          <button @click="state.saveOutline()" :disabled="!state.outlineText.value"
            class="px-3 py-1 bg-emerald-700 text-white rounded text-xs font-semibold hover:bg-emerald-800 shadow-sm" type="button">
            💾 保存全书细纲
          </button>
        </div>

        <div class="relative rounded-lg border border-[var(--color-parchment-darker)] bg-white shadow-inner">
          <textarea
            v-model="state.outlineText.value"
            rows="20"
            class="w-full border-0 rounded-lg px-4 py-3 text-sm font-mono leading-relaxed resize-y focus:ring-1 focus:ring-[var(--color-leather)]"
            style="min-height: 380px"
            placeholder="全书细纲集合，格式：【第1章细纲】标题\n场景分解：\n  场景1…"
          />
        </div>
      </div>
    </div>
  </StepCard>
</template>
