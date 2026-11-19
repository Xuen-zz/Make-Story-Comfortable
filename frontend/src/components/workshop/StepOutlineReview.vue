<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'
import type { DashboardChapterItem, DashboardPayload } from '@/components/workshop/WorkflowStepper.vue'

const props = defineProps<{
  state: ReturnType<typeof useWorkshopState>
  chapters: DashboardChapterItem[]
  dashboard: DashboardPayload | null
}>()

const emit = defineEmits<{
  (e: 'proceed-to-batch', start: number, end: number): void
  (e: 'refresh'): void
}>()

const showInputsDrawer = ref(false)
const showRawTextModal = ref(false)
const editingDrafts = ref<Record<number, string>>({})
const confirmedMap = ref<Record<number, boolean>>({})

const totalCh = computed(() => Math.max(10, props.state.numChapters.value || 200))
const batchStart = computed({
  get: () => props.state.outlineBatchStart.value,
  set: (v: number) => {
    props.state.outlineBatchStart.value = Math.max(1, Math.min(totalCh.value, v || 1))
  },
})
const batchSize = computed({
  get: () => props.state.outlineBatchSize.value,
  set: (v: number) => {
    props.state.outlineBatchSize.value = Math.max(1, Math.min(20, v || 10))
  },
})
const batchEnd = computed(() => Math.min(totalCh.value, batchStart.value + batchSize.value - 1))

// 生成滚动 10 章窗格切片（如 1-10, 11-20...）
const batchWindows = computed(() => {
  const size = batchSize.value || 10
  const list: { start: number; end: number; plannedCount: number; writtenCount: number }[] = []
  const chapterMap = new Map<number, DashboardChapterItem>()
  for (const c of props.chapters) chapterMap.set(c.num, c)

  for (let s = 1; s <= totalCh.value; s += size) {
    const e = Math.min(totalCh.value, s + size - 1)
    let plannedCount = 0
    let writtenCount = 0
    for (let ch = s; ch <= e; ch++) {
      const info = chapterMap.get(ch)
      if (info?.has_outline) plannedCount++
      if (info?.has_final || info?.has_draft) writtenCount++
    }
    list.push({ start: s, end: e, plannedCount, writtenCount })
  }
  return list
})

function parseOutlineBlocks(text: string): Record<number, string> {
  const map: Record<number, string> = {}
  if (!text) return map
  const re = /(【第\s*(\d+)\s*章细纲】[\s\S]*?)(?=【第\s*\d+\s*章细纲】|$)/g
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    const num = parseInt(m[2], 10)
    if (!Number.isNaN(num)) {
      map[num] = m[1].trim()
    }
  }
  return map
}

// 合并磁盘细纲与流式新生成结果
const parsedOutlineMap = computed(() => {
  const base = parseOutlineBlocks(props.state.outlineText.value || '')
  const live = parseOutlineBlocks(props.state.outlineBatchResult.value || '')
  return { ...base, ...live }
})

function syncEditingDrafts() {
  const next: Record<number, string> = {}
  for (let ch = batchStart.value; ch <= batchEnd.value; ch++) {
    next[ch] = parsedOutlineMap.value[ch] || ''
  }
  editingDrafts.value = next
}

watch(
  [batchStart, batchEnd, () => props.state.outlineText.value, () => props.state.outlineBatchResult.value],
  () => {
    syncEditingDrafts()
  },
  { immediate: true },
)

onMounted(() => {
  if (!props.state.outlineText.value) {
    props.state.loadOutlineText()
  }
})

const chapterTitleMap = computed(() => {
  const map: Record<number, string> = {}
  for (const c of props.chapters) {
    map[c.num] = c.title || `第 ${c.num} 章`
  }
  return map
})

