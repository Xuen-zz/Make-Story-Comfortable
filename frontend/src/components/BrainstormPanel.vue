<script setup lang="ts">
import { ref, nextTick, onMounted, computed } from 'vue'
import { postSSE } from '@/api/client'
import { brainstormApi } from '@/api/client'
import { useConfigStore } from '@/stores/config'
import { useProjectStore } from '@/stores/project'
import { useProfileExtractor } from '@/composables/useProfileExtractor'
import ProfileExtractBar from '@/components/ProfileExtractBar.vue'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

const props = withDefaults(defineProps<{
  compact?: boolean
}>(), {
  compact: false
})

const emit = defineEmits<{
  (e: 'close'): void
}>()

const configStore = useConfigStore()
const projectStore = useProjectStore()

const llmConfig = ref('')
const messages = ref<ChatMessage[]>([])
const userInput = ref('')
const streaming = ref(false)
const streamContent = ref('')
const chatContainerRef = ref<HTMLElement>()

// Context toggles
const includeCoreSeed = ref(true)
const includeCharacters = ref(true)
const includeWorldBuilding = ref(true)
const includePlot = ref(true)
const includeBlueprint = ref(false)
const includeCharacterState = ref(false)
const extraContext = ref('')
const showSettings = ref(false)
const profiler = useProfileExtractor()

// Discussion mode
const discussionMode = ref('advisor')
const modeOptions = [
  { value: 'casual', label: '轻松闲聊', desc: '像朋友聊天，简短随意' },
  { value: 'advisor', label: '专业顾问', desc: '结构化建议，深度分析' },
  { value: 'brainstorm', label: '头脑风暴', desc: '多角色视角，观点碰撞' },
  { value: 'devil', label: '魔鬼代言人', desc: '挑战想法，找出剧情弱点' },
  { value: 'roleplay', label: '角色扮演', desc: '以小说角色身份对话对戏' },
]

const canSend = computed(() => userInput.value.trim() && llmConfig.value && !streaming.value)

function scrollToBottom() {
  nextTick(() => {
    if (chatContainerRef.value) {
      chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight
    }
  })
}

function sendMessage() {
  const text = userInput.value.trim()
  if (!text || streaming.value) return

  // 异步提取偏好（不阻塞发送）
  profiler.tryExtract(text, llmConfig.value)

  messages.value.push({ role: 'user', content: text })
  userInput.value = ''
  streaming.value = true
  streamContent.value = ''

  scrollToBottom()

  postSSE(
    brainstormApi.chatUrl(),
    {
      llm_config_name: llmConfig.value,
      filepath: projectStore.filepath,
      messages: messages.value,
      include_core_seed: includeCoreSeed.value,
      include_characters: includeCharacters.value,
      include_world_building: includeWorldBuilding.value,
      include_plot: includePlot.value,
      include_blueprint: includeBlueprint.value,
      include_character_state: includeCharacterState.value,
      extra_context: extraContext.value,
      discussion_mode: discussionMode.value,
    },
    (_msg, _value, content) => {
      if (content) {
        streamContent.value = content
        scrollToBottom()
      }
    },
    (content) => {
      const finalContent = content || streamContent.value
      messages.value.push({ role: 'assistant', content: finalContent })
      streamContent.value = ''
    },
    (err) => {
      messages.value.push({ role: 'assistant', content: `❌ ${err}` })
      streamContent.value = ''
      streaming.value = false
    },
    () => {
      streaming.value = false
      scrollToBottom()
    },
  )
}

