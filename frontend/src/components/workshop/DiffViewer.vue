<script setup lang="ts">
import { ref, computed } from 'vue'
import { diffLines, diffChars } from 'diff'

const props = withDefaults(defineProps<{
  oldText: string
  newText: string
  checklist?: string
  loading?: boolean
  oldLabel?: string
  newLabel?: string
}>(), {
  checklist: '',
  loading: false,
  oldLabel: '📝 3.8 Flash 原初稿',
  newLabel: '🛡️ 4 Hydrogen 审校定稿',
})

const showChangedOnly = ref(false)
const showChecklist = ref(true)

interface DiffSeg {
  text: string
  kind: 'same' | 'removed' | 'added'
}

interface AlignedRow {
  idx: number
  oldPara: string
  newPara: string
  type: 'equal' | 'modified' | 'added' | 'removed'
  oldSegs: DiffSeg[]
  newSegs: DiffSeg[]
}

function splitParas(text: string): string[] {
  if (!text) return []
  return text.split(/\n+/).map(p => p.trim()).filter(Boolean)
}

function buildCharSegs(oldStr: string, newStr: string): { oldSegs: DiffSeg[]; newSegs: DiffSeg[] } {
  const parts = diffChars(oldStr, newStr)
  const oldSegs: DiffSeg[] = []
  const newSegs: DiffSeg[] = []
  for (const part of parts) {
    if (part.removed) {
      oldSegs.push({ text: part.value, kind: 'removed' })
    } else if (part.added) {
      newSegs.push({ text: part.value, kind: 'added' })
    } else {
      oldSegs.push({ text: part.value, kind: 'same' })
      newSegs.push({ text: part.value, kind: 'same' })
    }
  }
  return { oldSegs, newSegs }
}

const alignedRows = computed<AlignedRow[]>(() => {
  const oldText = (props.oldText || '').trim()
  const newText = (props.newText || '').trim()
  if (!oldText && !newText) return []

  const lineDiffs = diffLines(oldText, newText)
  const rows: AlignedRow[] = []
  let i = 0
  let rowNo = 1

  while (i < lineDiffs.length) {
    const d = lineDiffs[i]
    if (!d.added && !d.removed) {
      for (const p of splitParas(d.value)) {
        rows.push({
          idx: rowNo++,
          oldPara: p,
          newPara: p,
          type: 'equal',
          oldSegs: [{ text: p, kind: 'same' }],
          newSegs: [{ text: p, kind: 'same' }],
        })
      }
      i++
    } else if (d.removed && i + 1 < lineDiffs.length && lineDiffs[i + 1].added) {
      const remParas = splitParas(d.value)
      const addParas = splitParas(lineDiffs[i + 1].value)
      const maxLen = Math.max(remParas.length, addParas.length)
      for (let j = 0; j < maxLen; j++) {
        const op = remParas[j] || ''
        const np = addParas[j] || ''
        if (op && np) {
          const { oldSegs, newSegs } = buildCharSegs(op, np)
          rows.push({ idx: rowNo++, oldPara: op, newPara: np, type: 'modified', oldSegs, newSegs })
        } else if (op) {
          rows.push({ idx: rowNo++, oldPara: op, newPara: '', type: 'removed', oldSegs: [{ text: op, kind: 'removed' }], newSegs: [] })
        } else if (np) {
          rows.push({ idx: rowNo++, oldPara: '', newPara: np, type: 'added', oldSegs: [], newSegs: [{ text: np, kind: 'added' }] })
        }
      }
      i += 2
    } else if (d.removed) {
      for (const p of splitParas(d.value)) {
        rows.push({ idx: rowNo++, oldPara: p, newPara: '', type: 'removed', oldSegs: [{ text: p, kind: 'removed' }], newSegs: [] })
      }
      i++
    } else if (d.added) {
      for (const p of splitParas(d.value)) {
        rows.push({ idx: rowNo++, oldPara: '', newPara: p, type: 'added', oldSegs: [], newSegs: [{ text: p, kind: 'added' }] })
      }
      i++
    } else {
      i++
    }
  }
  return rows
})

const stats = computed(() => {
  let modified = 0
  let added = 0
  let removed = 0
  for (const r of alignedRows.value) {
    if (r.type === 'modified') modified++
    else if (r.type === 'added') added++
    else if (r.type === 'removed') removed++
  }
  const oldChars = (props.oldText || '').trim().length
  const newChars = (props.newText || '').trim().length
  return {
    total: alignedRows.value.length,
    changed: modified + added + removed,
    modified,
    added,
    removed,
    oldChars,
    newChars,
    delta: newChars - oldChars,
  }
})

const displayedRows = computed(() =>
  showChangedOnly.value
    ? alignedRows.value.filter(r => r.type !== 'equal')
    : alignedRows.value,
)
</script>

