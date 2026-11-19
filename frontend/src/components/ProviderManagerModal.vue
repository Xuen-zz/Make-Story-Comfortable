<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { providersApi, systemApi } from '@/api/client'
import { useConfigStore } from '@/stores/config'

const props = defineProps<{
  open: boolean
  onboardingMode?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'synced'): void
}>()

const configStore = useConfigStore()

interface ProviderTemplate {
  id: string
  name: string
  interface_format: string
  base_url: string
  default_models: string[]
  requires_key: boolean
  advanced?: boolean
  available?: boolean
  badge?: string
}

const templates = ref<ProviderTemplate[]>([])
const savedProviders = ref<any[]>([])
const activeId = ref('deepseek')
const showAdvanced = ref(false)

const formName = ref('')
const formFormat = ref('OpenAI')
const formBaseUrl = ref('')
const formApiKey = ref('')
const showKey = ref(false)
const availableModels = ref<string[]>([])
const selectedModels = ref<string[]>([])
const customModelInput = ref('')

const fetching = ref(false)
const testing = ref(false)
const saving = ref(false)
const statusText = ref('')
const testResult = ref<{ ok: boolean; latency_ms?: number; reply?: string; error?: string } | null>(null)

// 数据存储目录
const dataDir = ref('')
const booksRoot = ref('')
const savingFolder = ref(false)
const hasNativeFolderPicker = Boolean(typeof window !== 'undefined' && window.novelflowDesktop?.selectFolder)

async function loadProvidersAndInfo() {
  try {
    const [pRes, sysRes] = await Promise.all([
      providersApi.list(),
      systemApi.info(),
    ])
    templates.value = pRes.data.templates || []
    savedProviders.value = pRes.data.saved || []
    dataDir.value = sysRes.data.data_dir || ''
    booksRoot.value = sysRes.data.books_root || ''
    selectProvider(activeId.value)
  } catch (e) {
    console.error('加载提供商失败:', e)
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) loadProvidersAndInfo()
  },
  { immediate: true },
)

const visibleTemplates = computed(() =>
  templates.value.filter(t => showAdvanced.value || !t.advanced || savedProviders.value.some(s => s.id === t.id)),
)

function selectProvider(id: string) {
  activeId.value = id
  statusText.value = ''
  testResult.value = null
  const tpl = templates.value.find(t => t.id === id)
  const saved = savedProviders.value.find(s => s.id === id)

  formName.value = saved?.name || tpl?.name || id
  formFormat.value = saved?.interface_format || tpl?.interface_format || 'OpenAI'
  formBaseUrl.value = saved?.base_url ?? tpl?.base_url ?? ''
  formApiKey.value = saved?.api_key || ''

  const defaults = tpl?.default_models || []
  const savedModels = saved?.selected_models || []
  availableModels.value = Array.from(new Set([...defaults, ...savedModels]))
  selectedModels.value = savedModels.length ? [...savedModels] : [...defaults]
}

function isSaved(id: string) {
  return savedProviders.value.some(s => s.id === id && (s.selected_models?.length > 0))
}

function toggleModel(m: string) {
  if (selectedModels.value.includes(m)) {
    selectedModels.value = selectedModels.value.filter(x => x !== m)
  } else {
    selectedModels.value = [...selectedModels.value, m]
  }
}

function addManualModel() {
  const m = customModelInput.value.trim()
  if (!m) return
  if (!availableModels.value.includes(m)) availableModels.value.push(m)
  if (!selectedModels.value.includes(m)) selectedModels.value.push(m)
  customModelInput.value = ''
}

async function handleFetchModels() {
  fetching.value = true
  statusText.value = ''
  try {
    const res = await providersApi.fetchModels({
      interface_format: formFormat.value,
      base_url: formBaseUrl.value,
      api_key: formApiKey.value,
    })
    if (res.data.success) {
      const list = (res.data.models || []) as string[]
      availableModels.value = Array.from(new Set([...list, ...selectedModels.value]))
      statusText.value = `✅ 成功拉取到 ${list.length} 个可用模型`
    } else {
      statusText.value = `⚠️ ${res.data.error || '未拉取到模型'}`
    }
  } catch (e: unknown) {
    statusText.value = `❌ 拉取异常: ${(e as Error).message}`
  } finally {
    fetching.value = false
  }
}

