<script setup lang="ts">
import { ref, computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useConfigStore } from '@/stores/config'
import { useWorkflowCanvas } from '@/composables/useWorkflowCanvas'

const props = defineProps<{
  id: string
  data: {
    nodeType: string
    label: string
    params: Record<string, any>
    bypass?: boolean
    collapsed?: boolean
  }
}>()

const wf = useWorkflowCanvas()
const configStore = useConfigStore()

const showPromptEditor = ref(false)
const showMiniPreview = ref(false)

const meta = computed(() => wf.nodeMetaMap.value[props.data.nodeType])
const runtime = computed(() => wf.nodeRuntime.value[props.id] || { status: 'idle', progress: 0 })
const params = computed(() => props.data.params || {})
const inputs = computed(() => meta.value?.inputs || [])
const outputs = computed(() => meta.value?.outputs || [])

function portColor(portType: string): string {
  return wf.portTypes.value[portType]?.color || '#94a3b8'
}

const headerAccent = computed(() => {
  const t = props.data.nodeType
  if (['idea_seed', 'arch_generator', 'directory_generator', 'batch_outline_gate'].includes(t)) {
    return 'border-t-blue-400'
  }
  if (['chapter_input', 'outline_loader', 'memory_assembler', 'style_prompt', 'llm_config'].includes(t)) {
    return 'border-t-zinc-400'
  }
  if (['character_profile', 'prev_excerpt_loader', 'rag_retriever', 'foreshadow_loader', 'forbidden_lock', 'note_primitive', 'context_combiner'].includes(t)) {
    return 'border-t-teal-500/80'
  }
  if (['pre_write_gate', 'draft_writer', 'script_audit', 'deai_reviewer', 'custom_rewrite', 'ending_hook_rewriter'].includes(t)) {
    return 'border-t-zinc-200'
  }
  return 'border-t-emerald-500'
})

const frameClass = computed(() => {
  if (props.data.bypass) {
    return 'border-zinc-700/80 border-dashed opacity-55 bg-[#121419]'
  }
  const st = runtime.value.status
  if (st === 'running') {
    return 'border-emerald-400 ring-2 ring-emerald-500/50 shadow-[0_0_22px_rgba(16,185,129,0.28)] bg-[#151b1a]'
  }
  if (st === 'waiting_gate') {
    return 'border-amber-400 ring-2 ring-amber-400/50 shadow-[0_0_20px_rgba(245,158,11,0.25)] bg-[#191815]'
  }
  if (st === 'error') {
    return 'border-red-500 ring-2 ring-red-500/40 bg-[#1c1416]'
  }
  if (st === 'completed') {
    return 'border-emerald-500/70 bg-[#15171c]'
  }
  if (st === 'cached') {
    return 'border-sky-500/60 border-dashed bg-[#13171d]'
  }
  return 'border-[#262932] hover:border-zinc-500 bg-[#15171c]'
})

const previewSnippet = computed(() => {
  const out = runtime.value.outputs
  if (!out) return ''
  const txt =
    out.polished_text
    || out.draft_text
    || out.text_out
    || out.approved_text
    || out.selected_text
    || out.final_text
    || out.arch_text
    || out.directory_text
    || out.checklist
    || out.outline
    || out.handoff
    || ''
  if (typeof txt === 'string' && txt.trim()) return txt.trim()
  if (out.context_bundle?.text) return String(out.context_bundle.text).trim()
  return ''
})

const previewChars = computed(() => previewSnippet.value.length)
const auditScore = computed(() => {
  const s = runtime.value.outputs?.score
  return typeof s === 'number' ? s : null
})

function setParam(key: string, val: unknown) {
  wf.updateNodeParam(props.id, key, val)
}

function resetPromptToDefault() {
  const t = props.data.nodeType
  if (t === 'deai_reviewer') {
    const strength = params.value.review_strength || 'strong'
    setParam(
      'custom_prompt_template',
      strength === 'light'
        ? wf.defaultPrompts.value.review_light
        : wf.defaultPrompts.value.review_strong,
    )
  } else if (t === 'custom_rewrite') {
    setParam('custom_prompt_template', wf.defaultPrompts.value.custom_rewrite)
  } else if (t === 'ending_hook_rewriter') {
    setParam('custom_prompt_template', wf.defaultPrompts.value.ending_hook)
  } else if (t === 'draft_writer') {
    setParam('custom_prompt_template', '')
  }
}

function onReviewStrengthChange(val: 'strong' | 'light') {
  setParam('review_strength', val)
  const cur = (params.value.custom_prompt_template || '').trim()
  if (
    !cur
    || cur === wf.defaultPrompts.value.review_strong?.trim()
    || cur === wf.defaultPrompts.value.review_light?.trim()
  ) {
    setParam(
      'custom_prompt_template',
      val === 'light' ? wf.defaultPrompts.value.review_light : wf.defaultPrompts.value.review_strong,
    )
  }
}

function canRunFromHere() {
  return !wf.isRunning.value && !props.data.bypass
}
</script>