const batchItems = computed(() => {
  const items: { num: number; title: string; outline: string; hasOutline: boolean; written: boolean }[] = []
  for (let ch = batchStart.value; ch <= batchEnd.value; ch++) {
    const cInfo = props.chapters.find(x => x.num === ch)
    const text = editingDrafts.value[ch] || ''
    items.push({
      num: ch,
      title: chapterTitleMap.value[ch] || `第 ${ch} 章`,
      outline: text,
      hasOutline: Boolean(text.trim()),
      written: Boolean(cInfo?.has_final || cInfo?.has_draft),
    })
  }
  return items
})

const readyCountInBatch = computed(() => batchItems.value.filter(i => i.hasOutline).length)

const inputDeps = computed(() => {
  const a = props.dashboard?.assets || {}
  return [
    {
      label: '小说核心架构',
      ok: Boolean(a.architecture?.exists || props.state.arch.value.result),
      chars: a.architecture?.chars || 0,
    },
    {
      label: '全书章节目录',
      ok: Boolean(a.blueprint?.exists || props.state.bp.value.result),
      chars: a.blueprint?.chars || 0,
      extra: a.blueprint?.total_chapters ? `共 ${a.blueprint.total_chapters} 章` : '',
    },
    {
      label: '全局前文记忆',
      ok: Boolean(a.global_summary?.exists),
      chars: a.global_summary?.chars || 0,
    },
    {
      label: '角色能力状态表',
      ok: Boolean(a.character_state?.exists),
      chars: a.character_state?.chars || 0,
    },
  ]
})

async function handleSaveSingle(ch: number) {
  await props.state.saveSingleChapterOutline(ch, editingDrafts.value[ch] || '')
  confirmedMap.value[ch] = true
  emit('refresh')
}

async function handleSaveWholeBatch() {
  if (props.state.outlineBatchResult.value) {
    await props.state.saveBatchOutline()
  }
  // 同步当前批次里被单独编辑过的章节
  for (let ch = batchStart.value; ch <= batchEnd.value; ch++) {
    const txt = (editingDrafts.value[ch] || '').trim()
    if (txt && txt !== (parsedOutlineMap.value[ch] || '').trim()) {
      await props.state.saveSingleChapterOutline(ch, txt)
    }
  }
  emit('refresh')
}

function selectWindow(s: number) {
  batchStart.value = s
}
</script>

