<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { useConfigStore } from '@/stores/config'
import { systemApi } from '@/api/client'
import ProjectManagerModal from '@/components/ProjectManagerModal.vue'
import ProviderManagerModal from '@/components/ProviderManagerModal.vue'

const route = useRoute()
const projectStore = useProjectStore()
const configStore = useConfigStore()

const projectModalOpen = ref(false)
const providerModalOpen = ref(false)
const onboardingMode = ref(false)
const appVersion = ref('2.1.0')
const hasConfiguredModel = ref(true)
const updateBanner = ref<{ status: string; message: string; version?: string; percent?: number } | null>(null)
const checkingUpdate = ref(false)

let unbindUpdateListener: (() => void) | null = null

async function refreshSystemStatus(autoOpenOnboarding = false) {
  try {
    const res = await systemApi.info()
    appVersion.value = res.data.version || '2.1.0'
    hasConfiguredModel.value = Boolean(res.data.has_configured_model)
    const isDismissed = localStorage.getItem('novelflow_onboarding_dismissed') === 'true'
    if (autoOpenOnboarding && !hasConfiguredModel.value && !isDismissed) {
      onboardingMode.value = true
      providerModalOpen.value = true
    }
  } catch {
    // 忽略启动探测错误
  }
}

function handleCloseProviderModal() {
  localStorage.setItem('novelflow_onboarding_dismissed', 'true')
  onboardingMode.value = false
  providerModalOpen.value = false
}

onMounted(async () => {
  await Promise.all([
    projectStore.loadProjects(),
    projectStore.loadActive(),
    configStore.loadAll(),
    refreshSystemStatus(true),
  ])
  if (window.novelflowDesktop?.onUpdateStatus) {
    unbindUpdateListener = window.novelflowDesktop.onUpdateStatus((payload) => {
      updateBanner.value = payload
      if (payload.status === 'up-to-date' || payload.status === 'error') {
        checkingUpdate.value = false
        setTimeout(() => {
          if (updateBanner.value?.status === payload.status) updateBanner.value = null
        }, 4000)
      } else if (payload.status === 'available' || payload.status === 'downloaded') {
        checkingUpdate.value = false
      }
    })
  }
})

onUnmounted(() => {
  if (unbindUpdateListener) unbindUpdateListener()
})

const navItems = [
  { to: '/', label: '节点工作流画布', short: '画布', icon: '🔗', matchPaths: ['/', '/workflow'] },
  { to: '/workshop', label: '写书工单台', short: '工单', icon: '📋', matchPaths: ['/workshop'] },
  { to: '/reader', label: '整书阅读器', short: '阅读', icon: '📖', matchPaths: ['/reader'] },
  {
    to: '/settings',
    label: '资产与系统设置',
    short: '设置',
    icon: '⚙️',
    matchPaths: ['/settings', '/assets', '/system', '/styles', '/knowledge', '/presets', '/profile', '/config', '/consistency', '/files', '/logs'],
  },
]

function isActiveNav(matchPaths: string[]) {
  return matchPaths.includes(route.path)
}

const activeBookTitle = computed(() => projectStore.activeProject || '未选择书籍')
const visibleBookTabs = computed(() => projectStore.projects.slice(0, 6))

function openProviderModal() {
  onboardingMode.value = false
  providerModalOpen.value = true
}

async function handleCheckUpdates() {
  if (!window.novelflowDesktop?.checkForUpdates) {
    updateBanner.value = {
      status: 'up-to-date',
      message: `当前运行版本 v${appVersion.value}（浏览器调试模式；桌面端安装包支持 GitHub Releases 一键自动更新）`,
    }
    setTimeout(() => { updateBanner.value = null }, 4500)
    return
  }
  checkingUpdate.value = true
  updateBanner.value = { status: 'checking', message: '正在连接 GitHub Releases 检查新版本…' }
  try {
    await window.novelflowDesktop.checkForUpdates()
  } catch (e: unknown) {
    checkingUpdate.value = false
    updateBanner.value = { status: 'error', message: `检查更新失败: ${(e as Error).message}` }
  }
}

async function handleDownloadUpdate() {
  await window.novelflowDesktop?.downloadUpdate()
}

async function handleInstallUpdate() {
  await window.novelflowDesktop?.quitAndInstall()
}

function handleOpenBrowserDownload() {
  const downloadUrl = 'https://ghproxy.net/https://github.com/Xuen-zz/Make-Story-Comfortable/releases/latest'
  if (window.novelflowDesktop?.openExternal) {
    window.novelflowDesktop.openExternal(downloadUrl)
  } else {
    window.open(downloadUrl, '_blank')
  }
}
</script>