<template>
  <div
    class="w-[300px] rounded-xl border border-t-[3px] text-zinc-200 shadow-xl transition-all duration-200 select-none"
    :class="[headerAccent, frameClass]"
  >
    <!-- 顶部标题栏 -->
    <div class="px-2.5 py-2 bg-[#1b1e25] rounded-t-lg border-b border-[#262932] flex items-center justify-between gap-1.5">
      <div class="flex items-center gap-1.5 min-w-0">
        <span
          class="w-2 h-2 rounded-full shrink-0"
          :class="{
            'bg-zinc-500': runtime.status === 'idle',
            'bg-emerald-400 animate-ping': runtime.status === 'running',
            'bg-emerald-500': runtime.status === 'completed',
            'bg-amber-400 animate-pulse': runtime.status === 'waiting_gate',
            'bg-sky-400': runtime.status === 'cached',
            'bg-red-500': runtime.status === 'error',
            'bg-zinc-600': data.bypass || runtime.status === 'bypassed',
          }"
        />
        <span class="text-xs font-bold text-zinc-100 truncate">{{ data.label }}</span>
      </div>

      <div class="flex items-center gap-1 nodrag shrink-0">
        <button
          @click.stop="wf.executeSingleChapter({ chapterNum: wf.canvasChapterNum.value, startFromNodeId: id })"
          :disabled="!canRunFromHere()"
          type="button"
          title="从此处重跑下游（复用前面已跑节点的缓存）"
          class="px-1.5 py-0.5 rounded bg-emerald-500/20 hover:bg-emerald-500/40 text-emerald-300 text-[10px] font-bold disabled:opacity-30 cursor-pointer"
        >
          ▶
        </button>
        <button
          @click.stop="wf.toggleNodeBypass(id)"
          type="button"
          title="Bypass 旁路跳过此节点"
          class="px-1.5 py-0.5 rounded text-[10px] font-bold cursor-pointer"
          :class="data.bypass ? 'bg-amber-500/25 text-amber-300' : 'bg-[#262932] hover:bg-[#323643] text-zinc-200'"
        >
          ⏭
        </button>
        <button
          @click.stop="wf.toggleNodeCollapsed(id)"
          type="button"
          title="折叠/展开参数"
          class="px-1 py-0.5 rounded bg-[#262932] hover:bg-[#323643] text-zinc-200 text-[10px] cursor-pointer"
        >
          {{ data.collapsed ? '▸' : '▾' }}
        </button>
        <button
          @click.stop="wf.deleteNode(id)"
          type="button"
          title="删除节点"
          class="px-1 py-0.5 rounded bg-red-500/15 hover:bg-red-500/35 text-red-300 text-[10px] cursor-pointer"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- 运行进度条 -->
    <div v-if="runtime.status === 'running' || runtime.status === 'waiting_gate'" class="px-2.5 pt-1.5">
      <div class="h-1.5 w-full rounded-full bg-[#0e1014] overflow-hidden">
        <div
          class="h-full transition-all duration-300"
          :class="runtime.status === 'waiting_gate' ? 'bg-amber-400' : 'bg-emerald-400'"
          :style="{ width: `${runtime.progress || 25}%` }"
        />
      </div>
      <div class="text-[10px] text-emerald-300 mt-0.5 truncate">{{ runtime.message || '执行中...' }}</div>
    </div>

    <!-- 输入 / 输出端口连线排布区 -->
    <div
      v-if="inputs.length || outputs.length"
      class="py-1.5 flex items-start justify-between gap-2 border-b border-[#22252e] text-[11px]"
    >
      <div class="flex flex-col gap-1.5 min-w-0">
        <div
          v-for="pin in inputs"
          :key="pin.id"
          class="relative flex items-center pl-3.5 pr-1 h-5"
        >
          <Handle
            :id="pin.id"
            type="target"
            :position="Position.Left"
            class="!w-3 !h-3 !border-2 !border-[#0e1014]"
            :style="{ backgroundColor: portColor(pin.type), left: '-6px' }"
          />
          <span class="truncate text-zinc-200">{{ pin.label }}</span>
        </div>
      </div>

      <div class="flex flex-col items-end gap-1.5 min-w-0 ml-auto">
        <div
          v-for="pin in outputs"
          :key="pin.id"
          class="relative flex items-center justify-end pr-3.5 pl-1 h-5"
        >
          <span class="truncate text-zinc-200 font-medium">{{ pin.label }}</span>
          <Handle
            :id="pin.id"
            type="source"
            :position="Position.Right"
            class="!w-3 !h-3 !border-2 !border-[#0e1014]"
            :style="{ backgroundColor: portColor(pin.type), right: '-6px' }"
          />
        </div>
      </div>
    </div>

    <!-- 中部可调参数区 -->
    <div v-if="!data.collapsed" class="p-2.5 space-y-2 text-[11px] nodrag nowheel">
      <!-- idea_seed -->
      <template v-if="data.nodeType === 'idea_seed'">
        <label class="block space-y-0.5">
          <span class="text-zinc-400">核心题材</span>
          <input
            :value="params.genre || ''"
            @input="setParam('genre', ($event.target as HTMLInputElement).value)"
            type="text"
            placeholder="东方玄幻 / 悬疑推理…"
            class="w-full px-2 py-1 rounded bg-[#0e1014] border border-[#262932] text-zinc-100"
          />
        </label>
        <div class="grid grid-cols-2 gap-1.5">
          <label class="space-y-0.5">
            <span class="text-zinc-400">规划章数</span>
            <input
              :value="params.num_chapters ?? 30"
              @input="setParam('num_chapters', Number(($event.target as HTMLInputElement).value) || 30)"
              type="number"
              min="1"
              class="w-full px-2 py-1 rounded bg-[#0e1014] border border-[#262932] text-sky-300 font-mono"
            />
          </label>
          <label class="space-y-0.5">
            <span class="text-zinc-400">每章字数</span>
            <input
              :value="params.word_number ?? 2800"
              @input="setParam('word_number', Number(($event.target as HTMLInputElement).value) || 2800)"
              type="number"
              step="100"
              class="w-full px-2 py-1 rounded bg-[#0e1014] border border-[#262932] text-zinc-200 font-mono"
            />
          </label>
        </div>
        <label class="block space-y-0.5">
          <span class="text-zinc-400">脑洞 / 主题设定</span>
          <textarea
            :value="params.topic || ''"
            @input="setParam('topic', ($event.target as HTMLTextAreaElement).value)"
            rows="2"
            placeholder="留空则读取当前书籍已有设定…"
            class="w-full rounded bg-[#0e1014] border border-[#262932] p-1.5 text-[10px] text-zinc-200"
          />
        </label>
      </template>

      <!-- arch_generator -->
      <template v-else-if="data.nodeType === 'arch_generator'">
        <label class="block space-y-0.5">
          <span class="text-zinc-400">架构生成模型</span>
          <select
            :value="params.llm_config_name || ''"
            @change="setParam('llm_config_name', ($event.target as HTMLSelectElement).value)"
            class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-zinc-100"
          >
            <option value="">(跟随项目默认架构模型)</option>
            <option v-for="m in configStore.llmChoices" :key="m" :value="m">{{ m }}</option>
          </select>
        </label>
        <div class="text-[10px] text-zinc-400">
          依据立项参数构建世界观、角色矩阵与全书冲突主线。
        </div>
      </template>

      <!-- directory_generator -->
      <template v-else-if="data.nodeType === 'directory_generator'">
        <label class="block space-y-0.5">
          <span class="text-zinc-400">目录生成模型</span>
          <select
            :value="params.llm_config_name || ''"
            @change="setParam('llm_config_name', ($event.target as HTMLSelectElement).value)"
            class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-zinc-100"
          >
            <option value="">(跟随项目默认架构模型)</option>
            <option v-for="m in configStore.llmChoices" :key="m" :value="m">{{ m }}</option>
          </select>
        </label>
        <div class="text-[10px] text-zinc-400">
          输出全书分卷章纲目录 `Novel_directory.txt`。
        </div>
      </template>

      <!-- batch_outline_gate -->
      <template v-else-if="data.nodeType === 'batch_outline_gate'">
        <div class="grid grid-cols-2 gap-1.5">
          <label class="space-y-0.5">
            <span class="text-zinc-400">起始章号</span>
            <input
              :value="params.start_chapter ?? 1"
              @input="setParam('start_chapter', Number(($event.target as HTMLInputElement).value) || 1)"
              type="number"
              min="1"
              class="w-full px-2 py-1 rounded bg-[#0e1014] border border-[#262932] text-sky-300 font-mono"
            />
          </label>
          <label class="space-y-0.5">
            <span class="text-zinc-400">批大小(章)</span>
            <input
              :value="params.batch_size ?? 3"
              @input="setParam('batch_size', Number(($event.target as HTMLInputElement).value) || 3)"
              type="number"
              min="1"
              max="20"
              class="w-full px-2 py-1 rounded bg-[#0e1014] border border-[#262932] text-zinc-200 font-mono"
            />
          </label>
        </div>
        <label class="flex items-center gap-2 text-amber-300 cursor-pointer">
          <input
            :checked="Boolean(params.pause_after_batch)"
            @change="setParam('pause_after_batch', ($event.target as HTMLInputElement).checked)"
            type="checkbox"
          />
          <span>生成后暂停待人工审阅放行</span>
        </label>
        <div v-if="runtime.status === 'waiting_gate'" class="pt-1 flex gap-1.5">
          <button
            @click="wf.submitGate({ action: 'approve' })"
            type="button"
            class="flex-1 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-[11px] cursor-pointer"
          >
            ✅ 确认细纲放行
          </button>
        </div>
      </template>

      <!-- chapter_input -->
      <template v-else-if="data.nodeType === 'chapter_input'">
        <div class="grid grid-cols-2 gap-2">
          <label class="space-y-0.5">
            <span class="text-zinc-400">当前章号</span>
            <input
              :value="wf.canvasChapterNum.value"
              @input="wf.canvasChapterNum.value = Number(($event.target as HTMLInputElement).value) || 1"
              type="number"
              min="1"
              class="w-full px-2 py-1 rounded bg-[#0e1014] border border-[#262932] text-sky-300 font-mono"
            />
          </label>
          <label class="space-y-0.5">
            <span class="text-zinc-400">目标字数</span>
            <input
              :value="wf.canvasWordNumber.value"
              @input="wf.canvasWordNumber.value = Number(($event.target as HTMLInputElement).value) || 2500"
              type="number"
              step="100"
              class="w-full px-2 py-1 rounded bg-[#0e1014] border border-[#262932] text-zinc-200 font-mono"
            />
          </label>
        </div>
      </template>

      <!-- outline_loader -->
      <template v-else-if="data.nodeType === 'outline_loader'">
        <label class="flex items-center gap-1.5 cursor-pointer text-zinc-200">
          <input
            :checked="params.auto_complete !== false"
            @change="setParam('auto_complete', ($event.target as HTMLInputElement).checked)"
            type="checkbox"
            class="accent-amber-400"
          />
          <span>缺细纲时回退读取目录梗概</span>
        </label>
        <textarea
          :value="params.override_outline || ''"
          @input="setParam('override_outline', ($event.target as HTMLTextAreaElement).value)"
          rows="2"
          placeholder="可选：留空则读取磁盘本章细纲，填写则临时覆盖…"
          class="w-full rounded bg-[#0e1014] border border-[#262932] p-1.5 text-[11px] text-zinc-200"
        />
      </template>

      <!-- memory_assembler -->
      <template v-else-if="data.nodeType === 'memory_assembler'">
        <div class="grid grid-cols-2 gap-1.5 text-zinc-200">
          <label
            v-for="item in ([
              ['inject_summary', '前文摘要'],
              ['inject_char_state', '角色状态'],
              ['inject_world_building', '世界观'],
              ['inject_canon', '正史约束'],
              ['inject_handoff', '上章交接'],
            ] as const)"
            :key="item[0]"
            class="flex items-center gap-1.5 cursor-pointer"
          >
            <input
              :checked="params[item[0]] !== false"
              @change="setParam(item[0], ($event.target as HTMLInputElement).checked)"
              type="checkbox"
              class="accent-teal-400"
            />
            <span>{{ item[1] }}</span>
          </label>
        </div>
      </template>

      <!-- character_profile -->
      <template v-else-if="data.nodeType === 'character_profile'">
        <label class="block">
          <div class="flex justify-between text-zinc-400">
            <span>人设档案截取上限</span>
            <span class="font-mono text-teal-300">{{ params.max_chars ?? 2500 }} 字</span>
          </div>
          <input
            :value="params.max_chars ?? 2500"
            @input="setParam('max_chars', Number(($event.target as HTMLInputElement).value))"
            type="range" min="800" max="5000" step="100"
            class="w-full accent-teal-400"
          />
        </label>
      </template>

      <!-- prev_excerpt_loader -->
      <template v-else-if="data.nodeType === 'prev_excerpt_loader'">
        <label class="block">
          <div class="flex justify-between text-zinc-400">
            <span>读取上章结尾字数</span>
            <span class="font-mono text-teal-300">{{ params.tail_chars ?? 800 }} 字</span>
          </div>
          <input
            :value="params.tail_chars ?? 800"
            @input="setParam('tail_chars', Number(($event.target as HTMLInputElement).value))"
            type="range" min="300" max="1500" step="50"
            class="w-full accent-teal-400"
          />
        </label>
      </template>

      <!-- rag_retriever -->
      <template v-else-if="data.nodeType === 'rag_retriever'">
        <label class="block">
          <div class="flex justify-between text-zinc-400">
            <span>检索片段条数 (Top-K)</span>
            <span class="font-mono text-teal-300">{{ params.top_k ?? 4 }} 条</span>
          </div>
          <input
            :value="params.top_k ?? 4"
            @input="setParam('top_k', Number(($event.target as HTMLInputElement).value))"
            type="range" min="1" max="8" step="1"
            class="w-full accent-teal-400"
          />
        </label>
        <input
          :value="params.query_override || ''"
          @input="setParam('query_override', ($event.target as HTMLInputElement).value)"
          type="text"
          placeholder="可选自定义检索关键词（留空自动用细纲检索）"
          class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-[11px]"
        />
      </template>

      <!-- foreshadow_loader -->
      <template v-else-if="data.nodeType === 'foreshadow_loader'">
        <textarea
          :value="params.extra_foreshadow || ''"
          @input="setParam('extra_foreshadow', ($event.target as HTMLTextAreaElement).value)"
          rows="2"
          placeholder="补充本章必须埋下或回收的伏笔线索（会自动合并全局伏笔池）…"
          class="w-full rounded bg-[#0e1014] border border-[#262932] p-1.5 text-[11px]"
        />
      </template>

      <!-- forbidden_lock -->
      <template v-else-if="data.nodeType === 'forbidden_lock'">
        <textarea
          :value="params.forbidden_words || ''"
          @input="setParam('forbidden_words', ($event.target as HTMLTextAreaElement).value)"
          rows="2"
          placeholder="AI禁用词黑名单（逗号分隔）…"
          class="w-full rounded bg-[#0e1014] border border-[#262932] p-1.5 text-[10px]"
        />
        <input
          :value="params.term_locks || ''"
          @input="setParam('term_locks', ($event.target as HTMLInputElement).value)"
          type="text"
          placeholder="称谓/招式名锁定（例：主角固定称呼陈默）"
          class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-[10px]"
        />
      </template>

      <!-- note_primitive -->
      <template v-else-if="data.nodeType === 'note_primitive'">
        <input
          :value="params.note_title || '临时设定补充'"
          @input="setParam('note_title', ($event.target as HTMLInputElement).value)"
          type="text"
          class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-teal-300 font-semibold"
        />
        <textarea
          :value="params.note_content || ''"
          @input="setParam('note_content', ($event.target as HTMLTextAreaElement).value)"
          rows="3"
          placeholder="写任意背景便签、台词金句或临场要求，可同时连给多个节点…"
          class="w-full rounded bg-[#0e1014] border border-[#262932] p-1.5 text-[11px]"
        />
      </template>

      <!-- context_combiner -->
      <template v-else-if="data.nodeType === 'context_combiner'">
        <div class="text-zinc-400 leading-relaxed">
          把左侧接入的所有设定/记忆束自动拼接整理成一份完整上下文往下传递。
        </div>
      </template>

      <!-- style_prompt -->
      <template v-else-if="data.nodeType === 'style_prompt'">
        <div class="grid grid-cols-2 gap-1.5">
          <label class="block space-y-0.5">
            <span class="text-zinc-400">文风 DNA</span>
            <select
              :value="params.style_name || ''"
              @change="setParam('style_name', ($event.target as HTMLSelectElement).value)"
              class="w-full rounded bg-[#0e1014] border border-[#262932] px-1.5 py-1 text-zinc-200"
            >
              <option value="">默认 / 不指定</option>
              <option v-for="s in wf.styleChoices.value" :key="s" :value="s">{{ s }}</option>
            </select>
          </label>
          <label class="block space-y-0.5">
            <span class="text-zinc-400">卖点 / XP 标签</span>
            <input
              :value="params.xp_type || ''"
              @input="setParam('xp_type', ($event.target as HTMLInputElement).value)"
              type="text"
              placeholder="如：反派压迫/装逼打脸"
              class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-zinc-200"
            />
          </label>
        </div>
        <textarea
          :value="params.user_guidance || ''"
          @input="setParam('user_guidance', ($event.target as HTMLTextAreaElement).value)"
          rows="2"
          placeholder="导演补充指令（如节奏/情绪/台词风格）…"
          class="w-full rounded bg-[#0e1014] border border-[#262932] p-1.5 text-zinc-200"
        />
      </template>

      <!-- llm_config -->
      <template v-else-if="data.nodeType === 'llm_config'">
        <label class="block space-y-0.5">
          <span class="text-zinc-400">选择模型</span>
          <select
            :value="params.llm_config_name || ''"
            @change="setParam('llm_config_name', ($event.target as HTMLSelectElement).value)"
            class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-emerald-300"
          >
            <option v-for="m in configStore.llmChoices" :key="m" :value="m">{{ m }}</option>
          </select>
        </label>
        <label class="block">
          <div class="flex justify-between text-zinc-400">
            <span>Temperature</span>
            <span class="font-mono text-emerald-300">{{ params.temperature ?? 0.7 }}</span>
          </div>
          <input
            :value="params.temperature ?? 0.7"
            @input="setParam('temperature', Number(($event.target as HTMLInputElement).value))"
            type="range" min="0.1" max="1.3" step="0.05"
            class="w-full accent-emerald-400"
          />
        </label>
      </template>

      <!-- pre_write_gate -->
      <template v-else-if="data.nodeType === 'pre_write_gate'">
        <label class="block space-y-0.5">
          <span class="text-zinc-400">预检模型</span>
          <select
            :value="params.llm_config_name || ''"
            @change="setParam('llm_config_name', ($event.target as HTMLSelectElement).value)"
            class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-zinc-200"
          >
            <option v-for="m in configStore.llmChoices" :key="m" :value="m">{{ m }}</option>
          </select>
        </label>
        <label class="block space-y-0.5">
          <span class="text-zinc-400">冲突处理策略</span>
          <select
            :value="params.on_fail || 'append_hint'"
            @change="setParam('on_fail', ($event.target as HTMLSelectElement).value)"
            class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-amber-300"
          >
            <option value="append_hint">附带纠偏提醒放行给起草</option>
            <option value="pause">发现冲突时暂停等人工处理</option>
            <option value="warn_only">仅记录警告不改细纲</option>
          </select>
        </label>
      </template>

      <!-- draft_writer -->
      <template v-else-if="data.nodeType === 'draft_writer'">
        <label class="block space-y-0.5">
          <span class="text-zinc-400">起草模型</span>
          <select
            :value="params.llm_config_name || ''"
            @change="setParam('llm_config_name', ($event.target as HTMLSelectElement).value)"
            class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-zinc-100"
          >
            <option v-for="m in configStore.llmChoices" :key="m" :value="m">{{ m }}</option>
          </select>
        </label>
        <div class="grid grid-cols-2 gap-2">
          <label>
            <div class="flex justify-between text-zinc-400">
              <span>温度</span>
              <span class="font-mono text-zinc-100">{{ params.temperature ?? 0.7 }}</span>
            </div>
            <input
              :value="params.temperature ?? 0.7"
              @input="setParam('temperature', Number(($event.target as HTMLInputElement).value))"
              type="range" min="0.1" max="1.3" step="0.05"
              class="w-full accent-emerald-500"
            />
          </label>
          <label class="space-y-0.5">
            <span class="text-zinc-400">字数 (0=跟随起点)</span>
            <input
              :value="params.word_number ?? 0"
              @input="setParam('word_number', Number(($event.target as HTMLInputElement).value) || 0)"
              type="number"
              min="0"
              step="100"
              class="w-full px-1.5 py-0.5 rounded bg-[#0e1014] border border-[#262932] font-mono text-zinc-200"
            />
          </label>
        </div>
        <label class="flex items-center gap-1.5 cursor-pointer text-zinc-200">
          <input
            :checked="params.scene_by_scene !== false"
            @change="setParam('scene_by_scene', ($event.target as HTMLInputElement).checked)"
            type="checkbox"
            class="accent-emerald-500"
          />
          <span>分场景渐进起草</span>
        </label>
        <button
          @click="showPromptEditor = !showPromptEditor"
          type="button"
          class="w-full text-left px-2 py-1 rounded bg-[#1d2028] hover:bg-[#262a35] text-zinc-200 text-[10px] flex justify-between cursor-pointer"
        >
          <span>⚙️ 展开底层 Prompt 模板 / 附加指令</span>
          <span>{{ showPromptEditor ? '▴' : '▾' }}</span>
        </button>
        <div v-if="showPromptEditor" class="space-y-1.5 pt-1">
          <textarea
            :value="params.writing_guidance || ''"
            @input="setParam('writing_guidance', ($event.target as HTMLTextAreaElement).value)"
            rows="2"
            placeholder="附加写作重点指令…"
            class="w-full rounded bg-[#0e1014] border border-[#262932] p-1.5 text-[11px]"
          />
          <textarea
            :value="params.custom_prompt_template || ''"
            @input="setParam('custom_prompt_template', ($event.target as HTMLTextAreaElement).value)"
            rows="4"
            placeholder="留空=用内置「中文十条铁律」起草引擎；填写则接管模板（支持 {outline} {context_bundle} {word_number}）"
            class="w-full rounded bg-[#0e1014] border border-[#262932] p-1.5 font-mono text-[10px]"
          />
          <button @click="resetPromptToDefault()" type="button" class="text-[10px] text-sky-400 hover:underline cursor-pointer">
            ↺ 清空并恢复内置引擎
          </button>
        </div>
      </template>

      <!-- script_audit -->
      <template v-else-if="data.nodeType === 'script_audit'">
        <label class="block">
          <div class="flex justify-between text-zinc-400">
            <span>及格阈值分数</span>
            <span class="font-mono text-amber-300">{{ params.min_score ?? 80 }} 分</span>
          </div>
          <input
            :value="params.min_score ?? 80"
            @input="setParam('min_score', Number(($event.target as HTMLInputElement).value))"
            type="range" min="50" max="100" step="5"
            class="w-full accent-amber-400"
          />
        </label>
        <label class="block space-y-0.5">
          <span class="text-zinc-400">不达标策略</span>
          <select
            :value="params.on_fail || 'pass_to_ai'"
            @change="setParam('on_fail', ($event.target as HTMLSelectElement).value)"
            class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-zinc-200"
          >
            <option value="pass_to_ai">输出整改清单交给下游审校</option>
            <option value="pause">不达标时暂停等人工处理</option>
            <option value="warn_only">仅提示分数，直接放行</option>
          </select>
        </label>
      </template>

      <!-- deai_reviewer -->
      <template v-else-if="data.nodeType === 'deai_reviewer'">
        <label class="block space-y-0.5">
          <span class="text-zinc-400">审校模型</span>
          <select
            :value="params.llm_config_name || ''"
            @change="setParam('llm_config_name', ($event.target as HTMLSelectElement).value)"
            class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-emerald-300"
          >
            <option v-for="m in configStore.llmChoices" :key="m" :value="m">{{ m }}</option>
          </select>
        </label>
        <div class="grid grid-cols-2 gap-1 bg-[#12141a] p-0.5 rounded border border-[#323846]">
          <button
            @click="onReviewStrengthChange('strong')"
            type="button"
            class="py-1 rounded text-[10px] font-bold cursor-pointer"
            :class="(params.review_strength || 'strong') === 'strong' ? 'bg-emerald-600 text-white' : 'text-zinc-400'"
          >
            🔥 强力去AI味
          </button>
          <button
            @click="onReviewStrengthChange('light')"
            type="button"
            class="py-1 rounded text-[10px] font-bold cursor-pointer"
            :class="params.review_strength === 'light' ? 'bg-emerald-600 text-white' : 'text-zinc-400'"
          >
            🍃 轻度润色
          </button>
        </div>
        <button
          @click="showPromptEditor = !showPromptEditor"
          type="button"
          class="w-full text-left px-2 py-1 rounded bg-[#1d2028] hover:bg-[#262a35] text-zinc-200 text-[10px] flex justify-between cursor-pointer"
        >
          <span>⚙️ 展开完整去AI Prompt 模板</span>
          <span>{{ showPromptEditor ? '▴' : '▾' }}</span>
        </button>
        <div v-if="showPromptEditor" class="space-y-1.5 pt-1">
          <textarea
            :value="params.custom_prompt_template || ''"
            @input="setParam('custom_prompt_template', ($event.target as HTMLTextAreaElement).value)"
            rows="6"
            class="w-full rounded bg-[#0e1014] border border-[#262932] p-1.5 font-mono text-[10px] text-zinc-200"
          />
          <button @click="resetPromptToDefault()" type="button" class="text-[10px] text-emerald-400 hover:underline cursor-pointer">
            ↺ 恢复系统默认审校模板
          </button>
        </div>
      </template>

      <!-- custom_rewrite -->
      <template v-else-if="data.nodeType === 'custom_rewrite'">
        <label class="block space-y-0.5">
          <span class="text-zinc-400">改写模型</span>
          <select
            :value="params.llm_config_name || ''"
            @change="setParam('llm_config_name', ($event.target as HTMLSelectElement).value)"
            class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-zinc-100"
          >
            <option v-for="m in configStore.llmChoices" :key="m" :value="m">{{ m }}</option>
          </select>
        </label>
        <textarea
          :value="params.instruction || ''"
          @input="setParam('instruction', ($event.target as HTMLTextAreaElement).value)"
          rows="2"
          placeholder="填写二改指令…"
          class="w-full rounded bg-[#0e1014] border border-[#262932] p-1.5 text-[11px]"
        />
        <button
          @click="showPromptEditor = !showPromptEditor"
          type="button"
          class="w-full text-left px-2 py-1 rounded bg-[#1d2028] hover:bg-[#262a35] text-zinc-200 text-[10px] flex justify-between cursor-pointer"
        >
          <span>⚙️ 展开完整改写 Prompt 模板</span>
          <span>{{ showPromptEditor ? '▴' : '▾' }}</span>
        </button>
        <div v-if="showPromptEditor" class="space-y-1.5 pt-1">
          <textarea
            :value="params.custom_prompt_template || ''"
            @input="setParam('custom_prompt_template', ($event.target as HTMLTextAreaElement).value)"
            rows="5"
            class="w-full rounded bg-[#0e1014] border border-[#262932] p-1.5 font-mono text-[10px]"
          />
          <button @click="resetPromptToDefault()" type="button" class="text-[10px] text-sky-400 hover:underline cursor-pointer">
            ↺ 恢复默认改写模板
          </button>
        </div>
      </template>

      <!-- ending_hook_rewriter -->
      <template v-else-if="data.nodeType === 'ending_hook_rewriter'">
        <label class="block space-y-0.5">
          <span class="text-zinc-400">精修模型</span>
          <select
            :value="params.llm_config_name || ''"
            @change="setParam('llm_config_name', ($event.target as HTMLSelectElement).value)"
            class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-zinc-100"
          >
            <option v-for="m in configStore.llmChoices" :key="m" :value="m">{{ m }}</option>
          </select>
        </label>
        <label class="block">
          <div class="flex justify-between text-zinc-400">
            <span>结尾切片重铸长度</span>
            <span class="font-mono text-zinc-100">{{ params.tail_chars ?? 420 }} 字</span>
          </div>
          <input
            :value="params.tail_chars ?? 420"
            @input="setParam('tail_chars', Number(($event.target as HTMLInputElement).value))"
            type="range" min="200" max="800" step="20"
            class="w-full accent-emerald-500"
          />
        </label>
        <button
          @click="showPromptEditor = !showPromptEditor"
          type="button"
          class="w-full text-left px-2 py-1 rounded bg-[#1d2028] hover:bg-[#262a35] text-zinc-200 text-[10px] flex justify-between cursor-pointer"
        >
          <span>⚙️ 展开钩子精修 Prompt</span>
          <span>{{ showPromptEditor ? '▴' : '▾' }}</span>
        </button>
        <div v-if="showPromptEditor" class="space-y-1.5 pt-1">
          <textarea
            :value="params.custom_prompt_template || ''"
            @input="setParam('custom_prompt_template', ($event.target as HTMLTextAreaElement).value)"
            rows="5"
            class="w-full rounded bg-[#0e1014] border border-[#262932] p-1.5 font-mono text-[10px]"
          />
          <button @click="resetPromptToDefault()" type="button" class="text-[10px] text-sky-400 hover:underline cursor-pointer">
            ↺ 恢复默认钩子模板
          </button>
        </div>
      </template>

      <!-- human_gate -->
      <template v-else-if="data.nodeType === 'human_gate'">
        <label class="block space-y-0.5">
          <span class="text-zinc-400">暂停策略</span>
          <select
            :value="params.gate_mode || 'always'"
            @change="setParam('gate_mode', ($event.target as HTMLSelectElement).value)"
            class="w-full rounded bg-[#0e1014] border border-[#262932] px-2 py-1 text-amber-300"
          >
            <option value="always">按全局设置（单章必停）</option>
            <option value="single_only">仅单章运行暂停</option>
            <option value="never">直通不暂停</option>
          </select>
        </label>
        <div v-if="runtime.status === 'waiting_gate'" class="pt-1 flex gap-1.5">
          <button
            @click="wf.submitGate({ action: 'approve' })"
            type="button"
            class="flex-1 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-[11px] cursor-pointer"
          >
            ✅ 确认放行
          </button>
          <button
            @click="wf.inspectedNodeId.value = id"
            type="button"
            class="px-2 py-1.5 rounded bg-amber-600 hover:bg-amber-500 text-white font-bold text-[11px] cursor-pointer"
          >
            审阅
          </button>
        </div>
      </template>

      <!-- ab_selector -->
      <template v-else-if="data.nodeType === 'ab_selector'">
        <div class="text-zinc-400">接入分支 A / B 后暂停并打开红绿对比，择优向下传递。</div>
        <button
          v-if="runtime.status === 'waiting_gate'"
          @click="wf.pendingGate.value && (wf.inspectedNodeId.value = id)"
          type="button"
          class="w-full py-1.5 rounded bg-amber-600 hover:bg-amber-500 text-white font-bold text-[11px] cursor-pointer animate-pulse"
        >
          ⚖️ 打开 A/B 红绿对比择优
        </button>
      </template>

      <!-- memory_archive -->
      <template v-else-if="data.nodeType === 'memory_archive'">
        <label class="flex items-center gap-1.5 cursor-pointer text-zinc-200">
          <input
            :checked="params.update_canon !== false"
            @change="setParam('update_canon', ($event.target as HTMLInputElement).checked)"
            type="checkbox"
            class="accent-emerald-400"
          />
          <span>同步演进正史约束与 Handoff 交接</span>
        </label>
      </template>
    </div>

    <!-- 底部：产出状态条 + 质检分 + 迷你预览 -->
    <div
      v-if="runtime.status !== 'idle'"
      class="px-2.5 py-1.5 border-t border-[#22252e] bg-[#111318] rounded-b-xl text-[10px] space-y-1.5 nodrag nowheel"
    >
      <div class="flex items-center justify-between gap-1 text-zinc-400">
        <span class="truncate">
          <template v-if="runtime.status === 'completed'">✓ {{ runtime.message || '完成' }}</template>
          <template v-else-if="runtime.status === 'cached'">♻️ 命中缓存</template>
          <template v-else-if="runtime.status === 'bypassed'">⏭️ 已旁路跳过</template>
          <template v-else-if="runtime.status === 'error'">❌ 出错</template>
          <template v-else>{{ runtime.message }}</template>
        </span>
        <span
          v-if="auditScore !== null"
          class="px-1.5 py-0.5 rounded font-mono font-bold shrink-0"
          :class="auditScore >= 80 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'"
        >
          {{ auditScore }}/100
        </span>
        <span v-else-if="previewChars > 0" class="font-mono text-emerald-400 shrink-0">{{ previewChars }} 字</span>
      </div>

      <div v-if="previewSnippet" class="flex items-center gap-1.5">
        <button
          @click.stop="showMiniPreview = !showMiniPreview"
          type="button"
          class="px-2 py-0.5 rounded bg-[#1d2028] hover:bg-[#262a35] text-zinc-200 cursor-pointer"
        >
          {{ showMiniPreview ? '收起摘要' : '👁️ 节点内预览' }}
        </button>
        <button
          @click.stop="wf.inspectedNodeId.value = id"
          type="button"
          class="px-2 py-0.5 rounded bg-zinc-700/60 hover:bg-zinc-600/80 text-zinc-100 cursor-pointer"
        >
          🔍 全屏 / Diff
        </button>
      </div>

      <div
        v-if="showMiniPreview && previewSnippet"
        class="p-2 rounded bg-[#0b0c10] border border-[#22252e] text-[#d4d4d8] text-[11px] leading-relaxed max-h-28 overflow-y-auto whitespace-pre-wrap select-text font-novel-prose"
      >
        {{ previewSnippet.slice(0, 420) }}{{ previewSnippet.length > 420 ? '…' : '' }}
      </div>
    </div>
  </div>
</template>
