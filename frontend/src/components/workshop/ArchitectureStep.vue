<script setup lang="ts">
import { ref } from 'vue'
import type { useWorkshopState } from '@/composables/useWorkshopState'
import StepCard from '@/components/StepCard.vue'
import StreamOutput from '@/components/StreamOutput.vue'

defineProps<{ state: ReturnType<typeof useWorkshopState> }>()

type ArchTab = 'seed' | 'chars' | 'char_state' | 'world' | 'plot' | 'full' | 'continue'
const activeTab = ref<ArchTab>('seed')
</script>

<template>
  <StepCard :step="1" title="小说雪花架构" description="核心种子 · 角色动力学 · 世界观 · 剧情骨架（标签页切换，专注编辑）">
    <div class="space-y-4">
      <!-- 顶部控制栏 -->
      <div class="flex flex-wrap gap-3 items-center pb-3 border-b border-[var(--color-parchment-darker)]">
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">叙事DNA</label>
          <select v-model="state.archStyle.value" class="border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm bg-white">
            <option v-for="s in state.styleList.value" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-[var(--color-ink-light)] mb-1">角色人数</label>
          <input v-model="state.numCharacters.value" placeholder="3-6" class="w-20 border border-[var(--color-parchment-darker)] rounded-md px-3 py-1.5 text-sm bg-white" />
        </div>
        <div class="flex-1" />
        <label class="flex items-center gap-2 text-sm cursor-pointer select-none">
          <input type="checkbox" v-model="state.stepMode.value" class="accent-[var(--color-leather)]" />
          分步推演模式
        </label>
        <button
          v-if="!state.stepMode.value"
          @click="state.doGenerateArch()"
          :disabled="state.arch.value.running || !state.llmConfig.value"
          class="btn-primary"
          type="button"
        >
          {{ state.arch.value.running ? '生成中…' : '▶ 生成完整架构' }}
        </button>
        <button
          v-else
          @click="state.doAssemble()"
          :disabled="!state.seedText.value || !state.charText.value || !state.worldText.value || (state.workflowMode.value !== 'improv' && !state.plotText.value)"
          class="btn-primary"
          type="button"
        >
          ▶ 组装并保存架构
        </button>
      </div>

      <!-- 子标签导航 -->
      <div class="flex items-center gap-1.5 flex-wrap bg-[var(--color-parchment)]/60 p-1.5 rounded-xl border border-[var(--color-parchment-darker)] text-xs">
        <button
          @click="activeTab = 'seed'"
          type="button"
          class="px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5"
          :class="activeTab === 'seed' ? 'bg-[var(--color-leather)] text-white shadow-xs' : 'text-[var(--color-ink-light)] hover:bg-white'"
        >
          <span>① 核心种子</span>
          <span v-if="state.seedText.value" class="w-1.5 h-1.5 rounded-full bg-emerald-400" />
        </button>

        <button
          @click="activeTab = 'chars'"
          type="button"
          class="px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5"
          :class="activeTab === 'chars' ? 'bg-[var(--color-leather)] text-white shadow-xs' : 'text-[var(--color-ink-light)] hover:bg-white'"
        >
          <span>② 角色动力学</span>
          <span v-if="state.charText.value" class="w-1.5 h-1.5 rounded-full bg-emerald-400" />
        </button>

        <button
          @click="activeTab = 'char_state'"
          type="button"
          class="px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5"
          :class="activeTab === 'char_state' ? 'bg-[var(--color-leather)] text-white shadow-xs' : 'text-[var(--color-ink-light)] hover:bg-white'"
        >
          <span>③ 角色状态</span>
          <span v-if="state.charStateText.value" class="w-1.5 h-1.5 rounded-full bg-emerald-400" />
        </button>

        <button
          @click="activeTab = 'world'"
          type="button"
          class="px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5"
          :class="activeTab === 'world' ? 'bg-[var(--color-leather)] text-white shadow-xs' : 'text-[var(--color-ink-light)] hover:bg-white'"
        >
          <span>④ 世界观</span>
          <span v-if="state.worldText.value" class="w-1.5 h-1.5 rounded-full bg-emerald-400" />
        </button>

        <button
          v-if="state.workflowMode.value !== 'improv'"
          @click="activeTab = 'plot'"
          type="button"
          class="px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5"
          :class="activeTab === 'plot' ? 'bg-[var(--color-leather)] text-white shadow-xs' : 'text-[var(--color-ink-light)] hover:bg-white'"
        >
          <span>⑤ 剧情骨架</span>
          <span v-if="state.plotText.value" class="w-1.5 h-1.5 rounded-full bg-emerald-400" />
        </button>

        <button
          @click="activeTab = 'full'"
          type="button"
          class="px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5"
          :class="activeTab === 'full' ? 'bg-[var(--color-leather)] text-white shadow-xs' : 'text-[var(--color-ink-light)] hover:bg-white'"
        >
          <span>📄 完整总览</span>
        </button>

        <button
          @click="activeTab = 'continue'"
          type="button"
          class="px-3 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5 ml-auto"
          :class="activeTab === 'continue' ? 'bg-amber-700 text-white shadow-xs' : 'text-amber-800 hover:bg-amber-50 border border-amber-200'"
        >
          <span>➕ 续写新卷</span>
        </button>
      </div>

      <!-- ① 核心种子 -->
      <div v-show="activeTab === 'seed'" class="space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-sm font-semibold text-[var(--color-leather)]">① 核心种子（一句话冲突与灵魂）</span>
          <div class="flex items-center gap-2">
            <span v-if="state.stepSeed.value.running" class="text-xs text-[var(--color-ink-light)] italic">{{ state.stepSeed.value.progress || '生成中…' }}</span>
            <button v-if="state.stepMode.value" @click="state.doStepSeed()" :disabled="state.stepSeed.value.running || !state.llmConfig.value" class="btn-sm" type="button">
              {{ state.stepSeed.value.running ? '生成中…' : '▶ 生成种子' }}
            </button>
            <button @click="state.saveCoreSeed()" :disabled="!state.seedText.value" class="btn-sm" type="button">💾 保存</button>
          </div>
        </div>
        <textarea v-model="state.seedText.value" rows="10" placeholder="点击生成或手动编辑核心种子…"
          class="w-full border border-[var(--color-parchment-darker)] rounded-lg px-3.5 py-2.5 text-sm font-serif leading-relaxed resize-y bg-white" />
        <p v-if="state.stepSeed.value.error" class="text-xs text-red-500">{{ state.stepSeed.value.error }}</p>
        <div v-if="state.seedText.value" class="flex items-center gap-2 pt-1">
          <input v-model="state.revisionGuidance.value.core_seed" placeholder="输入 AI 修订建议（如：让核心冲突更激烈…）" class="flex-1 border border-[var(--color-parchment-darker)] rounded-lg px-3 py-1.5 text-sm" />
          <button @click="state.doRevise('core_seed')" :disabled="state.revisionState.value.core_seed.running || !state.revisionGuidance.value.core_seed || !state.llmConfig.value" class="btn-sm" type="button">
            {{ state.revisionState.value.core_seed.running ? '修订中…' : '✏️ AI 修订' }}
          </button>
        </div>
      </div>

      <!-- ② 角色动力学 -->
      <div v-show="activeTab === 'chars'" class="space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-sm font-semibold text-[var(--color-leather)]">② 角色动力学（人物关系与弧线）</span>
          <div class="flex items-center gap-2">
            <span v-if="state.stepChar.value.running" class="text-xs text-[var(--color-ink-light)] italic">{{ state.stepChar.value.progress || '生成中…' }}</span>
            <button v-if="state.stepMode.value" @click="state.doStepChar()" :disabled="state.stepChar.value.running || !state.seedText.value || !state.llmConfig.value" class="btn-sm" type="button">
              {{ state.stepChar.value.running ? '生成中…' : '▶ 生成角色' }}
            </button>
            <button @click="state.saveCharDynamics()" :disabled="!state.charText.value" class="btn-sm" type="button">💾 保存</button>
          </div>
        </div>
        <textarea v-model="state.charText.value" rows="12" placeholder="基于核心种子生成角色动力学…"
          class="w-full border border-[var(--color-parchment-darker)] rounded-lg px-3.5 py-2.5 text-sm font-serif leading-relaxed resize-y bg-white" />
        <p v-if="state.stepChar.value.error" class="text-xs text-red-500">{{ state.stepChar.value.error }}</p>
        <div v-if="state.charText.value" class="space-y-2">
          <div class="flex items-center gap-2">
            <input v-model="state.revisionGuidance.value.characters" placeholder="输入 AI 修订建议（如：强化主角与反派博弈…）" class="flex-1 border border-[var(--color-parchment-darker)] rounded-lg px-3 py-1.5 text-sm" />
            <button @click="state.doRevise('characters')" :disabled="state.revisionState.value.characters.running || !state.revisionGuidance.value.characters || !state.llmConfig.value" class="btn-sm" type="button">
              {{ state.revisionState.value.characters.running ? '修订中…' : '✏️ AI 修订' }}
            </button>
          </div>
          <details class="border border-dashed border-[var(--color-parchment-darker)] rounded-lg p-3">
            <summary class="cursor-pointer text-xs font-medium text-[var(--color-leather)] select-none">＋ 补充新角色</summary>
            <div class="mt-2 space-y-2">
              <div class="flex gap-2 items-end flex-wrap">
                <input v-model="state.supplementGuidance.value" placeholder="补充要求，如：增加一位宗门长老…" class="flex-1 border border-[var(--color-parchment-darker)] rounded px-2 py-1 text-sm" />
                <input v-model="state.supplementNum.value" placeholder="1-2" class="w-16 border border-[var(--color-parchment-darker)] rounded px-2 py-1 text-sm text-center" />
                <button @click="state.doSupplementChar()" :disabled="state.supplementChar.value.running || !state.charText.value || !state.llmConfig.value" class="btn-sm" type="button">
                  {{ state.supplementChar.value.running ? '生成中…' : '▶ 生成补充角色' }}
                </button>
              </div>
              <div v-if="state.supplementResult.value" class="space-y-2">
                <textarea v-model="state.supplementResult.value" rows="5" class="w-full border border-[var(--color-parchment-darker)] rounded px-3 py-2 text-sm font-mono" />
                <div class="flex justify-end gap-2">
                  <button @click="state.supplementResult.value = ''" class="btn-sm" type="button">清空</button>
                  <button @click="state.appendSupplementChar()" class="btn-sm" type="button">✅ 追加到角色列表</button>
                </div>
              </div>
            </div>
          </details>
        </div>
      </div>

      <!-- ③ 角色状态 -->
      <div v-show="activeTab === 'char_state'" class="space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-sm font-semibold text-[var(--color-leather)]">③ 角色初始状态（物品 / 能力 / 外貌 / 口癖）</span>
          <div class="flex items-center gap-2">
            <span v-if="state.stepCharState.value.running" class="text-xs text-[var(--color-ink-light)] italic">{{ state.stepCharState.value.progress || '生成中…' }}</span>
            <button v-if="state.stepMode.value" @click="state.doStepCharState()" :disabled="state.stepCharState.value.running || !state.charText.value || !state.llmConfig.value" class="btn-sm" type="button">
              {{ state.stepCharState.value.running ? '生成中…' : '▶ 生成状态' }}
            </button>
            <button @click="state.saveCharState()" :disabled="!state.charStateText.value" class="btn-sm" type="button">💾 保存</button>
          </div>
        </div>
        <textarea v-model="state.charStateText.value" rows="12" placeholder="角色初始状态快照…"
          class="w-full border border-[var(--color-parchment-darker)] rounded-lg px-3.5 py-2.5 text-sm font-mono leading-relaxed resize-y bg-white" />
        <div v-if="state.charStateText.value" class="flex items-center gap-2">
          <input v-model="state.revisionGuidance.value.char_state" placeholder="输入 AI 修订建议…" class="flex-1 border border-[var(--color-parchment-darker)] rounded-lg px-3 py-1.5 text-sm" />
          <button @click="state.doRevise('char_state')" :disabled="state.revisionState.value.char_state.running || !state.revisionGuidance.value.char_state || !state.llmConfig.value" class="btn-sm" type="button">
            {{ state.revisionState.value.char_state.running ? '修订中…' : '✏️ AI 修订' }}
          </button>
        </div>
      </div>

      <!-- ④ 世界观 -->
      <div v-show="activeTab === 'world'" class="space-y-3">
        <div class="flex items-center justify-between flex-wrap gap-2">
          <span class="text-sm font-semibold text-[var(--color-leather)]">④ 世界观设定（空间 / 力量体系 / 社会矛盾）</span>
          <div class="flex items-center gap-2">
            <label class="flex items-center gap-1 text-xs cursor-pointer select-none">
              <input type="checkbox" v-model="state.injectCharToWorld.value" class="accent-[var(--color-leather)]" />
              注入角色设定
            </label>
            <button v-if="state.stepMode.value" @click="state.doStepWorld()" :disabled="state.stepWorld.value.running || !state.seedText.value || !state.llmConfig.value" class="btn-sm" type="button">
              {{ state.stepWorld.value.running ? '生成中…' : '▶ 生成世界观' }}
            </button>
            <button @click="state.saveWorldBuilding()" :disabled="!state.worldText.value" class="btn-sm" type="button">💾 保存</button>
          </div>
        </div>
        <textarea v-model="state.worldText.value" rows="12" placeholder="世界观设定…"
          class="w-full border border-[var(--color-parchment-darker)] rounded-lg px-3.5 py-2.5 text-sm font-serif leading-relaxed resize-y bg-white" />
        <div v-if="state.worldText.value" class="flex items-center gap-2">
          <input v-model="state.revisionGuidance.value.world" placeholder="输入 AI 修订建议…" class="flex-1 border border-[var(--color-parchment-darker)] rounded-lg px-3 py-1.5 text-sm" />
          <button @click="state.doRevise('world')" :disabled="state.revisionState.value.world.running || !state.revisionGuidance.value.world || !state.llmConfig.value" class="btn-sm" type="button">
            {{ state.revisionState.value.world.running ? '修订中…' : '✏️ AI 修订' }}
          </button>
        </div>
      </div>

      <!-- ⑤ 剧情骨架 -->
      <div v-show="activeTab === 'plot' && state.workflowMode.value !== 'improv'" class="space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-sm font-semibold text-[var(--color-leather)]">⑤ 三幕剧情骨架（全书 {{ state.numChapters.value }} 章主线走向）</span>
          <div class="flex items-center gap-2">
            <button v-if="state.stepMode.value" @click="state.doStepPlot()" :disabled="state.stepPlot.value.running || !state.seedText.value || !state.charText.value || !state.worldText.value || !state.llmConfig.value" class="btn-sm" type="button">
              {{ state.stepPlot.value.running ? '生成中…' : '▶ 生成情节' }}
            </button>
            <button @click="state.savePlotArch()" :disabled="!state.plotText.value" class="btn-sm" type="button">💾 保存</button>
          </div>
        </div>
        <textarea v-model="state.plotText.value" rows="12" placeholder="三幕剧情架构…"
          class="w-full border border-[var(--color-parchment-darker)] rounded-lg px-3.5 py-2.5 text-sm font-serif leading-relaxed resize-y bg-white" />
        <div v-if="state.plotText.value" class="flex items-center gap-2">
          <input v-model="state.revisionGuidance.value.plot" placeholder="输入 AI 修订建议…" class="flex-1 border border-[var(--color-parchment-darker)] rounded-lg px-3 py-1.5 text-sm" />
          <button @click="state.doRevise('plot')" :disabled="state.revisionState.value.plot.running || !state.revisionGuidance.value.plot || !state.llmConfig.value" class="btn-sm" type="button">
            {{ state.revisionState.value.plot.running ? '修订中…' : '✏️ AI 修订' }}
          </button>
        </div>
      </div>

      <!-- 📄 完整组装视图 -->
      <div v-show="activeTab === 'full'" class="space-y-3">
        <StreamOutput
          :progress="state.arch.value.progress"
          :result="state.arch.value.result"
          :error="state.arch.value.error"
          :running="state.arch.value.running"
          :editable="false"
          :progress-value="state.arch.value.progressValue"
          :cancelable="true"
          placeholder="完整组装后的架构将在此显示…"
          @cancel="state.cancelSSE(state.arch.value)"
        />
      </div>

      <!-- ➕ 续写新卷 -->
      <div v-show="activeTab === 'continue'" class="space-y-3">
        <div class="p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900">
          想在现有剧情后继续扩展新卷/新地图（例如第 10 章之后扩展 190 章）？在此填写续写章数与方向即可追加到架构中。
        </div>
        <div class="flex gap-3 flex-wrap items-end">
          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">续写章节数</label>
            <input v-model.number="state.newChapters.value" type="number" min="1" class="w-24 border border-[var(--color-parchment-darker)] rounded px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">新增角色数</label>
            <input v-model="state.contNumCharacters.value" placeholder="1-3" class="w-24 border border-[var(--color-parchment-darker)] rounded px-2 py-1.5 text-sm" />
          </div>
          <div class="flex-1 min-w-[200px]">
            <label class="block text-xs text-[var(--color-ink-light)] mb-1">续写指导（可选）</label>
            <input v-model="state.continueGuidance.value" placeholder="例如：进入上界新地图，接续第10章悬念…" class="w-full border border-[var(--color-parchment-darker)] rounded px-2 py-1.5 text-sm" />
          </div>
          <button @click="state.doContinueArch()" :disabled="state.continueArch.value.running" class="btn-primary" type="button">
            {{ state.continueArch.value.running ? '生成中…' : '▶ 一键续写新卷' }}
          </button>
        </div>

        <div class="flex gap-3 items-center flex-wrap">
          <button @click="state.doCompressContext()" :disabled="state.compressRunning.value"
            class="px-3 py-1.5 rounded-md text-xs font-medium border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)] text-[var(--color-leather)] hover:bg-[var(--color-parchment-dark)] disabled:opacity-50 cursor-pointer"
            type="button">
            {{ state.compressRunning.value ? '压缩中…' : '🗜️ 压缩前文上下文' }}
          </button>
          <label class="flex items-center gap-1.5 text-xs cursor-pointer select-none">
            <input type="checkbox" v-model="state.compressWorldBuilding.value" class="accent-[var(--color-leather)]" />
            同时压缩世界观
          </label>
          <span v-if="state.compressResult.value" class="text-xs" :class="state.compressResult.value.startsWith('❌') ? 'text-red-600' : 'text-green-700'">
            {{ state.compressResult.value }}
          </span>
        </div>

        <StreamOutput
          :progress="state.continueArch.value.progress"
          :result="state.continueArch.value.result"
          :error="state.continueArch.value.error"
          :running="state.continueArch.value.running"
          :progress-value="state.continueArch.value.progressValue"
          :cancelable="true"
          @cancel="state.cancelSSE(state.continueArch.value)"
        />
      </div>
    </div>
  </StepCard>
</template>