async function handleTestConnection() {
  const modelToTest = selectedModels.value[0] || availableModels.value[0] || ''
  testing.value = true
  testResult.value = null
  try {
    const res = await providersApi.testConnection({
      interface_format: formFormat.value,
      base_url: formBaseUrl.value,
      api_key: formApiKey.value,
      model_name: modelToTest,
    })
    testResult.value = res.data
  } catch (e: unknown) {
    testResult.value = { ok: false, error: (e as Error).message }
  } finally {
    testing.value = false
  }
}

async function handleSaveProvider() {
  saving.value = true
  statusText.value = ''
  try {
    const res = await providersApi.save({
      id: activeId.value,
      name: formName.value,
      interface_format: formFormat.value,
      base_url: formBaseUrl.value,
      api_key: formApiKey.value,
      selected_models: selectedModels.value,
      enabled: true,
    })
    await configStore.loadAll()
    await loadProvidersAndInfo()
    statusText.value = res.data.message || '✅ 已保存并同步模型列表'
    emit('synced')
  } catch (e: unknown) {
    statusText.value = `❌ 保存失败: ${(e as Error).message}`
  } finally {
    saving.value = false
  }
}

async function handlePickBooksFolder() {
  if (window.novelflowDesktop?.selectFolder) {
    const chosen = await window.novelflowDesktop.selectFolder()
    if (chosen) {
      booksRoot.value = chosen
      await saveBooksFolder()
    }
  }
}