<template>
  <div class="h-screen flex flex-col bg-[#0c0d10] text-zinc-200 overflow-hidden">
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- 顶部 ComfyUI-Pro 桌面端多标签工作区栏                               -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <header class="h-11 shrink-0 bg-[#0e1014] border-b border-[#23262f] px-3 flex items-center justify-between gap-2 select-none z-40">
      <!-- 左：品牌 Logo + 多书籍标签切换 -->
      <div class="flex items-center gap-2 min-w-0 flex-1 overflow-x-auto no-scrollbar">
        <div class="flex items-center gap-1.5 shrink-0 pr-2 border-r border-[#23262f]">
          <span class="text-base">🔗</span>
          <span class="font-bold text-xs tracking-wide text-zinc-100">NovelFlow</span>
          <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#181b22] border border-[#272a34] text-zinc-400">
            v{{ appVersion }}
          </span>
        </div>

        <!-- 打开的书籍多标签页 -->
        <div class="flex items-center gap-1 min-w-0">
          <button
            v-for="name in visibleBookTabs"
            :key="name"
            @click="projectStore.activateProject(name)"
            type="button"
            class="px-2.5 py-1 rounded-lg text-xs transition-colors truncate max-w-[150px] cursor-pointer border"
            :class="activeBookTitle === name
              ? 'bg-[#1f232c] border-zinc-500 text-zinc-100 font-semibold'
              : 'bg-[#13151a] border-transparent text-zinc-400 hover:bg-[#1a1d24] hover:text-zinc-200'"
            :title="name"
          >
            📘 {{ name }}
          </button>

          <button
            @click="projectModalOpen = true"
            type="button"
            class="px-2.5 py-1 rounded-lg bg-[#15171c] hover:bg-[#20242e] border border-[#272a34] text-xs text-zinc-300 shrink-0 cursor-pointer"
            title="新建书籍或切换全部书架项目"
          >
            + 书架 ({{ projectStore.projects.length }})
          </button>
        </div>
      </div>

      <!-- 右：独立模型中心 + 更新按钮 -->
      <div class="flex items-center gap-2 shrink-0">
        <button
          @click="openProviderModal"
          type="button"
          class="px-2.5 py-1 rounded-lg border text-xs font-semibold flex items-center gap-1.5 cursor-pointer transition-colors"
          :class="!hasConfiguredModel
            ? 'bg-amber-500/15 border-amber-500/60 text-amber-200 animate-pulse'
            : 'bg-[#181b22] hover:bg-[#222631] border-[#2c303b] text-zinc-200'"
          title="独立配置 DeepSeek / Gemini / OpenAI / Ollama 等模型提供商"
        >
          <span>📦 模型中心</span>
          <span
            class="w-2 h-2 rounded-full"
            :class="hasConfiguredModel ? 'bg-emerald-400' : 'bg-amber-400'"
          />
        </button>

        <button
          @click="handleCheckUpdates"
          :disabled="checkingUpdate"
          type="button"
          class="px-2.5 py-1 rounded-lg bg-[#181b22] hover:bg-[#222631] border border-[#2c303b] text-xs text-zinc-300 cursor-pointer disabled:opacity-50"
          title="检查 GitHub Releases 最新版本更新"
        >
          {{ checkingUpdate ? '⏳ 检查中…' : '🔄 检查更新' }}
        </button>
      </div>
    </header>

    <!-- 版本自动更新通知条 -->
    <div
      v-if="updateBanner"
      class="shrink-0 px-4 py-1.5 bg-[#151a18] border-b border-emerald-700/50 text-xs flex items-center justify-between gap-3"
    >
      <span class="text-emerald-300">
        🚀 {{ updateBanner.message }}
        <template v-if="typeof updateBanner.percent === 'number'">
          ({{ Math.round(updateBanner.percent) }}%)
        </template>
      </span>
      <div class="flex items-center gap-2 shrink-0">
        <button
          v-if="updateBanner.status === 'available'"
          @click="handleDownloadUpdate"
          type="button"
          class="px-2.5 py-0.5 rounded bg-emerald-500 text-zinc-950 font-bold cursor-pointer"
        >
          立即下载更新
        </button>
        <button
          v-if="updateBanner.status === 'downloaded'"
          @click="handleInstallUpdate"
          type="button"
          class="px-2.5 py-0.5 rounded bg-emerald-400 text-zinc-950 font-bold cursor-pointer"
        >
          重启并安装 v{{ updateBanner.version }}
        </button>
        <button
          v-if="updateBanner.status === 'available' || updateBanner.status === 'error'"
          @click="handleOpenBrowserDownload"
          type="button"
          class="px-2.5 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-emerald-400 border border-emerald-500/30 font-medium cursor-pointer"
          title="使用系统默认浏览器直接下载完整安装包"
        >
          浏览器极速下载
        </button>
        <button @click="updateBanner = null" type="button" class="text-zinc-400 hover:text-white cursor-pointer">✕</button>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- 下方主体：极简左轨 Icon Rail + 全高度工作区视图                     -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div class="flex-1 min-h-0 flex overflow-hidden">
      <aside class="w-14 shrink-0 bg-[#0e1014] border-r border-[#23262f] py-2.5 flex flex-col items-center justify-between select-none z-30">
        <nav class="flex flex-col items-center gap-2 w-full px-1.5">
          <router-link
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="w-full py-2 rounded-xl flex flex-col items-center justify-center gap-0.5 text-[10px] transition-all"
            :class="
              isActiveNav(item.matchPaths)
                ? 'bg-[#222631] text-zinc-100 border border-zinc-600 font-bold'
                : 'text-zinc-400 hover:bg-[#171a21] hover:text-zinc-200 border border-transparent'
            "
            :title="item.label"
          >
            <span class="text-base leading-none">{{ item.icon }}</span>
            <span>{{ item.short }}</span>
          </router-link>
        </nav>

        <button
          @click="openProviderModal"
          type="button"
          class="w-10 h-10 rounded-xl bg-[#15171c] hover:bg-[#20242e] border border-[#272a34] flex items-center justify-center text-sm cursor-pointer"
          title="模型调度与存储目录设置"
        >
          🔑
        </button>
      </aside>

      <!-- 主视图区 -->
      <main class="flex-1 min-w-0 h-full overflow-y-auto">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </main>
    </div>

    <!-- 全局书架与项目管理弹窗 -->
    <ProjectManagerModal
      :open="projectModalOpen"
      @close="projectModalOpen = false"
    />

    <!-- 独立模型与提供商管理中心弹窗 -->
    <ProviderManagerModal
      :open="providerModalOpen"
      :onboarding-mode="onboardingMode"
      @close="handleCloseProviderModal"
      @synced="refreshSystemStatus(false)"
    />
  </div>
</template>
