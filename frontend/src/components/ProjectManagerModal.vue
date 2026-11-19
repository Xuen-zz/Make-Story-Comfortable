<script setup lang="ts">
import { ref, watch } from 'vue'
import { useProjectStore } from '@/stores/project'
import { projectsApi } from '@/api/client'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const projectStore = useProjectStore()
const tab = ref<'list' | 'create' | 'backups'>('list')
const newName = ref('')
const newPath = ref('')
const creating = ref(false)
const deleting = ref(false)
const discovering = ref(false)
const statusMsg = ref('')

// 备份相关
const backups = ref<{ id: string; timestamp: string; note: string; size_mb: number }[]>([])
const backupNote = ref('')
const backupLoading = ref(false)

async function loadBackups() {
  const name = projectStore.activeProject
  if (!name) return
  try {
    const res = await projectsApi.listBackups(name)
    backups.value = res.data.backups
  } catch {
    backups.value = []
  }
}

watch(() => props.open, (isOpen) => {
  if (isOpen) {
    statusMsg.value = ''
    if (tab.value === 'backups') loadBackups()
  }
})

watch(tab, (t) => {
  if (t === 'backups') loadBackups()
})

async function onSelectProject(name: string) {
  if (!name || name === projectStore.activeProject) {
    emit('close')
    return
  }
  try {
    await projectStore.activateProject(name)
    statusMsg.value = `✅ 已切换到「${name}」`
    setTimeout(() => emit('close'), 300)
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  }
}

async function onCreate() {
  if (!newName.value.trim()) return
  creating.value = true
  statusMsg.value = ''
  try {
    await projectStore.createProject(newName.value.trim(), newPath.value.trim())
    newName.value = ''
    newPath.value = ''
    tab.value = 'list'
    statusMsg.value = '✅ 新书项目创建成功'
    setTimeout(() => emit('close'), 300)
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  } finally {
    creating.value = false
  }
}

async function onDiscover() {
  discovering.value = true
  try {
    const res = await projectStore.discoverProjects()
    statusMsg.value = res.message
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  } finally {
    discovering.value = false
  }
}

async function onDelete(name: string) {
  if (!confirm(`确定要删除项目「${name}」吗？项目文件将被移至 trash 目录。`)) return
  deleting.value = true
  try {
    await projectStore.deleteProject(name)
    statusMsg.value = `✅ 已删除「${name}」`
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  } finally {
    deleting.value = false
  }
}

async function onCreateBackup() {
  const name = projectStore.activeProject
  if (!name) return
  backupLoading.value = true
  try {
    const res = await projectsApi.createBackup(name, backupNote.value.trim())
    statusMsg.value = res.data.message
    backupNote.value = ''
    await loadBackups()
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  } finally {
    backupLoading.value = false
  }
}

async function onRestoreBackup(backupId: string) {
  const name = projectStore.activeProject
  if (!name) return
  if (!confirm(`确定要还原到备份「${backupId}」吗？当前状态会自动备份后再还原。`)) return
  backupLoading.value = true
  try {
    const res = await projectsApi.restoreBackup(name, backupId)
    statusMsg.value = res.data.message
    await loadBackups()
    await projectStore.loadActive()
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  } finally {
    backupLoading.value = false
  }
}