async function saveBooksFolder() {
  if (!booksRoot.value.trim()) return
  savingFolder.value = true
  try {
    const res = await systemApi.setBooksRoot(booksRoot.value.trim())
    booksRoot.value = res.data.books_root
    statusText.value = `✅ 小说默认存储目录已更新为：${booksRoot.value}`
  } catch (e: unknown) {
    statusText.value = `❌ 目录设置失败: ${(e as Error).message}`
  } finally {
    savingFolder.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[110] bg-black/80 backdrop-blur-xs flex items-center justify-center p-4"
      @click.self="emit('close')"
    >
      <div class="w-full max-w-5xl max-h-[88vh] rounded-2xl border border-[#2c303b] bg-[#15171c] text-zinc-200 shadow-2xl flex flex-col overflow-hidden">
        <!-- 顶栏 -->
        <div class="px-5 py-3.5 bg-[#0e1014] border-b border-[#23262f] flex items-center justify-between gap-3">
          <div>
            <div class="text-base font-bold text-zinc-100 flex items-center gap-2">
              <span>📦 模型与 API 提供商管理中心</span>
              <span v-if="onboardingMode" class="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                首次使用引导 · 配置 1 个模型即可开写
              </span>
            </div>
            <p class="text-xs text-zinc-400 mt-0.5">
              独立模型调度底座（支持云端 API Key、本地 Ollama/LM Studio 与可选高阶本机桥接），保存后即时同步至所有工作流节点。
            </p>
          </div>
          <button
            @click="emit('close')"
            type="button"
            class="px-3 py-1.5 rounded-lg bg-[#1b1e25] hover:bg-[#252934] border border-[#2c303b] text-xs font-semibold cursor-pointer"
          >
            关闭 ✕
          </button>
        </div>

        <!-- 主体双栏 -->
        <div class="flex-1 min-h-0 flex flex-col md:flex-row overflow-hidden">
          <!-- 左：Provider 列表 -->
          <aside class="w-full md:w-64 shrink-0 bg-[#0e1014] border-b md:border-b-0 md:border-r border-[#23262f] p-3 overflow-y-auto space-y-1.5">
            <button
              v-for="tpl in visibleTemplates"
              :key="tpl.id"
              @click="selectProvider(tpl.id)"
              type="button"
              class="w-full text-left px-3 py-2.5 rounded-xl border transition-all cursor-pointer"
              :class="activeId === tpl.id
                ? 'bg-[#1f222a] border-zinc-400 text-zinc-100'
                : 'bg-[#15171c] border-[#23262f] text-zinc-300 hover:border-zinc-600'"
            >
              <div class="flex items-center justify-between gap-1">
                <span class="text-xs font-bold truncate">{{ tpl.name }}</span>
                <span v-if="isSaved(tpl.id)" class="w-2 h-2 rounded-full bg-emerald-400 shrink-0" title="已配置可用模型" />
              </div>
              <div class="text-[10px] text-zinc-400 mt-0.5 truncate">{{ tpl.badge }}</div>
            </button>

            <div class="pt-2 border-t border-[#23262f]">
              <label class="flex items-center gap-2 text-[11px] text-zinc-400 cursor-pointer select-none px-1">
                <input v-model="showAdvanced" type="checkbox" class="accent-emerald-500" />
                <span>显示高级本地桥接（Antigravity）</span>
              </label>
            </div>
          </aside>

          <!-- 右：Provider 配置与模型拉取 -->
          <section class="flex-1 min-w-0 overflow-y-auto p-5 space-y-4">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <label class="space-y-1">
                <span class="text-zinc-400 font-medium">显示名称</span>
                <input v-model="formName" type="text" class="w-full px-3 py-2 rounded-lg border bg-[#0e1014]" />
              </label>
              <label class="space-y-1">
                <span class="text-zinc-400 font-medium">接口协议格式</span>
                <select v-model="formFormat" class="w-full px-3 py-2 rounded-lg border bg-[#0e1014]">
                  <option value="OpenAI">OpenAI 兼容 (/v1/chat/completions)</option>
                  <option value="Google">Google Gemini 原生</option>
                  <option value="Ollama">Ollama 本地 (/api)</option>
                  <option value="ML Studio">LM Studio 本地</option>
                  <option value="Codex">Codex / Antigravity 本地 CLI</option>
                </select>
              </label>

              <label class="sm:col-span-2 space-y-1">
                <span class="text-zinc-400 font-medium">API Base URL（留空或按需填兼容中转地址）</span>
                <input
                  v-model="formBaseUrl"
                  type="text"
                  placeholder="例如 https://api.deepseek.com/v1 或 http://127.0.0.1:11434"
                  class="w-full px-3 py-2 rounded-lg border bg-[#0e1014] font-mono"
                />
              </label>

              <label class="sm:col-span-2 space-y-1">
                <span class="text-zinc-400 font-medium">API Key（本地 Ollama/LM Studio/agy 可留空）</span>
                <div class="flex gap-2">
                  <input
                    v-model="formApiKey"
                    :type="showKey ? 'text' : 'password'"
                    placeholder="sk-..."
                    class="flex-1 px-3 py-2 rounded-lg border bg-[#0e1014] font-mono"
                  />
                  <button
                    @click="showKey = !showKey"
                    type="button"
                    class="px-3 rounded-lg bg-[#1d2028] border border-[#2c303b] text-xs cursor-pointer"
                  >
                    {{ showKey ? '隐藏' : '显示' }}
                  </button>
                </div>
              </label>
            </div>

            <!-- 模型自动拉取 & 测速条 -->
            <div class="flex items-center gap-2 flex-wrap">
              <button
                @click="handleFetchModels"
                :disabled="fetching"
                type="button"
                class="px-3.5 py-2 rounded-lg bg-[#1d2028] hover:bg-[#272b36] border border-[#343946] text-xs font-semibold text-zinc-100 disabled:opacity-50 cursor-pointer"
              >
                {{ fetching ? '⏳ 正在拉取模型…' : '🔄 自动拉取可用模型列表' }}
              </button>
              <button
                @click="handleTestConnection"
                :disabled="testing"
                type="button"
                class="px-3.5 py-2 rounded-lg bg-[#1d2028] hover:bg-[#272b36] border border-[#343946] text-xs font-semibold text-emerald-300 disabled:opacity-50 cursor-pointer"
              >
                {{ testing ? '⏳ 测速中…' : '⚡ 一键测试连通性' }}
              </button>
              <button
                @click="handleSaveProvider"
                :disabled="saving"
                type="button"
                class="ml-auto px-4 py-2 rounded-lg bg-zinc-100 hover:bg-white text-zinc-950 text-xs font-bold cursor-pointer"
              >
                {{ saving ? '保存中…' : `💾 保存并同步勾选模型 (${selectedModels.length})` }}
              </button>
            </div>

            <!-- 反馈 & 测速结果 -->
            <div v-if="statusText" class="px-3 py-2 rounded-lg bg-[#1b1e25] border border-[#2c303b] text-xs text-zinc-200">
              {{ statusText }}
            </div>
            <div
              v-if="testResult"
              class="px-3 py-2 rounded-lg border text-xs"
              :class="testResult.ok ? 'bg-emerald-950/50 border-emerald-700/60 text-emerald-300' : 'bg-red-950/50 border-red-700/60 text-red-300'"
            >
              <template v-if="testResult.ok">
                ✅ 连通正常！延迟 {{ testResult.latency_ms }}ms · 回复预览：「{{ testResult.reply }}」
              </template>
              <template v-else>
                ❌ 连接失败 ({{ testResult.latency_ms }}ms)：{{ testResult.error }}
              </template>
            </div>

            <!-- 可勾选同步模型清单 -->
            <div class="rounded-xl border border-[#262932] bg-[#0e1014] p-3.5 space-y-2.5">
              <div class="flex items-center justify-between gap-2">
                <span class="text-xs font-bold text-zinc-200">勾选需要暴露给工作流节点的模型：</span>
                <div class="flex gap-1.5">
                  <input
                    v-model="customModelInput"
                    @keyup.enter="addManualModel"
                    type="text"
                    placeholder="手动补充模型 ID…"
                    class="px-2 py-1 rounded bg-[#15171c] border border-[#2c303b] text-[11px] font-mono"
                  />
                  <button @click="addManualModel" type="button" class="px-2.5 py-1 rounded bg-[#1d2028] border border-[#2c303b] text-[11px] cursor-pointer">
                    + 添加
                  </button>
                </div>
              </div>

              <div v-if="availableModels.length === 0" class="text-xs text-zinc-500 py-3 text-center">
                暂无候选模型，点击上方「🔄 自动拉取可用模型列表」或右侧手动输入模型 ID。
              </div>
              <div v-else class="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto">
                <button
                  v-for="m in availableModels"
                  :key="m"
                  @click="toggleModel(m)"
                  type="button"
                  class="px-2.5 py-1 rounded-lg border text-[11px] font-mono cursor-pointer transition-colors"
                  :class="selectedModels.includes(m)
                    ? 'bg-emerald-500/20 border-emerald-500/70 text-emerald-200 font-semibold'
                    : 'bg-[#15171c] border-[#272a34] text-zinc-400 hover:border-zinc-500'"
                >
                  {{ selectedModels.includes(m) ? '✓ ' : '+ ' }}{{ m }}
                </button>
              </div>
            </div>

            <!-- 程序与小说数据目录设置 -->
            <div class="rounded-xl border border-[#262932] bg-[#0e1014] p-3.5 space-y-2 text-xs">
              <div class="font-bold text-zinc-200">📁 独立存储路径（版本更新 100% 保留稿件与密钥）</div>
              <div class="text-[11px] text-zinc-400">
                配置与工作流存储目录：<span class="font-mono text-zinc-300">{{ dataDir }}</span>
              </div>
              <div class="flex items-center gap-2">
                <input
                  v-model="booksRoot"
                  type="text"
                  placeholder="默认小说输出文件夹…"
                  class="flex-1 px-2.5 py-1.5 rounded-lg border bg-[#15171c] font-mono text-[11px]"
                />
                <button
                  v-if="hasNativeFolderPicker"
                  @click="handlePickBooksFolder"
                  type="button"
                  class="px-3 py-1.5 rounded-lg bg-[#1d2028] border border-[#2c303b] text-xs cursor-pointer"
                >
                  📂 浏览选择
                </button>
                <button
                  @click="saveBooksFolder"
                  :disabled="savingFolder"
                  type="button"
                  class="px-3 py-1.5 rounded-lg bg-[#242833] border border-[#343946] text-xs font-semibold cursor-pointer"
                >
                  保存路径
                </button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  </Teleport>
</template>