function clearChat() {
  messages.value = []
  streamContent.value = ''
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

const copiedIdx = ref<number | null>(null)
function copyContent(text: string, idx: number) {
  navigator.clipboard.writeText(text)
  copiedIdx.value = idx
  setTimeout(() => {
    if (copiedIdx.value === idx) copiedIdx.value = null
  }, 1500)
}

onMounted(async () => {
  await Promise.all([configStore.loadAll(), projectStore.loadActive()])
  if (configStore.llmChoices.length) llmConfig.value = configStore.llmChoices[0]
})
</script>

<template>
  <div
    class="flex flex-col bg-white"
    :class="compact ? 'h-full p-3.5' : 'h-[calc(100vh-120px)] max-w-4xl mx-auto px-4 py-4 rounded-xl border border-[var(--color-parchment-darker)] shadow-sm'"
  >
    <!-- Header -->
    <div class="flex items-center justify-between mb-2 pb-2 border-b border-[var(--color-parchment-dark)]">
      <div class="flex items-center gap-2">
        <h2 class="font-bold flex items-center gap-1.5" :class="compact ? 'text-base' : 'text-xl'" style="color: var(--color-ink)">
          <span>💬</span>
          <span>AI 创作聊天助手</span>
        </h2>
        <!-- 讨论模式选择 -->
        <select
          v-model="discussionMode"
          class="border border-[var(--color-parchment-darker)] rounded px-2 py-1 text-xs bg-[var(--color-parchment)] text-[var(--color-ink)] font-medium cursor-pointer"
          title="切换 AI 交互模式"
        >
          <option v-for="m in modeOptions" :key="m.value" :value="m.value">
            {{ m.label }}
          </option>
        </select>
      </div>

      <div class="flex items-center gap-1.5">
        <button
          @click="showSettings = !showSettings"
          class="px-2 py-1 rounded text-xs border border-[var(--color-parchment-darker)] hover:bg-[var(--color-parchment)] transition-colors"
          type="button"
          :title="showSettings ? '隐藏设定与模型选项' : '配置上下文与模型'"
        >
          {{ showSettings ? '收起配置' : '⚙️ 设定' }}
        </button>
        <button
          @click="clearChat"
          :disabled="streaming"
          class="px-2 py-1 rounded text-xs border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors"
          type="button"
          title="清空当前聊天记录"
        >
          清空
        </button>
        <button
          v-if="compact"
          @click="emit('close')"
          class="p-1 rounded text-xs text-[var(--color-ink-light)] hover:bg-gray-100 hover:text-gray-800 transition-colors"
          type="button"
          title="收起聊天侧栏"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- Settings Panel (Collapsible) -->
    <Transition name="slide">
      <div
        v-if="showSettings"
        class="rounded-lg border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)] p-3 mb-2 space-y-2 text-xs"
      >
        <div class="flex gap-2">
          <div class="flex-1">
            <label class="block text-[var(--color-ink-light)] mb-1">使用模型</label>
            <select
              v-model="llmConfig"
              class="w-full border border-[var(--color-parchment-darker)] rounded px-2 py-1 text-xs bg-white"
            >
              <option v-for="c in configStore.llmChoices" :key="c" :value="c">{{ c }}</option>
            </select>
          </div>
        </div>

        <div>
          <label class="block text-[var(--color-ink-light)] mb-1 font-medium">注入本小说上下文：</label>
          <div class="grid grid-cols-3 gap-1">
            <label class="inline-flex items-center gap-1 cursor-pointer">
              <input type="checkbox" v-model="includeCoreSeed" class="rounded" />
              <span>核心种子</span>
            </label>
            <label class="inline-flex items-center gap-1 cursor-pointer">
              <input type="checkbox" v-model="includeCharacters" class="rounded" />
              <span>角色动力学</span>
            </label>
            <label class="inline-flex items-center gap-1 cursor-pointer">
              <input type="checkbox" v-model="includeWorldBuilding" class="rounded" />
              <span>世界观</span>
            </label>
            <label class="inline-flex items-center gap-1 cursor-pointer">
              <input type="checkbox" v-model="includePlot" class="rounded" />
              <span>剧情主线</span>
            </label>
            <label class="inline-flex items-center gap-1 cursor-pointer">
              <input type="checkbox" v-model="includeBlueprint" class="rounded" />
              <span>章节大纲</span>
            </label>
            <label class="inline-flex items-center gap-1 cursor-pointer">
              <input type="checkbox" v-model="includeCharacterState" class="rounded" />
              <span>角色状态</span>
            </label>
          </div>
        </div>

        <div>
          <textarea
            v-model="extraContext"
            rows="2"
            class="w-full border border-[var(--color-parchment-darker)] rounded p-1.5 text-xs resize-none bg-white"
            placeholder="可选：输入额外参考资料或特定约束..."
          />
        </div>
      </div>
    </Transition>

    <!-- Chat Messages Scroll Area -->
    <div
      ref="chatContainerRef"
      class="flex-1 overflow-y-auto rounded-lg border border-[var(--color-parchment-dark)] bg-neutral-50/60 p-3 space-y-3"
    >
      <!-- Empty state -->
      <div
        v-if="messages.length === 0 && !streaming"
        class="flex flex-col items-center justify-center h-full text-[var(--color-ink-light)] opacity-70 text-center px-4"
      >
        <span class="text-3xl mb-2">💡</span>
        <p class="text-xs font-semibold text-[var(--color-ink)]">与 AI 军师边写边聊</p>
        <p class="text-[11px] mt-1 leading-relaxed">
          打磨剧情反转 · 润色对话台词 · 挑漏洞挑刺 · 角色即兴对戏
        </p>
        <div class="mt-3 flex flex-wrap gap-1 justify-center">
          <button
            v-for="m in modeOptions"
            :key="m.value"
            @click="discussionMode = m.value"
            class="text-[11px] px-2 py-0.5 rounded border border-gray-300 bg-white hover:border-amber-600 transition-colors"
            :class="discussionMode === m.value ? 'border-amber-700 bg-amber-50 text-amber-900 font-medium' : ''"
          >
            {{ m.label }}
          </button>
        </div>
      </div>

      <!-- Messages -->
      <div
        v-for="(msg, i) in messages"
        :key="i"
        class="flex flex-col"
        :class="msg.role === 'user' ? 'items-end' : 'items-start'"
      >
        <div
          class="max-w-[92%] rounded-xl px-3.5 py-2.5 text-xs leading-relaxed whitespace-pre-wrap shadow-sm group relative"
          :class="
            msg.role === 'user'
              ? 'bg-[var(--color-leather)] text-white'
              : 'bg-white text-[var(--color-ink)] border border-[var(--color-parchment-darker)]'
          "
        >
          <div>{{ msg.content }}</div>
          <!-- 一键复制按钮 -->
          <div
            v-if="msg.role === 'assistant'"
            class="mt-1 pt-1 border-t border-gray-100 flex justify-end"
          >
            <button
              @click="copyContent(msg.content, i)"
              class="text-[10px] text-gray-400 hover:text-amber-800 flex items-center gap-1 transition-colors"
              title="复制回答内容"
            >
              <span>{{ copiedIdx === i ? '✓ 已复制' : '📋 复制' }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Streaming message -->
      <div v-if="streaming && streamContent" class="flex flex-col items-start">
        <div
          class="max-w-[92%] rounded-xl px-3.5 py-2.5 text-xs leading-relaxed whitespace-pre-wrap bg-white text-[var(--color-ink)] border border-amber-300 shadow-sm"
        >
          {{ streamContent }}
          <span class="inline-block w-1.5 h-3.5 ml-0.5 bg-amber-700 animate-pulse align-middle" />
        </div>
      </div>

      <!-- Loading indicator -->
      <div v-if="streaming && !streamContent" class="flex justify-start">
        <div class="rounded-xl px-3 py-2 bg-white border border-gray-200 text-gray-500 text-xs italic flex items-center gap-1.5">
          <span>Gemini 思考中</span>
          <span class="inline-block w-1.5 h-3 bg-amber-700 animate-pulse" />
        </div>
      </div>
    </div>

    <!-- 偏好提取确认条 -->
    <ProfileExtractBar
      :show="profiler.showConfirm.value"
      :preferences="profiler.extractedPrefs.value"
      :confirm-msg="profiler.confirmMsg.value"
      @confirm="profiler.confirmAppend()"
      @dismiss="profiler.dismissExtract()"
    />

    <!-- Input Box -->
    <div class="mt-2.5 flex gap-1.5">
      <textarea
        v-model="userInput"
        @keydown="handleKeydown"
        :disabled="streaming"
        rows="2"
        class="flex-1 border border-[var(--color-parchment-darker)] rounded-lg px-3 py-2 text-xs resize-none focus:outline-none focus:ring-1 focus:ring-[var(--color-leather)] bg-white disabled:opacity-50"
        :placeholder="`在「${modeOptions.find(m => m.value === discussionMode)?.label}」模式下向 AI 提问... (Enter 发送)`"
      />
      <button
        @click="sendMessage"
        :disabled="!canSend"
        class="px-3.5 self-end rounded-lg text-xs font-semibold h-[42px] disabled:opacity-40 transition-colors flex items-center justify-center text-white"
        style="background-color: var(--color-leather);"
        type="button"
      >
        {{ streaming ? '...' : '发送' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: all 0.2s ease;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
  overflow: hidden;
}
.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>