<template>
  <div class="space-y-4">
    <!-- 工单顶卡：第 3 步说明 + 滚动批次选择 -->
    <div class="rounded-2xl border border-[var(--color-parchment-darker)] bg-white p-4 shadow-xs space-y-3.5">
      <div class="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h3 class="text-base font-bold text-[var(--color-ink)]">
            📑 第 3 步：分批细纲生成与审核（滚动 {{ batchSize }} 章 / 批）
          </h3>
          <p class="text-xs text-[var(--color-ink-light)] mt-0.5">
            每次只推进未来 {{ batchSize }} 章的精细大纲（避免提前写死 200 章导致后面吃书），审核修改满意后，一键送入第 4 步批量写审。
          </p>
        </div>

        <div class="flex items-center gap-2 flex-wrap">
          <button
            @click="showRawTextModal = !showRawTextModal"
            type="button"
            class="px-3 py-1.5 rounded-lg border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/50 hover:bg-[var(--color-parchment)] text-xs font-medium cursor-pointer"
          >
            {{ showRawTextModal ? '关闭全书细纲全文' : '📄 查看/编辑细纲原文' }}
          </button>
          <button
            @click="emit('proceed-to-batch', batchStart, batchEnd)"
            type="button"
            class="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs sm:text-sm font-bold shadow-xs cursor-pointer transition-colors"
          >
            ✅ 细纲已审核，批量写第 {{ batchStart }}-{{ batchEnd }} 章 ➔
          </button>
        </div>
      </div>

      <!-- 滚动批次窗口快速切换条 -->
      <div class="flex items-center gap-1.5 flex-wrap pt-1">
        <span class="text-xs font-semibold text-zinc-200 mr-1">批次窗口：</span>
        <button
          v-for="win in batchWindows.slice(0, 20)"
          :key="win.start"
          @click="selectWindow(win.start)"
          type="button"
          class="px-2.5 py-1 rounded-lg text-xs font-medium border transition-all cursor-pointer flex items-center gap-1"
          :class="
            batchStart === win.start
              ? 'bg-[var(--color-leather)] text-white border-[var(--color-leather)] shadow-xs'
              : win.plannedCount === (win.end - win.start + 1)
                ? 'bg-emerald-50 text-emerald-800 border-emerald-200 hover:border-emerald-400'
                : win.plannedCount > 0
                  ? 'bg-amber-50 text-amber-900 border-amber-200 hover:border-amber-400'
                  : 'bg-[var(--color-parchment)]/40 text-[var(--color-ink-light)] border-[var(--color-parchment-darker)] hover:bg-[var(--color-parchment)]'
          "
        >
          <span>{{ win.start }}-{{ win.end }}</span>
          <span v-if="win.writtenCount > 0" class="text-[10px] opacity-80">✓</span>
          <span v-else-if="win.plannedCount > 0" class="text-[10px] opacity-80">({{ win.plannedCount }})</span>
        </button>
      </div>

      <!-- 生成控制条 -->
      <div class="rounded-xl border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/45 p-3 flex items-center justify-between flex-wrap gap-3">
        <div class="flex items-center gap-3 flex-wrap text-xs">
          <label class="flex items-center gap-1.5">
            <span class="font-medium text-[var(--color-ink-light)]">起始章</span>
            <input
              v-model.number="batchStart"
              type="number"
              min="1"
              :max="totalCh"
              class="w-16 px-2 py-1 rounded-lg border border-[var(--color-parchment-darker)] bg-white text-center font-mono"
            />
          </label>
          <label class="flex items-center gap-1.5">
            <span class="font-medium text-[var(--color-ink-light)]">每批章数</span>
            <input
              v-model.number="batchSize"
              type="number"
              min="1"
              max="20"
              class="w-14 px-2 py-1 rounded-lg border border-[var(--color-parchment-darker)] bg-white text-center font-mono"
            />
          </label>
          <div class="inline-flex rounded-lg border border-[var(--color-parchment-darker)] bg-white p-0.5">
            <button
              @click="state.outlineMode.value = 'concise'"
              type="button"
              class="px-2.5 py-1 rounded-md text-[11px] font-medium cursor-pointer"
              :class="state.outlineMode.value === 'concise' ? 'bg-[var(--color-leather)] text-white' : 'text-[var(--color-ink-light)]'"
            >
              ⚡ 简纲（推荐）
            </button>
            <button
              @click="state.outlineMode.value = 'detailed'"
              type="button"
              class="px-2.5 py-1 rounded-md text-[11px] font-medium cursor-pointer"
              :class="state.outlineMode.value === 'detailed' ? 'bg-[var(--color-leather)] text-white' : 'text-[var(--color-ink-light)]'"
            >
              🔍 分场精纲
            </button>
          </div>
          <button
            @click="showInputsDrawer = !showInputsDrawer"
            type="button"
            class="px-2.5 py-1 rounded-lg border border-[var(--color-parchment-darker)] bg-white hover:bg-amber-50 text-[11px] font-medium cursor-pointer"
          >
            📥 输入依赖检查 ({{ inputDeps.filter(d => d.ok).length }}/4) {{ showInputsDrawer ? '▴' : '▾' }}
          </button>
        </div>

        <div class="flex items-center gap-2">
          <button
            v-if="!state.detailedOutline.value.running"
            @click="state.doGenerateOutlineBatch()"
            type="button"
            class="btn-primary text-xs sm:text-sm"
          >
            ▶ 生成第 {{ batchStart }}-{{ batchEnd }} 章细纲
          </button>
          <button
            v-else
            @click="state.cancelSSE(state.detailedOutline.value)"
            type="button"
            class="px-3.5 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold cursor-pointer"
          >
            ⏹️ 停止生成
          </button>
          <button
            v-if="readyCountInBatch > 0"
            @click="handleSaveWholeBatch"
            type="button"
            class="px-3 py-2 rounded-lg border border-[var(--color-leather)] text-zinc-200 hover:bg-white text-xs font-semibold cursor-pointer"
          >
            💾 保存本批改动
          </button>
        </div>
      </div>

      <!-- 透明化：输入依赖检查折叠抽屉 -->
      <div
        v-if="showInputsDrawer"
        class="rounded-xl border border-amber-200 bg-amber-50/50 p-3 text-xs space-y-2"
      >
        <div class="font-bold text-amber-950">📥 生成细纲时将自动挂载以下上游设定（透明可见）：</div>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          <div
            v-for="dep in inputDeps"
            :key="dep.label"
            class="rounded-lg bg-white border border-amber-200/80 px-3 py-2 flex items-center justify-between"
          >
            <div>
              <div class="font-semibold text-[var(--color-ink)]">{{ dep.label }}</div>
              <div class="text-[11px] text-[var(--color-ink-light)]">
                {{ dep.extra || (dep.chars > 0 ? `${dep.chars} 字` : '暂无记录') }}
              </div>
            </div>
            <span class="text-xs font-bold" :class="dep.ok ? 'text-emerald-600' : 'text-amber-600'">
              {{ dep.ok ? '✓ 已备' : '待补' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 生成进度提示 -->
      <div
        v-if="state.detailedOutline.value.running || state.detailedOutline.value.progress"
        class="px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-center gap-2"
      >
        <span v-if="state.detailedOutline.value.running" class="w-2 h-2 rounded-full bg-amber-600 animate-ping" />
        <span>{{ state.detailedOutline.value.progress || '正在推演细纲...' }}</span>
      </div>
      <div
        v-if="state.detailedOutline.value.error"
        class="px-3 py-2 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800"
      >
        ❌ {{ state.detailedOutline.value.error }}
      </div>
    </div>

    <!-- 全书细纲全文快速抽屉（可选查看） -->
    <div
      v-if="showRawTextModal"
      class="rounded-2xl border border-[var(--color-parchment-darker)] bg-white p-4 shadow-xs space-y-2.5"
    >
      <div class="flex items-center justify-between">
        <span class="text-sm font-bold text-[var(--color-ink)]">📄 Novel_detailed_outline.txt 全文编辑</span>
        <div class="flex items-center gap-2">
          <button @click="state.saveOutline()" type="button" class="btn-primary text-xs">💾 保存全文</button>
          <button @click="showRawTextModal = false" type="button" class="text-xs text-[var(--color-ink-light)] hover:underline cursor-pointer">收起</button>
        </div>
      </div>
      <textarea
        v-model="state.outlineText.value"
        rows="12"
        class="w-full rounded-xl border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/25 p-3 text-xs font-mono leading-relaxed"
      />
    </div>

    <!-- 本批 AI 一键微调工具条 -->
    <div
      v-if="readyCountInBatch > 0"
      class="rounded-2xl border border-[var(--color-parchment-darker)] bg-white px-4 py-3 flex items-center gap-2.5 flex-wrap"
    >
      <span class="text-xs font-bold text-zinc-200 whitespace-nowrap">✨ AI 批量微调本批：</span>
      <input
        v-model="state.outlineRevisionGuidance.value"
        type="text"
        placeholder="例如：第3章冲突再激烈一点，第5章结尾加个悬念反转钩子..."
        class="flex-1 min-w-[220px] px-3 py-1.5 rounded-lg border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/25 text-xs"
      />
      <button
        @click="state.doReviseOutlineBatch()"
        :disabled="state.outlineRevision.value.running || !state.outlineRevisionGuidance.value.trim()"
        type="button"
        class="px-3.5 py-1.5 rounded-lg bg-[var(--color-leather)] hover:bg-[var(--color-leather-light)] text-white text-xs font-semibold disabled:opacity-50 cursor-pointer"
      >
        {{ state.outlineRevision.value.running ? '⏳ 微调中…' : '执行微调' }}
      </button>
    </div>

    <!-- 逐章细纲工单审核卡片列表 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-3.5">
      <div
        v-for="item in batchItems"
        :key="item.num"
        class="rounded-2xl border bg-white p-3.5 shadow-2xs flex flex-col gap-2.5 transition-colors"
        :class="
          confirmedMap[item.num]
            ? 'border-emerald-300 ring-1 ring-emerald-200/70'
            : item.hasOutline
              ? 'border-[var(--color-parchment-darker)]'
              : 'border-dashed border-stone-300 bg-[var(--color-parchment)]/25'
        "
      >
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2 min-w-0">
            <span class="px-2 py-0.5 rounded-md bg-[var(--color-parchment-dark)] text-[var(--color-ink)] font-mono text-xs font-bold shrink-0">
              第 {{ item.num }} 章
            </span>
            <span class="text-sm font-bold text-[var(--color-ink)] truncate">{{ item.title }}</span>
          </div>

          <div class="flex items-center gap-1.5 shrink-0">
            <span
              v-if="item.written"
              class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-semibold"
            >
              已写正文
            </span>
            <span
              v-else-if="item.hasOutline"
              class="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-semibold"
            >
              细纲就绪
            </span>
            <span
              v-else
              class="text-[10px] px-2 py-0.5 rounded-full bg-stone-200 text-stone-600"
            >
              待生成
            </span>
          </div>
        </div>

        <textarea
          v-model="editingDrafts[item.num]"
          rows="6"
          :placeholder="`第 ${item.num} 章细纲尚未生成，点击上方「▶ 生成第 ${batchStart}-${batchEnd} 章细纲」后将自动填充，您也可直接手写…`"
          class="w-full rounded-xl border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/20 p-2.5 text-xs text-[var(--color-ink)] leading-relaxed focus:outline-none focus:border-[var(--color-leather)]"
        />

        <div class="flex items-center justify-between text-[11px]">
          <span class="text-[var(--color-ink-light)]">
            {{ (editingDrafts[item.num] || '').length }} 字
          </span>
          <div class="flex items-center gap-2">
            <label class="flex items-center gap-1 cursor-pointer select-none text-[var(--color-ink-light)]">
              <input v-model="confirmedMap[item.num]" type="checkbox" class="rounded accent-emerald-600" />
              <span>已人工确认</span>
            </label>
            <button
              @click="handleSaveSingle(item.num)"
              :disabled="!(editingDrafts[item.num] || '').trim()"
              type="button"
              class="px-2.5 py-1 rounded-lg bg-[var(--color-parchment)] hover:bg-[var(--color-parchment-dark)] border border-[var(--color-parchment-darker)] text-[var(--color-ink)] font-medium disabled:opacity-40 cursor-pointer"
            >
              💾 保存本章
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部放行通往第 4 步 CTA -->
    <div class="rounded-2xl border border-emerald-300 bg-emerald-50/70 p-4 flex items-center justify-between flex-wrap gap-3">
      <div class="text-xs sm:text-sm text-emerald-950">
        <span class="font-bold">本批准备就绪度：{{ readyCountInBatch }} / {{ batchItems.length }} 章</span>
        <span class="text-emerald-800/80 ml-2">进入第 4 步后，流水线将按顺序逐章完成「3.8 Flash 起草 ➔ 4 Hydrogen 去AI审校 ➔ 记忆归档」。</span>
      </div>
      <button
        @click="emit('proceed-to-batch', batchStart, batchEnd)"
        type="button"
        class="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold shadow-sm cursor-pointer transition-colors"
      >
        🚀 进入批量写审（第 {{ batchStart }}-{{ batchEnd }} 章）➔
      </button>
    </div>
  </div>
</template>