<template>
  <div class="space-y-3">
    <!-- AI 修改清单卡片 -->
    <div
      v-if="checklist && checklist.trim()"
      class="rounded-xl border border-emerald-200 bg-emerald-50/60 p-3.5"
    >
      <div class="flex items-center justify-between gap-2 mb-1.5">
        <span class="text-xs font-bold text-emerald-900">📋 4 Hydrogen 审校与去AI修改清单</span>
        <button
          @click="showChecklist = !showChecklist"
          type="button"
          class="text-[11px] text-emerald-700 hover:underline cursor-pointer"
        >
          {{ showChecklist ? '收起' : '展开' }}
        </button>
      </div>
      <div
        v-if="showChecklist"
        class="text-xs text-emerald-950/90 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto bg-white/80 rounded-lg p-2.5 border border-emerald-100"
      >
        {{ checklist }}
      </div>
    </div>

    <!-- 空状态 -->
    <div
      v-if="loading"
      class="py-12 text-center text-xs text-[var(--color-ink-light)] rounded-xl border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/40"
    >
      ⏳ 正在加载对比数据…
    </div>

    <div
      v-else-if="!oldText && !newText"
      class="py-12 text-center text-xs text-[var(--color-ink-light)] rounded-xl border border-dashed border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/30"
    >
      暂无初稿与定稿记录。点击上方「⚡ 单章运行」后，将在此生成逐句红绿对比。
    </div>

    <div
      v-else-if="oldText && !newText"
      class="p-4 rounded-xl border border-amber-200 bg-amber-50/70 text-xs text-amber-900"
    >
      当前仅存在「3.8 Flash 原初稿」（{{ oldText.length }} 字），尚未经过「4 Hydrogen 审校定稿」。
    </div>

    <template v-else>
      <!-- 统计与过滤工具栏 -->
      <div class="flex items-center justify-between flex-wrap gap-2 px-3.5 py-2.5 rounded-xl border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/60 text-xs">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="font-bold text-[var(--color-ink)]">⚖️ 初稿 vs 审校逐句对照</span>
          <span class="px-2 py-0.5 rounded-full bg-white border border-[var(--color-parchment-darker)] text-[11px] font-medium">
            变动 {{ stats.changed }} / {{ stats.total }} 段
          </span>
          <span class="px-2 py-0.5 rounded-full bg-rose-50 border border-rose-200 text-rose-800 text-[11px]">
            原稿 {{ stats.oldChars }} 字
          </span>
          <span class="px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-[11px]">
            定稿 {{ stats.newChars }} 字 ({{ stats.delta >= 0 ? `+${stats.delta}` : stats.delta }})
          </span>
        </div>

        <div class="flex items-center gap-1.5">
          <button
            @click="showChangedOnly = false"
            type="button"
            class="px-2.5 py-1 rounded-lg text-[11px] font-semibold cursor-pointer transition-colors"
            :class="!showChangedOnly
              ? 'bg-[var(--color-leather)] text-white'
              : 'bg-white text-[var(--color-ink-light)] border border-[var(--color-parchment-darker)]'"
          >
            全章对照 ({{ stats.total }})
          </button>
          <button
            @click="showChangedOnly = true"
            type="button"
            class="px-2.5 py-1 rounded-lg text-[11px] font-semibold cursor-pointer transition-colors"
            :class="showChangedOnly
              ? 'bg-[var(--color-leather)] text-white'
              : 'bg-white text-[var(--color-ink-light)] border border-[var(--color-parchment-darker)]'"
          >
            仅看改动段 ({{ stats.changed }})
          </button>
        </div>
      </div>

      <!-- 并排双栏头 -->
      <div class="rounded-xl border border-[var(--color-parchment-darker)] overflow-hidden bg-white">
        <div class="grid grid-cols-1 lg:grid-cols-2 border-b border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/70 text-[11px] font-bold">
          <div class="px-3.5 py-2 text-rose-900 border-b lg:border-b-0 lg:border-r border-[var(--color-parchment-darker)]">
            {{ oldLabel }}（红底删除线 = 被去AI/替换）
          </div>
          <div class="px-3.5 py-2 text-emerald-900">
            {{ newLabel }}（绿底高亮 = 审校修改/新增）
          </div>
        </div>

        <div v-if="displayedRows.length === 0" class="py-8 text-center text-xs text-[var(--color-ink-light)]">
          初稿与定稿内容完全一致，未发现文本改动。
        </div>

        <div v-else class="max-h-[600px] overflow-y-auto divide-y divide-[var(--color-parchment-dark)] font-novel-prose">
          <div
            v-for="row in displayedRows"
            :key="row.idx"
            class="grid grid-cols-1 lg:grid-cols-2 text-sm leading-relaxed"
            :class="
              row.type === 'equal'
                ? 'bg-[#131417]'
                : row.type === 'modified'
                  ? 'bg-[#191a20]'
                  : row.type === 'added'
                    ? 'bg-[#101c17]'
                    : 'bg-[#1d1415]'
            "
          >
            <!-- 左：初稿 -->
            <div class="px-4 py-2.5 border-b lg:border-b-0 lg:border-r border-[var(--color-parchment-dark)] break-words">
              <span v-if="!row.oldPara" class="text-[11px] italic text-zinc-500">（本段为审校新增）</span>
              <template v-else>
                <span class="inline-block mr-1.5 text-[10px] font-mono text-zinc-500 select-none">#{{ row.idx }}</span>
                <template v-for="(seg, si) in row.oldSegs" :key="si">
                  <span
                    v-if="seg.kind === 'removed'"
                    class="bg-red-950/75 text-red-200 line-through decoration-red-400/80 rounded px-0.5"
                  >{{ seg.text }}</span>
                  <span v-else class="text-[#d4d4d8]">{{ seg.text }}</span>
                </template>
              </template>
            </div>

            <!-- 右：审校定稿 -->
            <div class="px-4 py-2.5 break-words">
              <span v-if="!row.newPara" class="text-[11px] italic text-red-400/80">（本段已在审校中被精简删除）</span>
              <template v-else>
                <span class="inline-block mr-1.5 text-[10px] font-mono text-zinc-500 select-none">#{{ row.idx }}</span>
                <template v-for="(seg, si) in row.newSegs" :key="si">
                  <span
                    v-if="seg.kind === 'added'"
                    class="bg-emerald-950/75 text-emerald-200 font-medium underline decoration-emerald-400/70 decoration-2 underline-offset-2 rounded px-0.5"
                  >{{ seg.text }}</span>
                  <span v-else class="text-[#d4d4d8]">{{ seg.text }}</span>
                </template>
              </template>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