async function onDeleteBackup(backupId: string) {
  const name = projectStore.activeProject
  if (!name) return
  if (!confirm(`确定要删除备份「${backupId}」吗？`)) return
  try {
    await projectsApi.deleteBackup(name, backupId)
    await loadBackups()
  } catch (e: unknown) {
    statusMsg.value = `❌ ${(e as Error).message}`
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[100] bg-black/50 backdrop-blur-xs flex items-center justify-center p-4"
      @click.self="emit('close')"
    >
      <div class="w-full max-w-2xl rounded-2xl border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)] shadow-2xl overflow-hidden">
        <!-- 头部 -->
        <div class="px-5 py-3.5 bg-[var(--color-spine)] text-[var(--color-parchment)] flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-lg">📚</span>
            <h3 class="font-bold text-base text-[var(--color-gold-light)]">书架与项目管理</h3>
          </div>
          <button
            @click="emit('close')"
            type="button"
            class="text-[var(--color-parchment-dark)] hover:text-white text-lg leading-none px-1.5 cursor-pointer"
          >
            ✕
          </button>
        </div>

        <!-- 标签页切换 -->
        <div class="px-5 pt-3 flex items-center gap-2 border-b border-[var(--color-parchment-darker)] bg-white">
          <button
            @click="tab = 'list'"
            type="button"
            class="px-3 py-2 text-sm font-medium border-b-2 transition-colors cursor-pointer"
            :class="tab === 'list' ? 'border-[var(--color-leather)] text-[var(--color-leather)] font-bold' : 'border-transparent text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
          >
            📖 我的书籍 ({{ projectStore.projects.length }})
          </button>
          <button
            @click="tab = 'create'"
            type="button"
            class="px-3 py-2 text-sm font-medium border-b-2 transition-colors cursor-pointer"
            :class="tab === 'create' ? 'border-[var(--color-leather)] text-[var(--color-leather)] font-bold' : 'border-transparent text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
          >
            ➕ 新建书籍
          </button>
          <button
            v-if="projectStore.activeProject"
            @click="tab = 'backups'"
            type="button"
            class="px-3 py-2 text-sm font-medium border-b-2 transition-colors cursor-pointer"
            :class="tab === 'backups' ? 'border-[var(--color-leather)] text-[var(--color-leather)] font-bold' : 'border-transparent text-[var(--color-ink-light)] hover:text-[var(--color-ink)]'"
          >
            💾 备份管理
          </button>
        </div>

        <div class="p-5 space-y-4 bg-white max-h-[70vh] overflow-y-auto">
          <div
            v-if="statusMsg"
            class="px-3 py-2 rounded-lg text-xs border"
            :class="statusMsg.startsWith('❌') ? 'bg-red-50 text-red-700 border-red-200' : 'bg-emerald-50 text-emerald-800 border-emerald-200'"
          >
            {{ statusMsg }}
          </div>

          <!-- 书籍列表 -->
          <div v-if="tab === 'list'" class="space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-xs text-[var(--color-ink-light)]">点击任意书籍卡片即可切换工作区</span>
              <button
                @click="onDiscover"
                :disabled="discovering"
                type="button"
                class="px-2.5 py-1 text-xs rounded border border-[var(--color-parchment-darker)] hover:bg-[var(--color-parchment)] cursor-pointer disabled:opacity-50"
              >
                {{ discovering ? '扫描中…' : '🔄 扫描本地 output 目录' }}
              </button>
            </div>

            <div v-if="projectStore.projects.length === 0" class="text-sm text-[var(--color-ink-light)] italic py-6 text-center">
              暂无书籍项目，请点击上方「新建书籍」创建一个项目。
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <div
                v-for="p in projectStore.projects"
                :key="p"
                @click="onSelectProject(p)"
                class="p-3 rounded-xl border-2 transition-all cursor-pointer flex items-center justify-between gap-2"
                :class="
                  p === projectStore.activeProject
                    ? 'border-[var(--color-leather)] bg-amber-50/70 shadow-xs'
                    : 'border-[var(--color-parchment-darker)] hover:border-[var(--color-leather-light)] hover:bg-[var(--color-parchment)]/40'
                "
              >
                <div class="min-w-0">
                  <div class="font-bold text-sm text-[var(--color-ink)] truncate flex items-center gap-1.5">
                    <span>{{ p === projectStore.activeProject ? '📖' : '📘' }}</span>
                    <span>{{ p }}</span>
                  </div>
                  <div class="text-[11px] text-[var(--color-ink-light)] mt-0.5">
                    {{ p === projectStore.activeProject ? '当前正在创作' : '点击切换至此书' }}
                  </div>
                </div>
                <button
                  @click.stop="onDelete(p)"
                  :disabled="deleting"
                  type="button"
                  class="px-2 py-1 text-xs text-red-600 hover:bg-red-50 rounded border border-transparent hover:border-red-200 cursor-pointer shrink-0"
                  title="删除项目"
                >
                  删除
                </button>
              </div>
            </div>
          </div>

          <!-- 新建书籍 -->
          <div v-else-if="tab === 'create'" class="space-y-3">
            <div>
              <label class="block text-xs font-semibold text-[var(--color-ink-light)] mb-1">书籍 / 项目名称 *</label>
              <input
                v-model="newName"
                placeholder="例如：玄幻长篇试水"
                class="w-full border border-[var(--color-parchment-darker)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-leather)]"
                @keyup.enter="onCreate"
              />
            </div>
            <div>
              <label class="block text-xs font-semibold text-[var(--color-ink-light)] mb-1">存储路径（留空则自动放在 ./output/项目名）</label>
              <input
                v-model="newPath"
                placeholder="可选，例如：./output/my_novel"
                class="w-full border border-[var(--color-parchment-darker)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--color-leather)]"
              />
            </div>
            <div class="flex justify-end gap-2 pt-2">
              <button
                @click="tab = 'list'"
                type="button"
                class="px-4 py-2 rounded-lg border border-[var(--color-parchment-darker)] text-sm cursor-pointer hover:bg-[var(--color-parchment)]"
              >
                返回
              </button>
              <button
                @click="onCreate"
                :disabled="creating || !newName.trim()"
                type="button"
                class="px-5 py-2 rounded-lg text-sm font-semibold text-white bg-[var(--color-leather)] hover:opacity-90 disabled:opacity-40 cursor-pointer"
              >
                {{ creating ? '创建中…' : '创建并切换' }}
              </button>
            </div>
          </div>

          <!-- 备份管理 -->
          <div v-else-if="tab === 'backups'" class="space-y-3">
            <div class="text-xs text-[var(--color-ink-light)]">
              当前备份对象：<strong>{{ projectStore.activeProject }}</strong>
            </div>
            <div class="flex items-center gap-2">
              <input
                v-model="backupNote"
                placeholder="备份备注（可选，如：第20章写完）"
                class="flex-1 border border-[var(--color-parchment-darker)] rounded-lg px-3 py-1.5 text-sm"
              />
              <button
                @click="onCreateBackup"
                :disabled="backupLoading"
                type="button"
                class="px-4 py-1.5 rounded-lg text-sm font-semibold bg-[var(--color-leather)] text-white hover:opacity-90 disabled:opacity-50 cursor-pointer"
              >
                {{ backupLoading ? '处理中…' : '+ 创建备份' }}
              </button>
            </div>
            <div v-if="backups.length === 0" class="text-xs text-[var(--color-ink-light)] italic py-4 text-center">
              暂无历史备份
            </div>
            <div v-else class="space-y-1.5 max-h-60 overflow-y-auto">
              <div
                v-for="b in backups"
                :key="b.id"
                class="flex items-center justify-between gap-2 px-3 py-2 rounded-lg border border-[var(--color-parchment-darker)] bg-[var(--color-parchment)]/30 text-xs"
              >
                <span class="truncate">
                  <strong>{{ b.timestamp }}</strong>
                  <span v-if="b.note" class="text-[var(--color-leather)]"> — {{ b.note }}</span>
                  <span class="text-[var(--color-ink-light)]"> ({{ b.size_mb }} MB)</span>
                </span>
                <div class="flex items-center gap-2 shrink-0">
                  <button
                    @click="onRestoreBackup(b.id)"
                    :disabled="backupLoading"
                    type="button"
                    class="text-[var(--color-leather)] font-semibold hover:underline cursor-pointer"
                  >
                    还原
                  </button>
                  <button
                    @click="onDeleteBackup(b.id)"
                    type="button"
                    class="text-red-600 hover:underline cursor-pointer"
                  >
                    删除
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
