import { ref, computed, onMounted, onActivated, onDeactivated, watch } from 'vue'
import { useProjectStore } from '@/stores/project'
import { useConfigStore } from '@/stores/config'
import { useGenerateStore } from '@/stores/generate'
import { postSSE, generateApi, stylesApi, configApi, type SSEHandle } from '@/api/client'

export type StepState = {
  running: boolean
  progress: string
  result: string
  error: string
  progressValue?: number
  sseHandle?: { abort: () => void } | null
}

export const mkState = (): StepState => ({
  running: false, progress: '', result: '', error: '', progressValue: undefined, sseHandle: null,
})

export interface PipelineStageInfo {
  id: number
  name: string
  subtitle: string
  icon: string
  status: 'idle' | 'running' | 'completed' | 'retrying' | 'error'
  progress: number
  targetProgress?: number
  message?: string
  badge?: string
}

export function useWorkshopState() {
  const projectStore = useProjectStore()
  const configStore = useConfigStore()
  const generateStore = useGenerateStore()

  const llmConfig = ref('')
  const embConfig = ref('')
  const filepath = computed(() => projectStore.filepath)

  // ── 小说参数 ──────────────────────────────────────────────────────────────
  const topic = ref('')
  const genre = ref('玄幻')
  const numChapters = ref(200)
  const wordNumber = ref(2500)
  const userGuidance = ref('')
  const xpType = ref('')
  const xpSelectedPresets = ref<string[]>([])
  const numCharacters = ref('3-6')
  const contNumCharacters = ref('1-3')

  // ── 文风/DNA 列表 ─────────────────────────────────────────────────────────
  const styleList = ref<string[]>([])
  const archStyle = ref('')
  const bpStyle = ref('')
  const chStyle = ref('')
  const chNarrativeStyle = ref('')
  const contStyle = ref('')

  // ── 步骤状态 ──────────────────────────────────────────────────────────────
  const arch = ref(mkState())
  const bp = ref(mkState())
  // 章节细纲
  const detailedOutline = ref(mkState())
  const outlineText = ref('')
  const outlineBatchStart = ref(1)
  const outlineBatchSize = ref(10)
  const outlineMode = ref('concise')  // concise / detailed
  const outlineBatchResult = ref('')
  const outlineBatchBackup = ref('')
  const outlineRevisionGuidance = ref('')
  const outlineRevision = ref(mkState())
  const chapter = ref(mkState())
  const finalize = ref(mkState())
  const expand = ref(mkState())

  // 分步架构
  const stepMode = ref(false)
  const stepSeed = ref(mkState())
  const stepChar = ref(mkState())
  const stepCharState = ref(mkState())
  const stepWorld = ref(mkState())
  const stepPlot = ref(mkState())
  const seedText = ref('')
  const charText = ref('')
  const charStateText = ref('')
  const worldText = ref('')
  const plotText = ref('')

  // 修订相关
  const revisionGuidance = ref({
    core_seed: '', characters: '', char_state: '', world: '', plot: '',
    cont_seed: '', cont_world: '', cont_chars: '', cont_arcs: '', cont_char_state: '',
  })
  const revisionState = ref({
    core_seed: mkState(), characters: mkState(), char_state: mkState(), world: mkState(), plot: mkState(),
    cont_seed: mkState(), cont_world: mkState(), cont_chars: mkState(), cont_arcs: mkState(), cont_char_state: mkState(),
  })

  const revisionContext = ref({
    include_core_seed: false, include_characters: false,
    include_world_building: false, include_plot: false,
  })

  // 注入选项
  const injectCharToWorld = ref(false)
  // 章节参数
  const injectWorldBuilding = ref(false)
  const sceneByScene = ref(false)  // 按场景分段生成
  const chapterNum = ref(1)
  const charactersInvolved = ref('')
  const keyItems = ref('')
  const sceneLocation = ref('')
  const timeConstraint = ref('')
  const chGuidance = ref('')

  // 一键生成
  const batch = ref(mkState())

  // 续写
  const continueArch = ref(mkState())
  const newChapters = ref(5)
  const continueGuidance = ref('')
  const contXpType = ref('')
  const compressRunning = ref(false)
  const compressResult = ref('')
  const compressWorldBuilding = ref(true)

  // 续写分步
  const contStepMode = ref(false)
  const contStepSeed = ref(mkState())
  const contSeedText = ref('')
  const contStepWorld = ref(mkState())
  const contWorldText = ref('')
  const contStepChars = ref(mkState())
  const contStepArcs = ref(mkState())
  const contStepCharState = ref(mkState())
  const contCharsText = ref('')
  const contArcsText = ref('')
  const contCharStateText = ref('')

  // 补充角色
  const supplementChar = ref(mkState())
  const supplementGuidance = ref('')
  const supplementNum = ref('1-2')
  const supplementResult = ref('')
  const contSupplementChar = ref(mkState())
  const contSupplementGuidance = ref('')
  const contSupplementNum = ref('1-2')
  const contSupplementResult = ref('')

  // 角色动力学
  const characterDynamicsContent = ref('')

  // 润色
  const polishGuidance = ref('')
  const polishMode = ref('enhance')  // enhance / modify / add
  const polishIncludeOutline = ref(false)
  const polishIncludeCharState = ref(false)
  const polishIncludeSummary = ref(false)
  const polishIncludeWorld = ref(false)
  const expandOriginal = ref('')   // 润色前原文
  const expandNew = ref('')        // 润色后新文
  const expandChapterNum = ref(0)  // 润色的章节号

  // ── 即兴写作模式（improv） ───────────────────────────────────────────────
  const workflowMode = ref<'outlined' | 'improv'>('outlined')
  const improvBlueprint = ref(mkState())
  const improvOutline = ref(mkState())
  const improvChapter = ref(mkState())
  const improvIntent = ref('')              // 用户本章意图（自由文本框）
  const improvBlueprintText = ref('')       // 已保存的本章蓝图全文（编辑用）
  const improvOutlineText = ref('')         // 已保存的本章细纲全文（编辑用）
  const openThreadsText = ref('')           // 伏笔池全文
  // 修订状态
  const improvBlueprintRevise = ref(mkState())
  const improvOutlineRevise = ref(mkState())
  const improvBlueprintRevisionGuidance = ref('')
  const improvOutlineRevisionGuidance = ref('')

  // 偏好提取
  const profileExtracted = ref('')
  const profileShowConfirm = ref(false)
  const profileConfirmMsg = ref('')

  async function _tryExtractProfile(text: string) {
    if (!text || text.length < 10 || !llmConfig.value) return
    try {
      const res = await configApi.extractPreferences(text, llmConfig.value)
      const prefs = res.data.preferences || ''
      if (prefs) {
        profileExtracted.value = prefs
        profileShowConfirm.value = true
      }
    } catch { /* 静默 */ }
  }

  async function profileConfirmAppend() {
    if (!profileExtracted.value) return
    try {
      await configApi.appendProfile(profileExtracted.value)
      profileConfirmMsg.value = '✅ 已加入画像'
    } catch {
      profileConfirmMsg.value = '❌ 保存失败'
    }
    profileShowConfirm.value = false
    profileExtracted.value = ''
    setTimeout(() => { profileConfirmMsg.value = '' }, 3000)
  }

  function profileDismiss() {
    profileShowConfirm.value = false
    profileExtracted.value = ''
  }

  // 去 AI 痕迹
  const humanize = ref(mkState())
  const humanizerBatch = ref(false)
  const humanizerR8 = ref(false)
  const humanizerFocus = ref('')
  const humanizerStart = ref(1)
  const humanizerEnd = ref(1)
  const humanizerDepth = ref<'quick' | 'standard' | 'deep'>('standard')
  // 对比预览状态
  const humanizerOriginal = ref('')
  const humanizerHumanized = ref('')
  const humanizerChanges = ref('')
  const humanizerPreviewTab = ref<'humanized' | 'original' | 'changes'>('humanized')
  const humanizerPending = ref(false)       // 有待确认的结果
  const humanizerSaving = ref(false)
  const humanizerChapterNum = ref(0)        // 处理的章节号

  // 导出
  const exporting = ref(false)

  // 保存消息
  const saveMsg = ref('')

  // 重载
  const reloading = ref(false)

  // ── 生命周期 ──────────────────────────────────────────────────────────────
  onMounted(async () => {
    await projectStore.loadActive()
    await Promise.all([configStore.loadAll(), generateStore.loadStatus()])
    arch.value.result = generateStore.architectureContent
    bp.value.result = generateStore.blueprintContent
    autoFillChapterParams(chapterNum.value || 1)
    characterDynamicsContent.value = generateStore.characterDynamicsContent
    // 从独立文件填充步骤字段（优先于项目数据中的缓存值）
    if (generateStore.coreSeedContent) seedText.value = generateStore.coreSeedContent
    if (generateStore.characterDynamicsContent) charText.value = generateStore.characterDynamicsContent
    if (generateStore.worldBuildingContent) worldText.value = generateStore.worldBuildingContent
    if (generateStore.plotArchitectureContent) plotText.value = generateStore.plotArchitectureContent
    if (generateStore.characterStateContent) charStateText.value = generateStore.characterStateContent
    if (projectStore.activeProjectData) {
      const p = projectStore.activeProjectData
      topic.value = p.topic ?? ''
      genre.value = p.genre ?? '玄幻'
      numChapters.value = p.num_chapters ?? 200
      wordNumber.value = p.word_number ?? 2500
      userGuidance.value = p.user_guidance ?? ''
      xpType.value = p.xp_type ?? ''
      xpSelectedPresets.value = p.xp_selected_presets ?? []
      if (p.arch_style) archStyle.value = p.arch_style
      if (p.bp_style) bpStyle.value = p.bp_style
      if (p.ch_style) chStyle.value = p.ch_style
      if (p.ch_narrative_style) chNarrativeStyle.value = p.ch_narrative_style
      if (p.cont_style) contStyle.value = p.cont_style
      if (p.cont_xp_type) contXpType.value = p.cont_xp_type
      if (p.step_seed_text) seedText.value = p.step_seed_text
      if (p.step_char_text) charText.value = p.step_char_text
      if (p.step_char_state_text) charStateText.value = p.step_char_state_text
      if (p.step_world_text) worldText.value = p.step_world_text
      if (p.step_plot_text) plotText.value = p.step_plot_text
      if (p.continue_guidance) continueGuidance.value = p.continue_guidance
      if (p.cont_new_chapters) newChapters.value = p.cont_new_chapters
      if (p.cont_step_chars_text) contCharsText.value = p.cont_step_chars_text
      if (p.cont_step_arcs_text) contArcsText.value = p.cont_step_arcs_text
      if (p.cont_step_char_state_text) contCharStateText.value = p.cont_step_char_state_text
      workflowMode.value = (p.workflow_mode === 'improv' ? 'improv' : 'outlined')
    }
    try {
      const res = await stylesApi.list()
      styleList.value = ['不使用文风', ...res.data.styles]
    } catch { /* ignore */ }
    const p = projectStore.activeProjectData
    if (p?.llm_config_name && configStore.llmChoices.includes(p.llm_config_name)) {
      llmConfig.value = p.llm_config_name
    } else if (configStore.llmChoices.includes('Gemini 3.8 Flash (内置免密)')) {
      llmConfig.value = 'Gemini 3.8 Flash (内置免密)'
    } else if (configStore.llmChoices.length) {
      llmConfig.value = configStore.llmChoices[0]
    }
    if (p?.emb_config_name && configStore.embeddingChoices.includes(p.emb_config_name)) {
      embConfig.value = p.emb_config_name
    } else if (configStore.embeddingChoices.length) {
      embConfig.value = configStore.embeddingChoices[0]
    }

    // 自动加载全书章节细纲、草稿与章节列表
    await loadOutlineText()
    await loadExistingChapters()
    await loadChapterDraft(chapterNum.value || 1)
    await loadChapterEn(chapterNum.value || 1)
    await loadChapterArtifacts(chapterNum.value || 1)
  })

  // ── 加载/重载项目内容 ─────────────────────────────────────────────────────
  async function reloadProjectContent() {
    reloading.value = true
    try {
      await projectStore.loadActive()
      const p = projectStore.activeProjectData
      if (p) {
        topic.value = p.topic ?? ''
        genre.value = p.genre ?? '玄幻'
        numChapters.value = p.num_chapters ?? 200
        wordNumber.value = p.word_number ?? 2500
        userGuidance.value = p.user_guidance ?? ''
        xpType.value = p.xp_type ?? ''
        xpSelectedPresets.value = p.xp_selected_presets ?? []
        if (p.llm_config_name && configStore.llmChoices.includes(p.llm_config_name)) {
          llmConfig.value = p.llm_config_name
        }
        if (p.emb_config_name && configStore.embeddingChoices.includes(p.emb_config_name)) {
          embConfig.value = p.emb_config_name
        }
        archStyle.value = p.arch_style || ''
        bpStyle.value = p.bp_style || ''
        chStyle.value = p.ch_style || ''
        chNarrativeStyle.value = p.ch_narrative_style || ''
        contStyle.value = p.cont_style || ''
        contXpType.value = p.cont_xp_type || ''
        seedText.value = p.step_seed_text || ''
        charText.value = p.step_char_text || ''
        charStateText.value = p.step_char_state_text || ''
        worldText.value = p.step_world_text || ''
        plotText.value = p.step_plot_text || ''
        continueGuidance.value = p.continue_guidance || ''
        newChapters.value = p.cont_new_chapters ?? 5
        contSeedText.value = p.cont_step_seed_text || ''
        contWorldText.value = p.cont_step_world_text || ''
        contCharsText.value = p.cont_step_chars_text || ''
        contArcsText.value = p.cont_step_arcs_text || ''
        contCharStateText.value = p.cont_step_char_state_text || ''
        workflowMode.value = (p.workflow_mode === 'improv' ? 'improv' : 'outlined')
      }
      // 即兴模式：加载伏笔池及当前章节蓝图/细纲
      if (workflowMode.value === 'improv') {
        loadOpenThreads()
        loadImprovBlueprint()
        loadImprovOutline()
      }
      await generateStore.loadStatus()
      arch.value.result = generateStore.architectureContent
      bp.value.result = generateStore.blueprintContent
      characterDynamicsContent.value = generateStore.characterDynamicsContent
      // 从独立文件刷新步骤字段
      if (generateStore.coreSeedContent) seedText.value = generateStore.coreSeedContent
      if (generateStore.characterDynamicsContent) charText.value = generateStore.characterDynamicsContent
      if (generateStore.worldBuildingContent) worldText.value = generateStore.worldBuildingContent
      if (generateStore.plotArchitectureContent) plotText.value = generateStore.plotArchitectureContent
      if (generateStore.characterStateContent) charStateText.value = generateStore.characterStateContent
      // 从独立文件加载章节细纲
      await loadOutlineText()
      // 联动抽取当前章节细纲
      extractChapterToEdit(chapterNum.value)
      // 加载章节草稿列表与当前草稿、译文
      await loadExistingChapters()
      await loadChapterDraft(chapterNum.value)
      await loadChapterEn(chapterNum.value)
      await loadDirectoryEn()
    } finally {
      reloading.value = false
    }
  }

  // 切换项目时自动重载
  watch(() => projectStore.activeProject, (name) => {
    if (autoSaveTimer) { clearTimeout(autoSaveTimer); autoSaveTimer = null }
    if (!name) return
    reloadProjectContent()
  })

  // ── 基础参数自动保存 ──────────────────────────────────────────────────────
  let autoSaveTimer: ReturnType<typeof setTimeout> | null = null

  function scheduleAutoSave() {
    if (!projectStore.activeProject) return
    if (autoSaveTimer) clearTimeout(autoSaveTimer)
    const targetProject = projectStore.activeProject
    autoSaveTimer = setTimeout(() => {
      if (projectStore.activeProject !== targetProject) return
      projectStore.saveProject({
        topic: topic.value,
        genre: genre.value,
        num_chapters: numChapters.value,
        word_number: wordNumber.value,
        user_guidance: userGuidance.value,
        xp_type: xpType.value,
        xp_selected_presets: xpSelectedPresets.value,
        llm_config_name: llmConfig.value,
        emb_config_name: embConfig.value,
        arch_style: archStyle.value,
        bp_style: bpStyle.value,
        ch_style: chStyle.value,
        ch_narrative_style: chNarrativeStyle.value,
        cont_style: contStyle.value,
        cont_xp_type: contXpType.value,
        step_seed_text: seedText.value,
        step_char_text: charText.value,
        step_char_state_text: charStateText.value,
        step_world_text: worldText.value,
        step_plot_text: plotText.value,
        continue_guidance: continueGuidance.value,
        cont_new_chapters: newChapters.value,
        cont_step_seed_text: contSeedText.value,
        cont_step_world_text: contWorldText.value,
        cont_step_chars_text: contCharsText.value,
        cont_step_arcs_text: contArcsText.value,
        cont_step_char_state_text: contCharStateText.value,
      })
    }, 1500)
  }

  watch([topic, genre, numChapters, wordNumber, userGuidance, xpType, xpSelectedPresets,
         llmConfig, embConfig, archStyle, bpStyle, chStyle, chNarrativeStyle,
         contStyle, contXpType,
         seedText, charText, charStateText, worldText, plotText,
         continueGuidance, newChapters, contSeedText, contWorldText, contCharsText, contArcsText, contCharStateText], scheduleAutoSave)

  // ── 辅助 ──────────────────────────────────────────────────────────────────
  function runSSE(state: StepState, url: string, body: Record<string, unknown>) {
    state.running = true
    state.progress = ''
    state.result = ''
    state.error = ''
    state.progressValue = undefined
    const handle = postSSE(
      url, body,
      (msg, value, content) => {
        state.progress = msg
        if (value !== undefined) state.progressValue = value
        // 流式输出：progress 事件携带的 content 实时显示在结果区域
        if (content) state.result = content
      },
      (content) => { state.result = content },
      (err) => { state.error = err; state.running = false },
      () => { state.running = false; state.sseHandle = null },
    )
    state.sseHandle = handle
  }

  function cancelSSE(state: StepState) {
    if (state.sseHandle) {
      state.sseHandle.abort()
      state.sseHandle = null
    }
  }

  function runStepSSE(state: StepState, textRef: { value: string }, url: string, body: Record<string, unknown>) {
    state.running = true
    state.progress = ''
    state.result = ''
    state.error = ''
    state.progressValue = undefined
    const handle = postSSE(
      url, body,
      (msg, value) => { state.progress = msg; if (value !== undefined) state.progressValue = value },
      (content) => { state.result = content; textRef.value = content },
      (err) => { state.error = err; state.running = false },
      () => { state.running = false; state.sseHandle = null },
    )
    state.sseHandle = handle
  }

  // ── 保存 ──────────────────────────────────────────────────────────────────
  async function saveArchitecture() {
    // 已废弃：架构文件现在是只读组装副本
    saveMsg.value = '架构文件为只读，请使用各组件的独立保存按钮'
    setTimeout(() => { saveMsg.value = '' }, 3000)
  }

  async function saveComponent(name: string, content: string) {
    if (!content) return
    try {
      const res = await generateApi.saveComponent(name, content, filepath.value)
      saveMsg.value = `✅ ${name} 已保存`
      if (res.data.assembled_content) {
        arch.value.result = res.data.assembled_content
      }
    } catch (e: unknown) { saveMsg.value = `❌ ${(e as Error).message}` }
    setTimeout(() => { saveMsg.value = '' }, 3000)
  }

  async function saveCoreSeed() { await saveComponent('core_seed', seedText.value) }
  async function saveCharDynamics() { await saveComponent('character_dynamics', charText.value) }
  async function saveCharState() { await saveComponent('character_state', charStateText.value) }
  async function saveWorldBuilding() { await saveComponent('world_building', worldText.value) }
  async function savePlotArch() { await saveComponent('plot_architecture', plotText.value) }

  async function saveBlueprint() {
    try {
      await generateApi.saveBlueprint(bp.value.result, filepath.value)
      saveMsg.value = '✅ 蓝图已保存'
    } catch (e: unknown) { saveMsg.value = `❌ ${(e as Error).message}` }
    setTimeout(() => { saveMsg.value = '' }, 3000)
  }

  async function saveCharacterDynamics() {
    if (!characterDynamicsContent.value) return
    try {
      await generateApi.saveCharacterDynamics(characterDynamicsContent.value, filepath.value)
      saveMsg.value = '✅ 角色动力学已保存'
    } catch (e: unknown) { saveMsg.value = `❌ ${(e as Error).message}` }
    setTimeout(() => { saveMsg.value = '' }, 3000)
  }

  const existingChapters = ref<{ num: number; has_draft: boolean; has_final: boolean }[]>([])

  async function loadExistingChapters() {
    try {
      const res = await generateApi.chapters(filepath.value)
      existingChapters.value = res.data.chapters || []
    } catch {
      existingChapters.value = []
    }
  }

  async function loadChapterDraft(num?: number) {
    const target = num ?? chapterNum.value
    if (!target) return null
    chapter.value.error = ''
    try {
      const res = await generateApi.getChapter(target, filepath.value)
      if (res.data && res.data.content) {
        chapter.value.result = res.data.content
        return res.data.content
      } else {
        chapter.value.result = ''
      }
    } catch {
      // 本地无文件，彻底清空，绝不残留
      chapter.value.result = ''
    }
    return null
  }

  async function saveChapter() {
    if (!chapter.value.result) return
    try {
      await generateApi.saveChapter(chapterNum.value, chapter.value.result, filepath.value)
      saveMsg.value = `✅ 第 ${chapterNum.value} 章已保存`
      await loadExistingChapters()
    } catch (e: unknown) { saveMsg.value = `❌ ${(e as Error).message}` }
    setTimeout(() => { saveMsg.value = '' }, 3000)
  }

  // ── Ctrl+S 快捷键 ────────────────────────────────────────────────────────
  function handleKeydown(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault()
      if (chapter.value.result && !chapter.value.running) saveChapter()
      else if (bp.value.result && !bp.value.running) saveBlueprint()
      else if (arch.value.result && !arch.value.running) saveArchitecture()
    }
  }
  onActivated(() => document.addEventListener('keydown', handleKeydown))
  onDeactivated(() => document.removeEventListener('keydown', handleKeydown))

  // ── Step 1: 架构 ─────────────────────────────────────────────────────────
  function doGenerateArch() {
    const s = arch.value
    s.running = true; s.progress = ''; s.result = ''; s.error = ''; s.progressValue = undefined
    const handle = postSSE(
      '/generate/architecture',
      {
        llm_config_name: llmConfig.value,
        topic: topic.value, genre: genre.value,
        num_chapters: numChapters.value, word_number: wordNumber.value,
        filepath: filepath.value, user_guidance: userGuidance.value,
        arch_style_name: archStyle.value === '不使用文风' ? null : archStyle.value || null,
        xp_type: xpType.value,
        num_characters: numCharacters.value,
      },
      (msg, value) => { s.progress = msg; if (value !== undefined) s.progressValue = value },
      (content) => {
        try {
          const data = JSON.parse(content)
          seedText.value = data.core_seed ?? ''
          charText.value = data.character_dynamics ?? ''
          worldText.value = data.world_building ?? ''
          plotText.value = data.plot_architecture ?? ''
          charStateText.value = data.character_state ?? ''
          s.result = data.assembled ?? content
        } catch {
          s.result = content
        }
      },
      (err) => { s.error = err; s.running = false },
      () => { s.running = false; s.sseHandle = null },
    )
    s.sseHandle = handle
  }

  function doStepSeed() {
    runStepSSE(stepSeed.value, seedText, '/generate/architecture/step/core_seed', {
      llm_config_name: llmConfig.value,
      topic: topic.value, genre: genre.value,
      num_chapters: numChapters.value, word_number: wordNumber.value,
      step_guidance: '', global_guidance: userGuidance.value, xp_type: xpType.value,
    })
  }
  function doStepChar() {
    runStepSSE(stepChar.value, charText, '/generate/architecture/step/characters', {
      llm_config_name: llmConfig.value,
      seed_text: seedText.value,
      step_guidance: '', global_guidance: userGuidance.value, xp_type: xpType.value,
      num_characters: numCharacters.value,
    })
  }
  function doSupplementChar() {
    runStepSSE(supplementChar.value, supplementResult, '/generate/architecture/supplement_characters', {
      llm_config_name: llmConfig.value,
      existing_characters: charText.value,
      supplement_guidance: supplementGuidance.value,
      num_characters: supplementNum.value,
      core_seed: seedText.value,
      world_building: worldText.value,
      filepath: filepath.value,
    })
  }
  function appendSupplementChar() {
    if (supplementResult.value.trim()) {
      charText.value = charText.value.trimEnd() + '\n\n' + supplementResult.value.trim()
      supplementResult.value = ''
      supplementGuidance.value = ''
    }
  }
  function doStepCharState() {
    runStepSSE(stepCharState.value, charStateText, '/generate/architecture/step/char_state', {
      llm_config_name: llmConfig.value,
      char_dynamics_text: charText.value,
    })
  }
  function doStepWorld() {
    runStepSSE(stepWorld.value, worldText, '/generate/architecture/step/world', {
      llm_config_name: llmConfig.value,
      seed_text: seedText.value,
      step_guidance: '', global_guidance: userGuidance.value, xp_type: xpType.value,
      char_text: injectCharToWorld.value ? charText.value : '',
    })
  }
  function doStepPlot() {
    runStepSSE(stepPlot.value, plotText, '/generate/architecture/step/plot', {
      llm_config_name: llmConfig.value,
      seed_text: seedText.value, char_text: charText.value, world_text: worldText.value,
      step_guidance: '', global_guidance: userGuidance.value,
      num_chapters: numChapters.value, arch_style_name: archStyle.value || null,
      xp_type: xpType.value,
    })
  }

  function doRevise(stepType: string) {
    const textRefs: Record<string, { value: string }> = {
      core_seed: seedText, characters: charText, char_state: charStateText,
      world: worldText, plot: plotText,
      cont_seed: contSeedText, cont_world: contWorldText, cont_chars: contCharsText,
      cont_arcs: contArcsText, cont_char_state: contCharStateText,
    }
    // Map to backend step_type labels
    const backendStepType: Record<string, string> = {
      core_seed: 'core_seed', characters: 'characters', char_state: 'char_state',
      world: 'world', plot: 'plot',
      cont_seed: 'core_seed', cont_world: 'world', cont_chars: 'characters',
      cont_arcs: 'plot', cont_char_state: 'char_state',
    }
    const textRef = textRefs[stepType]
    const state = (revisionState.value as Record<string, StepState>)[stepType]
    const guidance = (revisionGuidance.value as Record<string, string>)[stepType]
    if (!textRef?.value || !guidance) return
    _tryExtractProfile(guidance)  // 异步提取偏好
    runStepSSE(state, textRef, generateApi.reviseStep(), {
      llm_config_name: llmConfig.value,
      original_content: textRef.value,
      revision_guidance: guidance,
      step_type: backendStepType[stepType] || stepType,
      filepath: filepath.value,
      include_core_seed: revisionContext.value.include_core_seed,
      include_characters: revisionContext.value.include_characters,
      include_world_building: revisionContext.value.include_world_building,
      include_plot: revisionContext.value.include_plot,
    })
  }

  async function doAssemble() {
    try {
      const res = await generateApi.assembleArch({
        filepath: filepath.value, topic: topic.value, genre: genre.value,
        num_chapters: numChapters.value, word_number: wordNumber.value,
        seed_text: seedText.value, char_text: charText.value,
        char_state_text: charStateText.value, world_text: worldText.value,
        plot_text: plotText.value,
      })
      arch.value.result = res.data.content
      saveMsg.value = '✅ 完整架构已成功组装并保存至 Novel_architecture.txt！'
      setTimeout(() => { saveMsg.value = '' }, 4000)
    } catch (e: unknown) {
      arch.value.error = (e as Error).message
      saveMsg.value = `❌ 组装失败: ${(e as Error).message}`
      setTimeout(() => { saveMsg.value = '' }, 4000)
    }
  }

  // ── Step 2: 蓝图 ─────────────────────────────────────────────────────────
  function doGenerateBP() {
    runSSE(bp.value, '/generate/blueprint', {
      llm_config_name: llmConfig.value, filepath: filepath.value,
      num_chapters: numChapters.value, user_guidance: userGuidance.value,
      bp_style_name: bpStyle.value === '不使用文风' ? null : bpStyle.value || null,
      xp_type: xpType.value,
    })
  }

  // ── Step 2.5: 章节细纲 ───────────────────────────────────────────────────
  function doGenerateOutlineBatch() {
    const start = outlineBatchStart.value
    const end = Math.min(start + outlineBatchSize.value - 1, numChapters.value)
    const s = detailedOutline.value
    s.running = true; s.progress = ''; s.result = ''; s.error = ''
    outlineBatchResult.value = ''
    const handle = postSSE(
      generateApi.detailedOutline(),
      {
        llm_config_name: llmConfig.value,
        filepath: filepath.value,
        start_chapter: start,
        end_chapter: end,
        num_chapters: numChapters.value,
        user_guidance: userGuidance.value,
        xp_type: xpType.value,
        outline_mode: outlineMode.value,
      },
      (msg, value, content) => { s.progress = msg; if (content) outlineBatchResult.value = content },
      (content) => {
        outlineBatchResult.value = content || outlineBatchResult.value
        loadOutlineText()
        loadExistingChapters()
      },
      (err) => { s.error = err; s.running = false },
      () => { s.running = false },
    )
    s.sseHandle = handle
  }

  async function loadOutlineText() {
    try {
      const res = await generateApi.getDetailedOutline(filepath.value)
      outlineText.value = res.data.content || ''
      if (outlineText.value) {
        extractChapterToEdit(chapterNum.value || 1)
      }
    } catch { /* ignore */ }
  }

  async function saveOutline() {
    if (!outlineText.value) return
    try {
      await generateApi.saveDetailedOutline(outlineText.value, filepath.value)
      saveMsg.value = '✅ 细纲已保存'
    } catch (e: unknown) { saveMsg.value = `❌ ${(e as Error).message}` }
    setTimeout(() => { saveMsg.value = '' }, 3000)
  }

  async function saveBatchOutline() {
    if (!outlineBatchResult.value) return
    try {
      await loadOutlineText()
      const batchChapNums: number[] = []
      const re = /【第\s*(\d+)\s*章细纲】/g
      let m
      while ((m = re.exec(outlineBatchResult.value)) !== null) {
        batchChapNums.push(parseInt(m[1]))
      }
      if (batchChapNums.length > 0) {
        let fullText = outlineText.value
        const batchText = outlineBatchResult.value.trim()
        for (const num of batchChapNums) {
          const chapterRe = new RegExp(`(【第\\s*${num}\\s*章细纲】[\\s\\S]*?)(?=【第\\s*\\d+\\s*章细纲】|$)`)
          const newMatch = batchText.match(chapterRe)
          const newContent = newMatch ? newMatch[1].trim() : ''
          if (!newContent) continue
          const existRe = new RegExp(`【第\\s*${num}\\s*章细纲】[\\s\\S]*?(?=【第\\s*\\d+\\s*章细纲】|$)`)
          if (existRe.test(fullText)) {
            fullText = fullText.replace(existRe, newContent + '\n\n')
          } else {
            fullText = fullText.trim() + '\n\n' + newContent
          }
        }
        outlineText.value = fullText.trim()
      }
      await generateApi.saveDetailedOutline(outlineText.value, filepath.value)
      saveMsg.value = '✅ 本批细纲已保存'
    } catch (e: unknown) {
      saveMsg.value = `❌ ${(e as Error).message}`
    }
    setTimeout(() => { saveMsg.value = '' }, 3000)
  }

  async function saveSingleChapterOutline(targetChNum: number, singleContent: string) {
    try {
      await loadOutlineText()
      const cleanBlock = singleContent.trim()
      const normalized = cleanBlock.startsWith('【第')
        ? cleanBlock
        : `【第${targetChNum}章细纲】\n${cleanBlock}`
      let fullText = outlineText.value || ''
      const existRe = new RegExp(`【第\\s*${targetChNum}\\s*章细纲】[\\s\\S]*?(?=【第\\s*\\d+\\s*章细纲】|$)`)
      if (existRe.test(fullText)) {
        fullText = fullText.replace(existRe, normalized + '\n\n')
      } else {
        fullText = fullText.trim() ? fullText.trim() + '\n\n' + normalized : normalized
      }
      outlineText.value = fullText.trim()
      await generateApi.saveDetailedOutline(outlineText.value, filepath.value)
      await loadExistingChapters()
      saveMsg.value = `✅ 第 ${targetChNum} 章细纲已保存`
    } catch (e: unknown) {
      saveMsg.value = `❌ ${(e as Error).message}`
    }
    setTimeout(() => { saveMsg.value = '' }, 3000)
  }

  function extractChapterToEdit(chapterNum: number) {
    if (!outlineText.value || chapterNum < 1) return
    const re = new RegExp(`(【第\\s*${chapterNum}\\s*章细纲】[\\s\\S]*?)(?=【第\\s*\\d+\\s*章细纲】|$)`)
    const m = outlineText.value.match(re)
    if (m && m[1]) {
      outlineBatchResult.value = m[1].trim()
    } else {
      outlineBatchResult.value = ''
    }
  }

  const currentChapterOutline = computed(() => {
    if (!outlineText.value || chapterNum.value < 1) return ''
    const re = new RegExp(`(【第\\s*${chapterNum.value}\\s*章细纲】[\\s\\S]*?)(?=【第\\s*\\d+\\s*章细纲】|$)`)
    const m = outlineText.value.match(re)
    return (m && m[1]) ? m[1].trim() : ''
  })

  function revertOutlineBatch() {
    if (!outlineBatchBackup.value) return
    outlineBatchResult.value = outlineBatchBackup.value
    outlineBatchBackup.value = ''
  }

  function doReviseOutlineBatch() {
    if (!outlineBatchResult.value || !outlineRevisionGuidance.value) return
    outlineBatchBackup.value = outlineBatchResult.value
    const s = outlineRevision.value
    runStepSSE(s, outlineBatchResult, generateApi.reviseStep(), {
      llm_config_name: llmConfig.value,
      original_content: outlineBatchResult.value,
      revision_guidance: outlineRevisionGuidance.value,
      step_type: 'plot',
      filepath: filepath.value,
      include_core_seed: revisionContext.value.include_core_seed,
      include_characters: revisionContext.value.include_characters,
      include_world_building: revisionContext.value.include_world_building,
      include_plot: revisionContext.value.include_plot,
    })
  }

  // ── 全链路自动生成与生产控制舱 (End-to-End Pipeline Cockpit) ──
  interface PipelineStageInfo {
    id: number
    name: string
    subtitle: string
    icon: string
    status: 'idle' | 'running' | 'completed' | 'retrying' | 'error'
    progress: number
    targetProgress?: number
    message?: string
    badge?: string
  }

  // ── 工坊双界面视图切换：'pipeline' (🏭 全自动生产中枢) vs 'step' (✍️ 步进精修工坊) ──
  const initialViewMode = ((typeof window !== 'undefined' && localStorage.getItem('novel_workshop_view_mode')) as ('all' | 'pipeline' | 'step')) || 'all'
  const workshopViewMode = ref<'all' | 'pipeline' | 'step'>(initialViewMode)

  // ── 因果连续性与幕间交接（Semantic Handoff & Continuity Engine） ──
  const handoffData = ref<any>(null)
  const handoffLoading = ref(false)
  const coldStartLoading = ref(false)
  const coldStartResult = ref<any>(null)
  const preWriteGateLoading = ref(false)
  const preWriteGateResult = ref<any>(null)
  const spanRepairLoading = ref(false)
  const spanRepairTarget = ref('')
  const spanRepairInstruction = ref('')
  const spanRepairResult = ref<any>(null)

  // ── 小说流水线底层规则与固定写法表 ──
  const adultMode = ref(false)
  const fixedTermsContent = ref('')
  const fixedTermsLoading = ref(false)

  function setWorkshopViewMode(mode: 'all' | 'pipeline' | 'step') {
    workshopViewMode.value = mode
    if (typeof window !== 'undefined') {
      localStorage.setItem('novel_workshop_view_mode', mode)
    }
  }

  const pipelineOpen = ref(false)
  const pipelineRunning = ref(false)
  const pipelineElapsed = ref(0)
  let pipelineTimer: ReturnType<typeof setInterval> | null = null
  let pipelineTicker: ReturnType<typeof setInterval> | null = null
  const pipelineActiveTab = ref<'terminal' | 'draft' | 'polish' | 'polishChecklist' | 'translation' | 'audit' | 'archive' | 'continuity'>('terminal')
  const pipelineAutoRetry = ref(true)
  const pipelineStatusMsg = ref('')
  const pipelineProgressVal = ref(0)
  const pipelineCurrentStageId = ref(1)
  const pipelineTargetChapter = ref<number | null>(null)

  // 跨章快速查阅器（流水线生产期间允许独立查阅/比对其他章节内容，互不干扰）
  const whitepaperModalOpen = ref(false)
  function openWhitepaperModal() {
    whitepaperModalOpen.value = true
  }
  function closeWhitepaperModal() {
    whitepaperModalOpen.value = false
  }

  const quickReaderOpen = ref(false)
  const quickReaderChapter = ref(1)

  function openQuickReader(targetChapter?: number) {
    if (targetChapter && targetChapter >= 1) {
      quickReaderChapter.value = targetChapter
    } else {
      quickReaderChapter.value = chapterNum.value > 1 ? chapterNum.value - 1 : 1
    }
    quickReaderOpen.value = true
  }

  function closeQuickReader() {
    quickReaderOpen.value = false
  }

  // 6 阶段全局权重: Stage 1 (10%), Stage 2 (35%), Stage 3 (20%), Stage 4 (20%), Stage 5 (10%), Stage 6 (5%)
  const STAGE_WEIGHTS = [0.10, 0.35, 0.20, 0.20, 0.10, 0.05]

  function stopPipelineTimers() {
    if (pipelineTimer) {
      clearInterval(pipelineTimer)
      pipelineTimer = null
    }
    if (pipelineTicker) {
      clearInterval(pipelineTicker)
      pipelineTicker = null
    }
  }

  const savedPipelineMode = (typeof localStorage !== 'undefined' ? localStorage.getItem('novel_pipeline_mode') : null) as 'fast_zh' | 'bilingual' | null
  const pipelineMode = ref<'fast_zh' | 'bilingual'>(savedPipelineMode === 'bilingual' ? 'bilingual' : 'fast_zh')
  const pipelineAutoAdvance = ref(false)
  const savedReviewStrength = (typeof localStorage !== 'undefined' ? localStorage.getItem('novel_review_strength') : null) as 'strong' | 'light' | null
  const pipelineReviewStrength = ref<'strong' | 'light'>(savedReviewStrength === 'light' ? 'light' : 'strong')
  function setReviewStrength(val: 'strong' | 'light') {
    pipelineReviewStrength.value = val
    if (typeof localStorage !== 'undefined') localStorage.setItem('novel_review_strength', val)
  }
  const pipelineContextToggles = ref({
    summary: true,
    charState: true,
    worldBuilding: true,
    canon: true,
  })
  const batchQueueRunning = ref(false)
  const batchQueuePaused = ref(false)
  const batchQueueStopRequested = ref(false)
  const batchQueueStart = ref(1)
  const batchQueueEnd = ref(10)
  const batchQueueCurrent = ref(0)
  const batchQueueStatusMap = ref<Record<number, 'pending' | 'running' | 'completed' | 'error' | 'skipped'>>({})

  // 零大纲极速孵化状态
  const fastIncubating = ref(false)
  const fastIncubateProgress = ref('')

  function setPipelineMode(mode: 'fast_zh' | 'bilingual') {
    pipelineMode.value = mode
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('novel_pipeline_mode', mode)
    }
    if (mode === 'fast_zh' && (pipelineActiveTab.value === 'translation' || pipelineActiveTab.value === 'audit')) {
      pipelineActiveTab.value = 'terminal'
    }
    pipelineStages.value = defaultPipelineStages()
  }

  const defaultPipelineStages = (): PipelineStageInfo[] => {
    if (pipelineMode.value === 'fast_zh') {
      return [
        { id: 1, name: '细纲与因果交接装配', subtitle: '装配上章交接契约(Handoff)、开篇禁令与正史设定', icon: '🔗', status: 'idle', progress: 0, targetProgress: 0 },
        { id: 2, name: '中文分场景起草', subtitle: '分场景起草，直写情绪与动作指纹 (Gemini 3.8 Flash Low)', icon: '✍️', status: 'idle', progress: 0, targetProgress: 0 },
        { id: 3, name: 'AI 总编审校润色', subtitle: 'Gemini 4 Hydrogen (Medium) 去套话审校与节奏精修', icon: '🛡️', status: 'idle', progress: 0, targetProgress: 0 },
        { id: 4, name: '正史演进与交接归档', subtitle: '提炼下章交接契约(Handoff)、演进正史页与全书记忆', icon: '📜', status: 'idle', progress: 0, targetProgress: 0 },
      ]
    }
    return [
      { id: 1, name: '细纲与因果交接装配', subtitle: '装配上章交接契约(Handoff)、开篇禁令与正史设定', icon: '🔗', status: 'idle', progress: 0, targetProgress: 0 },
      { id: 2, name: '中文分场景起草', subtitle: '分场景起草，直写情绪与动作指纹 (Gemini 3.8 Flash Low)', icon: '✍️', status: 'idle', progress: 0, targetProgress: 0 },
      { id: 3, name: 'AI 总编审校润色', subtitle: 'Gemini 4 Hydrogen (Medium) 去套话审校与节奏精修', icon: '🛡️', status: 'idle', progress: 0, targetProgress: 0 },
      { id: 4, name: '出海美式英文译制', subtitle: '高忠实度、纯正母语、第八大去AI翻译铁律', icon: '🇺🇸', status: 'idle', progress: 0, targetProgress: 0 },
      { id: 5, name: '双语质检审校', subtitle: '双语对照严格质检 (Gemini 4 Hydrogen Medium)', icon: '🛡️', status: 'idle', progress: 0, targetProgress: 0 },
      { id: 6, name: '正史演进与交接归档', subtitle: '提炼下章交接契约(Handoff)、演进正史页与全书记忆', icon: '📜', status: 'idle', progress: 0, targetProgress: 0 },
    ]
  }

  const pipelineStages = ref<PipelineStageInfo[]>(defaultPipelineStages())

  const pipelineTerminalLogs = ref<string[]>([])
  const pipelineData = ref({
    draft: '',
    polished: '',
    checklist: '',
    zhuque: null as any,
    translation: '',
    audit: '',
    auditPass: false,
    retryOccurred: false,
    enZhuque: null as any,
    summary: '',
    characterState: '',
    canonHistory: '',
    message: '',
  })

  let pipelineHandle: SSEHandle | null = null

  async function doFastIncubateBook(customTopic?: string, customGenre?: string, customGuidance?: string) {
    if (fastIncubating.value) return
    if (customTopic) topic.value = customTopic
    if (customGenre) genre.value = customGenre
    if (customGuidance) userGuidance.value = customGuidance

    const currentTopic = topic.value.trim()
    if (!currentTopic) {
      alert('请先输入故事核心脑洞或一句话主题！')
      return
    }

    fastIncubating.value = true
    fastIncubateProgress.value = '正在基于雪花写作法推演全书架构（核心种子、人物动力学、世界观、剧情骨架）...'

    // 保存基本配置到 project_config.json
    try {
      await projectStore.saveProject({
        topic: topic.value,
        genre: genre.value,
        num_chapters: numChapters.value,
        word_number: wordNumber.value,
        user_guidance: userGuidance.value,
      })
    } catch {
      // ignore
    }

    // 1. 生成架构
    const archSuccess = await new Promise<boolean>((resolve) => {
      const s = arch.value
      s.running = true; s.progress = ''; s.result = ''; s.error = ''
      postSSE(
        '/generate/architecture',
        {
          llm_config_name: llmConfig.value,
          topic: topic.value,
          genre: genre.value,
          num_chapters: numChapters.value || 200,
          word_number: wordNumber.value || 2500,
          filepath: filepath.value,
          user_guidance: userGuidance.value,
          arch_style_name: archStyle.value === '不使用文风' ? null : archStyle.value || null,
          xp_type: xpType.value,
          num_characters: numCharacters.value || '3-6',
        },
        (msg) => {
          s.progress = msg
          fastIncubateProgress.value = `[架构推演中] ${msg}`
        },
        (content) => {
          if (typeof content === 'string' && (content.startsWith('❌') || content.includes('生成失败') || content.includes('不存在或为空'))) {
            s.error = content
            fastIncubateProgress.value = `❌ 架构推演未成功: ${content}`
            return
          }
          try {
            const data = JSON.parse(content)
            seedText.value = data.core_seed ?? ''
            charText.value = data.character_dynamics ?? ''
            worldText.value = data.world_building ?? ''
            plotText.value = data.plot_architecture ?? ''
            charStateText.value = data.character_state ?? ''
            s.result = data.assembled ?? content
          } catch {
            s.result = content
          }
        },
        (err) => {
          s.error = err
          fastIncubateProgress.value = `❌ 架构生成失败: ${err}`
          resolve(false)
        },
        () => {
          s.running = false
          resolve(!s.error)
        }
      )
    })

    if (!archSuccess) {
      fastIncubating.value = false
      alert(`架构孵化未完成: ${arch.value.error || arch.value.result || '模型未返回有效架构，请检查大模型配置或网络连接'}`)
      return
    }

    // 2. 生成章节蓝图
    fastIncubateProgress.value = '全书架构已推演就绪，正在生成章节大纲蓝图 (Novel_directory.txt)...'
    const bpSuccess = await new Promise<boolean>((resolve) => {
      const s = bp.value
      s.running = true; s.progress = ''; s.result = ''; s.error = ''
      postSSE(
        '/generate/blueprint',
        {
          llm_config_name: llmConfig.value,
          filepath: filepath.value,
          num_chapters: numChapters.value || 200,
          user_guidance: userGuidance.value,
          bp_style_name: bpStyle.value === '不使用文风' ? null : bpStyle.value || null,
          xp_type: xpType.value,
        },
        (msg) => {
          s.progress = msg
          fastIncubateProgress.value = `[蓝图推演中] ${msg}`
        },
        (content) => {
          if (typeof content === 'string' && (content.startsWith('❌') || content.includes('生成失败') || content.includes('未找到') || content.includes('不存在或为空'))) {
            s.error = content
            fastIncubateProgress.value = `❌ 蓝图推演未成功: ${content}`
            return
          }
          s.result = content
        },
        (err) => {
          s.error = err
          fastIncubateProgress.value = `❌ 蓝图生成失败: ${err}`
          resolve(false)
        },
        () => {
          s.running = false
          resolve(!s.error)
        }
      )
    })

    fastIncubating.value = false
    if (bpSuccess) {
      fastIncubateProgress.value = '🎉 架构与蓝图已全部就绪！全自动流水线已解锁，已装配第 1 章！'
      await reloadProjectContent()
      autoFillChapterParams(1, true)
      alert('🎉 全书雪花架构与大纲蓝图已全自动孵化就绪！\n已自动为您装填第1章创作参数与剧情走向，直接点击【全自动流水线生产】即可一键开写！')
    } else {
      alert(`蓝图孵化未完成: ${bp.value.error || bp.value.result || '大纲蓝图生成失败，请检查大模型配置'}`)
    }
  }

  function openPipelineControlRoom(num?: number) {
    if (num !== undefined && num !== chapterNum.value) {
      selectChapter(num)
    }
    autoFillChapterParams(chapterNum.value, false)
    loadHandoff(chapterNum.value > 1 ? chapterNum.value - 1 : 1)
    pipelineOpen.value = true
  }

  function closePipelineControlRoom() {
    if (pipelineRunning.value) {
      const ok = window.confirm('生产流水线正在运行中，关闭窗口流水线仍会在后台执行，确定关闭窗口？')
      if (!ok) return
    }
    pipelineOpen.value = false
  }

  let pipelineResolver: ((ok: boolean) => void) | null = null

  function cancelPipeline() {
    if (pipelineHandle) {
      pipelineHandle.abort()
      pipelineHandle = null
    }
    pipelineRunning.value = false
    pipelineTargetChapter.value = null
    stopPipelineTimers()
    pipelineStatusMsg.value = '🛑 用户已手动终止生产流水线'
    pipelineTerminalLogs.value.push(`[${new Date().toLocaleTimeString()}] 🛑 流水线已手动终止。`)
    if (pipelineResolver) {
      const r = pipelineResolver
      pipelineResolver = null
      r(false)
    }
  }

  function doRunPipeline(targetChapter?: number): Promise<boolean> {
    if (pipelineRunning.value) return Promise.resolve(false)
    if (typeof targetChapter === 'number' && targetChapter >= 1) {
      chapterNum.value = targetChapter
    }
    // 安全填充：绝不冲掉用户已在界面填入的导演指令与定制参数
    autoFillChapterParams(chapterNum.value, false)

    return new Promise<boolean>((resolve) => {
      pipelineResolver = resolve
      pipelineRunning.value = true
    pipelineElapsed.value = 0
    stopPipelineTimers()

    pipelineTimer = setInterval(() => {
      pipelineElapsed.value++
    }, 1000)

    pipelineStages.value = defaultPipelineStages()
    const isZhOnly = pipelineMode.value === 'fast_zh'
    pipelineTerminalLogs.value = [
      `[${new Date().toLocaleTimeString()}] 🚀 启动第 ${chapterNum.value} 章${isZhOnly ? '中文出稿' : '出海双语'}生产流水线...`,
      isZhOnly
        ? `[${new Date().toLocaleTimeString()}] 🎯 预设参数: 模式=纯中文4步, 目标字数=${wordNumber.value}`
        : `[${new Date().toLocaleTimeString()}] 🎯 预设参数: 模式=出海双语6步, 目标字数=${wordNumber.value}, 译制标准=${translateStyle.value}, 智能重试=${pipelineAutoRetry.value ? '开启' : '关闭'}`
    ]
    pipelineData.value = {
      draft: '',
      polished: '',
      checklist: '',
    zhuque: null as any,
      translation: '',
      audit: '',
      auditPass: false,
      retryOccurred: false,
      enZhuque: null as any,
      summary: '',
      characterState: '',
      canonHistory: '',
      message: '',
    }
    pipelineProgressVal.value = 0
    pipelineCurrentStageId.value = 1
    pipelineTargetChapter.value = chapterNum.value
    pipelineStatusMsg.value = '正在装配细纲与参数...'

    // 渐进式平滑推进定时器（动态自适应：快时平滑追赶，慢时渐近减速趋近 90%）
    pipelineTicker = setInterval(() => {
      if (!pipelineRunning.value) return

      let weightedSum = 0
      pipelineStages.value.forEach((stage, idx) => {
        if (stage.status === 'completed') {
          stage.progress = 100
        } else if (stage.status === 'running' || stage.status === 'retrying') {
          const target = stage.targetProgress || 15
          if (stage.progress < target) {
            // 后端有进度或处于初始阶段时，快速平滑追赶
            const step = Math.max(0.8, (target - stage.progress) * 0.3)
            stage.progress = Math.min(target, Math.round((stage.progress + step) * 10) / 10)
          } else if (stage.progress < 92) {
            // 等待后端长耗时操作时，渐近式平滑减速，最多爬升至 92%，绝不假死亦不过冲
            const delta = (93 - stage.progress) * 0.02 + 0.08
            stage.progress = Math.min(92, Math.round((stage.progress + delta) * 10) / 10)
          }
        } else if (stage.status === 'idle') {
          stage.progress = 0
        }
        weightedSum += (stage.progress || 0) * (STAGE_WEIGHTS[idx] || 0.1)
      })

      // 平滑更新全局进度
      const targetVal = weightedSum / 100
      if (targetVal > pipelineProgressVal.value) {
        pipelineProgressVal.value = Math.min(1.0, Math.round(targetVal * 1000) / 1000)
      }
    }, 300)

    const payload = {
      llm_config_name: llmConfig.value,
      emb_config_name: embConfig.value || '',
      filepath: filepath.value,
      chapter_num: chapterNum.value,
      word_number: wordNumber.value,
      user_guidance: chGuidance.value || userGuidance.value,
      characters_involved: charactersInvolved.value,
      key_items: keyItems.value,
      scene_location: sceneLocation.value,
      time_constraint: timeConstraint.value,
      style_name: chStyle.value === '不使用文风' ? '' : chStyle.value || '',
      narrative_style_name: chNarrativeStyle.value === '不使用文风' ? '' : chNarrativeStyle.value || '',
      xp_type: xpType.value,
      target_style: translateStyle.value,
      auto_retry_translation: pipelineAutoRetry.value,
      scene_by_scene: sceneByScene.value,
      adult_mode: adultMode.value,
      pipeline_mode: pipelineMode.value,
      review_strength: pipelineReviewStrength.value,
      inject_world_building: pipelineContextToggles.value.worldBuilding,
      inject_summary: pipelineContextToggles.value.summary,
      inject_char_state: pipelineContextToggles.value.charState,
      inject_canon: pipelineContextToggles.value.canon,
    }

    pipelineHandle = postSSE(
      '/generate/pipeline_chapter',
      payload,
      (msg, val, content) => {
        if (msg) {
          pipelineStatusMsg.value = msg
          pipelineTerminalLogs.value.push(`[${new Date().toLocaleTimeString()}] ${msg}`)
        }
        if (val !== undefined && val > pipelineProgressVal.value) {
          pipelineProgressVal.value = val
        }
        if (content) {
          try {
            const ev = JSON.parse(content)
            if (ev.pipeline_event === 'stage_update') {
              const stageIdx = ev.stage
              const st = pipelineStages.value.find(s => s.id === stageIdx)
              if (st) {
                st.status = ev.status
                if (ev.message) st.message = ev.message
                if (ev.stage_progress !== undefined) {
                  st.targetProgress = Math.round(ev.stage_progress * 100)
                  if (st.status === 'running' && st.progress < st.targetProgress) {
                    st.progress = Math.max(st.progress, Math.min(st.targetProgress, st.progress + 6))
                  }
                }
                if (ev.status === 'completed') {
                  st.progress = 100
                  st.targetProgress = 100
                }
                if (ev.status === 'running') {
                  pipelineCurrentStageId.value = stageIdx
                  if (st.progress < 10) st.progress = 10
                }
              }
              if (ev.payload) {
                const p = ev.payload
                if (p.draft) {
                  pipelineData.value.draft = p.draft
                  chapter.value.result = p.draft
                }
                if (p.polished) {
                  pipelineData.value.polished = p.polished
                  expandNew.value = p.polished
                  chapter.value.result = p.polished
                }
                if (p.checklist) {
                  pipelineData.value.checklist = p.checklist
                }
                if (p.zhuque) {
                  pipelineData.value.zhuque = p.zhuque
                }
                if (p.translation) {
                  pipelineData.value.translation = p.translation
                  translateResult.value = p.translation
                }
                if (p.audit) {
                  pipelineData.value.audit = p.audit
                  auditState.value.result = p.audit
                  pipelineData.value.auditPass = Boolean(p.audit_pass)
                  pipelineData.value.retryOccurred = Boolean(p.retry_occurred)
                }
                if (p.en_zhuque) {
                  pipelineData.value.enZhuque = p.en_zhuque
                }
                if (p.summary) {
                  pipelineData.value.summary = p.summary
                }
                if (p.character_state) {
                  pipelineData.value.characterState = p.character_state
                }
                if (p.canon_history) {
                  pipelineData.value.canonHistory = p.canon_history
                }
                if (p.handoff) {
                  handoffData.value = p.handoff
                }
              }
            }
          } catch {
            // ignore JSON parse error
          }
        }
      },
      (content) => {
        if (content) {
          try {
            const res = JSON.parse(content)
            if (res.success) {
              if (res.draft) pipelineData.value.draft = res.draft
              if (res.polished) {
                pipelineData.value.polished = res.polished
                chapter.value.result = res.polished
                expandNew.value = res.polished
              }
              if (res.checklist) pipelineData.value.checklist = res.checklist
              if (res.translation) {
                pipelineData.value.translation = res.translation
                translateResult.value = res.translation
              }
              if (res.audit) {
                pipelineData.value.audit = res.audit
                auditState.value.result = res.audit
                pipelineData.value.auditPass = Boolean(res.audit_pass)
                pipelineData.value.retryOccurred = Boolean(res.retry_occurred)
              }
              if (res.en_zhuque) pipelineData.value.enZhuque = res.en_zhuque
              if (res.summary) pipelineData.value.summary = res.summary
              if (res.character_state) pipelineData.value.characterState = res.character_state
              pipelineStatusMsg.value = res.message || '🎉 全链路生产圆满完成！'
              pipelineStages.value.forEach(s => {
                s.status = 'completed'
                s.progress = 100
                s.targetProgress = 100
              })
              pipelineProgressVal.value = 1.0
              pipelineTerminalLogs.value.push(`[${new Date().toLocaleTimeString()}] ✅ ${pipelineStatusMsg.value}`)
            } else if (res.error) {
              pipelineStatusMsg.value = `❌ 生产中断: ${res.error}`
              if (res.failed_stage) {
                const s = pipelineStages.value.find(st => st.id === res.failed_stage)
                if (s) s.status = 'error'
              }
              pipelineTerminalLogs.value.push(`[${new Date().toLocaleTimeString()}] ❌ ${pipelineStatusMsg.value}`)
            }
          } catch {
            // text result
          }
        }
      },
      (err) => {
        pipelineStatusMsg.value = `❌ 异常: ${err}`
        pipelineTerminalLogs.value.push(`[${new Date().toLocaleTimeString()}] ❌ ${err}`)
        pipelineRunning.value = false
        stopPipelineTimers()
        if (pipelineResolver) {
          const r = pipelineResolver
          pipelineResolver = null
          r(false)
        }
      },
      () => {
        pipelineRunning.value = false
        stopPipelineTimers()
        pipelineHandle = null
        if (pipelineMode.value === 'bilingual' && pipelineData.value.translation) {
          pipelineActiveTab.value = 'translation'
        } else if (pipelineData.value.polished) {
          pipelineActiveTab.value = 'polish'
        }
        loadHandoff(chapterNum.value)
        loadExistingChapters()
        const ok = pipelineStages.value.every(s => s.status === 'completed')
        if (pipelineAutoAdvance.value && ok && !batchQueueRunning.value) {
          if (chapterNum.value < numChapters.value) {
            chapterNum.value++
            autoFillChapterParams(chapterNum.value, false)
          }
        }
        if (pipelineResolver) {
          const r = pipelineResolver
          pipelineResolver = null
          r(ok)
        }
      }
    )
    })
  }

  function togglePauseBatchQueue() {
    batchQueuePaused.value = !batchQueuePaused.value
  }

  function stopBatchQueue() {
    batchQueueStopRequested.value = true
    batchQueuePaused.value = false
    if (pipelineRunning.value) {
      cancelPipeline()
    }
    batchQueueRunning.value = false
  }

  async function doRunBatchQueue(start?: number, end?: number, overwriteCompleted = false) {
    if (batchQueueRunning.value || pipelineRunning.value) return
    const s = Math.max(1, start ?? batchQueueStart.value)
    const e = Math.min(numChapters.value, Math.max(s, end ?? batchQueueEnd.value))
    batchQueueStart.value = s
    batchQueueEnd.value = e
    batchQueueRunning.value = true
    batchQueuePaused.value = false
    batchQueueStopRequested.value = false

    const map: Record<number, 'pending' | 'running' | 'completed' | 'error' | 'skipped'> = {}
    for (let ch = s; ch <= e; ch++) {
      const exist = existingChapters.value.find(c => c.num === ch)
      if (!overwriteCompleted && exist?.has_final) {
        map[ch] = 'skipped'
      } else {
        map[ch] = 'pending'
      }
    }
    batchQueueStatusMap.value = map

    for (let ch = s; ch <= e; ch++) {
      if (batchQueueStopRequested.value) break
      while (batchQueuePaused.value && !batchQueueStopRequested.value) {
        await new Promise(r => setTimeout(r, 400))
      }
      if (batchQueueStopRequested.value) break
      if (batchQueueStatusMap.value[ch] === 'skipped') continue

      batchQueueCurrent.value = ch
      batchQueueStatusMap.value = { ...batchQueueStatusMap.value, [ch]: 'running' }
      chapterNum.value = ch
      const ok = await doRunPipeline(ch)
      batchQueueStatusMap.value = {
        ...batchQueueStatusMap.value,
        [ch]: ok ? 'completed' : 'error',
      }
      if (!ok && !batchQueueStopRequested.value) {
        // 出错后暂停队列，等待作者查看或手动处理，不盲目雪崩跑完后面依赖本章记忆的章节
        batchQueuePaused.value = true
        break
      }
    }
    batchQueueRunning.value = false
  }

  // ── Step 3: 章节 ─────────────────────────────────────────────────────────
  function doGenerateChapter() {
    runSSE(chapter.value, '/generate/chapter', {
      llm_config_name: llmConfig.value, emb_config_name: embConfig.value,
      filepath: filepath.value, chapter_num: chapterNum.value,
      word_number: wordNumber.value,
      user_guidance: chGuidance.value || userGuidance.value,
      characters_involved: charactersInvolved.value,
      key_items: keyItems.value, scene_location: sceneLocation.value,
      time_constraint: timeConstraint.value,
      style_name: chStyle.value === '不使用文风' ? null : chStyle.value || null,
      narrative_style_name: chNarrativeStyle.value === '不使用文风' ? null : chNarrativeStyle.value || null,
      xp_type: xpType.value,
      inject_world_building: injectWorldBuilding.value,
      scene_by_scene: sceneByScene.value,
    })
  }

  // ── Step 4: 精炼 ─────────────────────────────────────────────────────────
  function doFinalize() {
    runSSE(finalize.value, '/generate/finalize', {
      llm_config_name: llmConfig.value, emb_config_name: embConfig.value,
      filepath: filepath.value, chapter_num: chapterNum.value,
      word_number: wordNumber.value,
    })
  }

  // ── 即兴写作模式：单章蓝图/细纲/正文/伏笔池 ──────────────────────────────
  function doGenerateImprovBlueprint() {
    runSSE(improvBlueprint.value, '/generate/blueprint_single', {
      llm_config_name: llmConfig.value,
      filepath: filepath.value,
      chapter_num: chapterNum.value,
      chapter_intent: improvIntent.value,
      word_number: wordNumber.value,
    })
  }

  async function saveImprovBlueprint() {
    try {
      const num = chapterNum.value
      const content = improvBlueprint.value.result || improvBlueprintText.value
      await generateApi.saveBlueprintSingle(num, content, filepath.value)
      improvBlueprintText.value = content
      saveMsg.value = `✅ 第${num}章蓝图已保存`
      setTimeout(() => { saveMsg.value = '' }, 3000)
    } catch (e: unknown) {
      saveMsg.value = `❌ 保存失败: ${(e as Error).message}`
    }
  }

  async function loadImprovBlueprint() {
    try {
      const res = await generateApi.getBlueprintSingle(chapterNum.value, filepath.value)
      improvBlueprintText.value = res.data.content || ''
      improvBlueprint.value.result = res.data.content || ''
    } catch { /* ignore */ }
  }

  function doGenerateImprovOutline() {
    runSSE(improvOutline.value, '/generate/outline_single', {
      llm_config_name: llmConfig.value,
      filepath: filepath.value,
      chapter_num: chapterNum.value,
      word_number: wordNumber.value,
    })
  }

  async function saveImprovOutline() {
    try {
      const num = chapterNum.value
      const content = improvOutline.value.result || improvOutlineText.value
      await generateApi.saveOutlineSingle(num, content, filepath.value)
      improvOutlineText.value = content
      saveMsg.value = `✅ 第${num}章细纲已保存`
      setTimeout(() => { saveMsg.value = '' }, 3000)
    } catch (e: unknown) {
      saveMsg.value = `❌ 保存失败: ${(e as Error).message}`
    }
  }

  async function loadImprovOutline() {
    try {
      const res = await generateApi.getOutlineSingle(chapterNum.value, filepath.value)
      improvOutlineText.value = res.data.content || ''
      improvOutline.value.result = res.data.content || ''
    } catch { /* ignore */ }
  }

  function doGenerateImprovChapter() {
    runSSE(improvChapter.value, '/generate/chapter_improv', {
      llm_config_name: llmConfig.value,
      filepath: filepath.value,
      chapter_num: chapterNum.value,
      word_number: wordNumber.value,
      user_guidance: chGuidance.value || userGuidance.value,
      style_name: chStyle.value === '不使用文风' ? null : chStyle.value || null,
      narrative_style_name: chNarrativeStyle.value === '不使用文风' ? null : chNarrativeStyle.value || null,
    })
  }

  async function saveImprovChapter() {
    try {
      const num = chapterNum.value
      await generateApi.saveChapter(num, improvChapter.value.result, filepath.value)
      saveMsg.value = `✅ 第${num}章已保存`
      setTimeout(() => { saveMsg.value = '' }, 3000)
    } catch (e: unknown) {
      saveMsg.value = `❌ 保存失败: ${(e as Error).message}`
    }
  }

  async function loadOpenThreads() {
    try {
      const res = await generateApi.getOpenThreads(filepath.value)
      openThreadsText.value = res.data.content || ''
    } catch { /* ignore */ }
  }

  async function saveOpenThreadsText() {
    try {
      await generateApi.saveOpenThreads(openThreadsText.value, filepath.value)
      saveMsg.value = '✅ 伏笔池已保存'
      setTimeout(() => { saveMsg.value = '' }, 3000)
    } catch (e: unknown) {
      saveMsg.value = `❌ 保存失败: ${(e as Error).message}`
    }
  }

  function doReviseImprovBlueprint() {
    const current = improvBlueprint.value.result || improvBlueprintText.value
    if (!current) {
      saveMsg.value = '❌ 当前蓝图为空·先生成或加载一份蓝图再修订'
      setTimeout(() => { saveMsg.value = '' }, 3000)
      return
    }
    if (!improvBlueprintRevisionGuidance.value.trim()) {
      saveMsg.value = '❌ 请填写修订建议'
      setTimeout(() => { saveMsg.value = '' }, 3000)
      return
    }
    runSSE(improvBlueprintRevise.value, '/generate/blueprint_single/revise', {
      llm_config_name: llmConfig.value,
      filepath: filepath.value,
      chapter_num: chapterNum.value,
      current_blueprint: current,
      revision_guidance: improvBlueprintRevisionGuidance.value,
    })
  }

  // 修订完成后·把结果回填到 improvBlueprint.result
  watch(() => improvBlueprintRevise.value.result, (v) => {
    if (v && !improvBlueprintRevise.value.running) {
      improvBlueprint.value.result = v
    }
  })

  function doReviseImprovOutline() {
    const current = improvOutline.value.result || improvOutlineText.value
    if (!current) {
      saveMsg.value = '❌ 当前细纲为空·先生成或加载一份细纲再修订'
      setTimeout(() => { saveMsg.value = '' }, 3000)
      return
    }
    if (!improvOutlineRevisionGuidance.value.trim()) {
      saveMsg.value = '❌ 请填写修订建议'
      setTimeout(() => { saveMsg.value = '' }, 3000)
      return
    }
    runSSE(improvOutlineRevise.value, '/generate/outline_single/revise', {
      llm_config_name: llmConfig.value,
      filepath: filepath.value,
      chapter_num: chapterNum.value,
      current_outline: current,
      revision_guidance: improvOutlineRevisionGuidance.value,
    })
  }

  watch(() => improvOutlineRevise.value.result, (v) => {
    if (v && !improvOutlineRevise.value.running) {
      improvOutline.value.result = v
    }
  })

  async function setWorkflowMode(mode: 'outlined' | 'improv') {
    if (workflowMode.value === mode) return
    workflowMode.value = mode
    // 立即保存
    try {
      await projectStore.saveProject({ workflow_mode: mode })
      saveMsg.value = mode === 'improv' ? '✅ 已切换到即兴模式' : '✅ 已切换到大纲模式'
      setTimeout(() => { saveMsg.value = '' }, 3000)
    } catch (e: unknown) {
      saveMsg.value = `❌ 切换失败: ${(e as Error).message}`
    }
  }

  // ── 一键完成 ──────────────────────────────────────────────────────────────
  watch(() => batch.value.running, (running, wasRunning) => {
    if (wasRunning && !running && batch.value.result && !batch.value.error) {
      doExportNovel()
    }
  })

  function doBatchGenerate() {
    runSSE(batch.value, '/generate/batch', {
      llm_config_name: llmConfig.value, emb_config_name: embConfig.value,
      filepath: filepath.value, word_number: wordNumber.value,
      user_guidance: userGuidance.value,
      style_name: chStyle.value === '不使用文风' ? null : chStyle.value || null,
      narrative_style_name: chNarrativeStyle.value === '不使用文风' ? null : chNarrativeStyle.value || null,
      xp_type: xpType.value,
      inject_world_building: injectWorldBuilding.value,
    })
  }

  // ── Step 5: 润色 ─────────────────────────────────────────────────────────
  function doExpand() {
    // 清空上次的对比结果
    expandOriginal.value = ''
    expandNew.value = ''
    expandChapterNum.value = chapterNum.value
    if (polishGuidance.value) _tryExtractProfile(polishGuidance.value)  // 异步提取偏好
    const s = expand.value
    s.running = true; s.progress = ''; s.result = ''; s.error = ''; s.progressValue = undefined
    const handle = postSSE(
      '/generate/expand',
      {
        llm_config_name: llmConfig.value, filepath: filepath.value,
        chapter_num: chapterNum.value,
        style_name: chStyle.value === '不使用文风' ? null : chStyle.value || null,
        narrative_style_name: chNarrativeStyle.value === '不使用文风' ? null : chNarrativeStyle.value || null,
        xp_type: xpType.value, polish_guidance: polishGuidance.value,
        polish_mode: polishMode.value,
        include_outline: polishIncludeOutline.value,
        include_character_state: polishIncludeCharState.value,
        include_summary: polishIncludeSummary.value,
        include_world_building: polishIncludeWorld.value,
      },
      (msg, value, content) => {
        s.progress = msg
        if (value !== undefined) s.progressValue = value
        if (content) s.result = content
      },
      (content) => {
        // 完成回调：解析 JSON 响应
        s.result = content
        const marker = '<!--EXPAND_JSON-->'
        if (content.startsWith(marker)) {
          try {
            const data = JSON.parse(content.slice(marker.length))
            expandOriginal.value = data.original || ''
            expandNew.value = data.expanded || ''
            expandChapterNum.value = data.chapter_num || chapterNum.value
            s.result = '' // 清空 result，用 expandNew 展示
          } catch { /* 解析失败则保持原样 */ }
        }
      },
      (err) => { s.error = err; s.running = false },
      () => { s.running = false; s.sseHandle = null },
    )
    s.sseHandle = handle
  }

  async function saveExpandResult(useNew: boolean) {
    const num = expandChapterNum.value
    const content = useNew ? expandNew.value : expandOriginal.value
    if (!num || !content) return
    try {
      await generateApi.saveChapter(num, content, filepath.value)
      saveMsg.value = `✅ 第${num}章已保存（${useNew ? '新版' : '旧版'}）`
    } catch (e: unknown) {
      saveMsg.value = `❌ ${(e as Error).message}`
    }
    setTimeout(() => { saveMsg.value = '' }, 3000)
  }

  // ── Step 6: 去 AI 痕迹 ─────────────────────────────────────────────────
  function _resetHumanizerPreview() {
    humanizerOriginal.value = ''
    humanizerHumanized.value = ''
    humanizerChanges.value = ''
    humanizerPending.value = false
    humanizerPreviewTab.value = 'humanized'
    humanizerChapterNum.value = 0
  }

  // ── 出海英文本地化 ──
  const translateState = ref(mkState())
  const translateStyle = ref('Alpha Romance (GoodNovel / Dreame 爆款标准)')
  const translateGuidance = ref('')
  const translateResult = ref('')
  const translateSaving = ref(false)

  async function loadChapterEn(num?: number) {
    const target = num ?? chapterNum.value
    if (!target) return
    try {
      const res = await generateApi.getChapterEn(target, filepath.value)
      if (res.data && res.data.content) {
        translateResult.value = res.data.content
        translateState.value.result = res.data.content
        pipelineData.value.translation = res.data.content
        return res.data.content
      } else {
        translateResult.value = ''
        translateState.value.result = ''
      }
    } catch {
      translateResult.value = ''
      translateState.value.result = ''
    }
  }

  async function loadChapterArtifacts(num?: number) {
    const target = num ?? chapterNum.value
    if (!target) return
    try {
      const res = await generateApi.getChapterArtifacts(target, filepath.value)
      if (res.data) {
        const d = res.data
        // 关键修复 1：每次切换/加载章节时，严格按目标章节实际数据赋值（无则清空，防止旧章节产物残留污染）
        pipelineData.value.draft = d.draft || ''
        pipelineData.value.polished = d.polished || ''
        pipelineData.value.checklist = d.checklist || ''
        pipelineData.value.translation = d.translation || ''
        pipelineData.value.audit = ''
        pipelineData.value.auditPass = Boolean(d.has_en)
        pipelineData.value.retryOccurred = false
        pipelineData.value.message = ''
        if (d.summary) pipelineData.value.summary = d.summary
        if (d.character_state) pipelineData.value.characterState = d.character_state

        expandNew.value = d.polished || ''
        chapter.value.result = d.polished || d.draft || ''
        translateResult.value = d.translation || ''
        translateState.value.result = d.translation || ''

        // 关键修复 2：根据目标章节的实际生成文件情况，按当前流水线模式精准回显各阶段状态
        if (!pipelineRunning.value) {
          const isZhOnly = pipelineMode.value === 'fast_zh'
          if ((isZhOnly && d.has_polished && Boolean(d.summary)) || (!isZhOnly && d.has_en)) {
            pipelineStages.value.forEach(s => {
              s.status = 'completed'
              s.progress = 100
              s.targetProgress = 100
            })
            pipelineProgressVal.value = 1.0
            pipelineCurrentStageId.value = isZhOnly ? 4 : 6
            pipelineStatusMsg.value = `第 ${target} 章产物已就绪（已归档）`
            pipelineData.value.auditPass = true
          } else if (d.has_polished) {
            pipelineStages.value.forEach((s, idx) => {
              const done = idx <= 2
              s.status = done ? 'completed' : 'idle'
              s.progress = done ? 100 : 0
              s.targetProgress = done ? 100 : 0
            })
            pipelineProgressVal.value = isZhOnly ? 0.85 : 0.65
            pipelineCurrentStageId.value = 4
            pipelineStatusMsg.value = isZhOnly
              ? `第 ${target} 章中文审校定稿已就绪`
              : `第 ${target} 章中文润色已就绪，待出海英译与质检`
            pipelineData.value.auditPass = false
          } else if (d.has_draft) {
            pipelineStages.value.forEach((s, idx) => {
              const done = idx <= 1
              s.status = done ? 'completed' : 'idle'
              s.progress = done ? 100 : 0
              s.targetProgress = done ? 100 : 0
            })
            pipelineProgressVal.value = 0.45
            pipelineCurrentStageId.value = 3
            pipelineStatusMsg.value = `第 ${target} 章中文草稿已就绪，待审校润色`
            pipelineData.value.auditPass = false
          } else {
            // 本章尚未生成（如切换到第八章）：彻底重置为 0% 初始待命状态！
            pipelineStages.value = defaultPipelineStages()
            pipelineProgressVal.value = 0
            pipelineCurrentStageId.value = 1
            pipelineStatusMsg.value = `第 ${target} 章待命中，点击「启动全链路生产」开始`
            pipelineData.value.auditPass = false
            pipelineTerminalLogs.value = [
              `[${new Date().toLocaleTimeString()}] ℹ️ 当前选定第 ${target} 章（尚未生产）。流水线就绪，点击上方按钮开始。`
            ]
          }
        }
      }
    } catch {
      if (!pipelineRunning.value) {
        pipelineStages.value = defaultPipelineStages()
        pipelineProgressVal.value = 0
        pipelineCurrentStageId.value = 1
        pipelineData.value.draft = ''
        pipelineData.value.polished = ''
        pipelineData.value.checklist = ''
        pipelineData.value.translation = ''
        pipelineData.value.audit = ''
        pipelineData.value.auditPass = false
        pipelineData.value.retryOccurred = false
        pipelineStatusMsg.value = `第 ${target} 章待命中，点击「启动全链路生产」开始`
      }
    }
  }

  function doTranslateChapter() {
    const s = translateState.value
    s.running = true
    s.progress = '准备翻译...'
    s.result = ''
    translateResult.value = ''
    s.error = ''
    const handle = postSSE(
      '/generate/translate',
      {
        llm_config_name: llmConfig.value,
        filepath: filepath.value,
        chapter_num: chapterNum.value,
        target_style: translateStyle.value,
        custom_guidance: translateGuidance.value,
      },
      (msg, value) => {
        s.progress = msg
        if (value !== undefined) s.progressValue = value
      },
      (content) => {
        s.result = content
        translateResult.value = content
      },
      (err) => {
        s.error = err
        s.running = false
      },
      () => {
        s.running = false
        s.sseHandle = null
        if (translateResult.value) {
          saveChapterEn()
        }
      },
    )
    s.sseHandle = handle
  }

  async function saveChapterEn() {
    if (!translateResult.value) return
    translateSaving.value = true
    try {
      await generateApi.saveChapterEn(chapterNum.value, translateResult.value, filepath.value)
      saveMsg.value = `✅ 第 ${chapterNum.value} 章欧美英文版已保存至 chapters_en/`
    } catch (e: unknown) {
      saveMsg.value = `❌ ${(e as Error).message}`
    } finally {
      translateSaving.value = false
    }
    setTimeout(() => { saveMsg.value = '' }, 4000)
  }

  // ── 出海英文章名全集 (English Chapter Directory) ──
  interface ChapterEnDirectoryItem {
    num: number
    title_zh: string
    title_en: string
    title_en_clean?: string
    summary?: string
  }

  const directoryEnChapters = ref<ChapterEnDirectoryItem[]>([])
  const directoryEnRaw = ref('')
  const directoryEnLoading = ref(false)
  const directoryEnSaving = ref(false)
  const directoryEnState = ref(mkState())
  const localizationTab = ref<'directory' | 'chapter'>('directory')

  async function loadDirectoryEn() {
    if (!filepath.value) return
    directoryEnLoading.value = true
    try {
      const res = await generateApi.getDirectoryEn(filepath.value)
      if (res.data) {
        directoryEnChapters.value = res.data.chapters || []
        directoryEnRaw.value = res.data.raw_text || ''
      }
    } catch (e: unknown) {
      console.warn('Failed to load English chapter directory:', e)
    } finally {
      directoryEnLoading.value = false
    }
  }

  async function saveDirectoryEn(customChapters?: ChapterEnDirectoryItem[], customRaw?: string) {
    if (!filepath.value) return
    directoryEnSaving.value = true
    try {
      const payload: { filepath: string; chapters?: ChapterEnDirectoryItem[]; raw_text?: string } = {
        filepath: filepath.value,
        chapters: customChapters ?? directoryEnChapters.value,
        raw_text: customRaw ?? directoryEnRaw.value,
      }
      const res = await generateApi.saveDirectoryEn(payload)
      saveMsg.value = res.data?.message || '✅ 全书英文章名目录已保存！'
    } catch (e: unknown) {
      saveMsg.value = `❌ 保存英文目录失败: ${(e as Error).message}`
    } finally {
      directoryEnSaving.value = false
    }
    setTimeout(() => { saveMsg.value = '' }, 3500)
  }

  function doTranslateDirectory() {
    const s = directoryEnState.value
    s.running = true
    s.progress = '准备批量翻译全书章名...'
    s.result = ''
    s.error = ''
    const handle = postSSE(
      '/generate/translate_directory',
      {
        llm_config_name: llmConfig.value,
        filepath: filepath.value,
        target_style: translateStyle.value,
        custom_guidance: translateGuidance.value,
      },
      (msg, value) => {
        s.progress = msg
        if (value !== undefined) s.progressValue = value
      },
      (content) => {
        s.result = content
      },
      (err) => {
        s.error = err
        s.running = false
      },
      () => {
        s.running = false
        loadDirectoryEn()
      },
    )
    s.sseHandle = handle
  }

  // ── 独立双语质量质检审计 (Rule 4: Dual-language Audit) ──
  const auditState = ref(mkState())

  function doAuditTranslation(num?: number) {
    const target = num ?? chapterNum.value
    if (!target) return
    const s = auditState.value
    s.running = true
    s.progress = `准备对第 ${target} 章进行双语独立质检审查...`
    s.result = ''
    s.error = ''
    const handle = postSSE(
      '/generate/audit_translation',
      {
        llm_config_name: llmConfig.value,
        filepath: filepath.value,
        chapter_num: target,
      },
      (msg, value) => {
        s.progress = msg
        if (value !== undefined) s.progressValue = value
      },
      (content) => {
        s.result = content
      },
      (err) => {
        s.error = err
        s.running = false
      },
      () => {
        s.running = false
      },
    )
    s.sseHandle = handle
  }

  // ── 全局章节主动联动中枢（选中即同步加载本地，无则清空） ──
  function autoFillChapterParams(num?: number, forceOverwrite = false) {
    const chNum = num ?? chapterNum.value
    if (chNum < 1) return

    const bpText = bp.value.result || ''
    const otText = outlineText.value || ''

    // 1. 抽取大纲块
    const reBp = new RegExp(`第\\s*${chNum}\\s*章[\\s\\S]*?(?=第\\s*\\d+\\s*章|$)`)
    const bpMatch = bpText.match(reBp)
    const bpBlock = bpMatch ? bpMatch[0] : ''

    // 2. 抽取细纲块
    const reOt = new RegExp(`(【第\\s*${chNum}\\s*章细纲】[\\s\\S]*?)(?=【第\\s*\\d+\\s*章细纲】|$)`)
    const otMatch = otText.match(reOt)
    const otBlock = otMatch ? otMatch[1] : ''

    // 3. 涉及人物
    const chars: string[] = []
    const charM = bpBlock.match(/涉及角色[：:]\s*([^\r\n]+)/)
    if (charM && charM[1]) {
      const parts = charM[1].split(/[,，、\s]+/).map(s => s.trim()).filter(Boolean)
      chars.push(...parts)
    }
    const sceneCharsMatches = Array.from(otBlock.matchAll(/场景\d+（[^）]+）：([^\s—\-]+)/g))
    for (const scm of sceneCharsMatches) {
      if (scm && scm[1]) {
        const parts = scm[1].split(/[,，、\s]+/)
        for (const p of parts) {
          const cleanP = p.replace(/\(.*?\)|（.*?）/g, '').trim()
          if (cleanP && !chars.includes(cleanP) && cleanP.length <= 10) {
            chars.push(cleanP)
          }
        }
      }
    }
    if (forceOverwrite || !charactersInvolved.value.trim()) {
      charactersInvolved.value = chars.join('、')
    }

    // 4. 场景地点
    const locations: string[] = []
    const locMatches = Array.from(otBlock.matchAll(/场景\d+（([^）]+)）/g))
    for (const lm of locMatches) {
      if (lm && lm[1]) {
        const cleanLoc = lm[1].split('·')[0].split('（')[0].trim()
        if (cleanLoc && !locations.includes(cleanLoc)) {
          locations.push(cleanLoc)
        }
      }
    }
    if (forceOverwrite || !sceneLocation.value.trim()) {
      sceneLocation.value = locations.length > 0 ? locations.join(' ➔ ') : ''
    }

    // 5. 关键物品
    const itemKeywords = [
      '药剂', '婚契', '信物', '骨坠', '香囊', '银针', '狼纹', '印记', '药膏',
      '剧毒', '拒马', '战獒', '羊皮', '额环', '药鼎', '血契', '草药', '匕首',
      '灵泉', '图腾', '矿石', '诏令', '披风', '法相', '火漆', '暗格'
    ]
    const items: string[] = []
    const fbM = bpBlock.match(/伏笔操作[：:]\s*(?:埋设|强化|回收)?\((.*?)\)/)
    if (fbM && fbM[1]) {
      items.push(fbM[1].trim())
    }
    for (const kw of itemKeywords) {
      const reg = new RegExp(`([^，。；、（—\\s]{0,6}${kw}[^，。；、）—\\s]{0,6})`, 'g')
      const matches = Array.from(otBlock.matchAll(reg))
      for (const m of matches) {
        if (m && m[1]) {
          const phrase = m[1].trim()
          if (phrase && !items.includes(phrase) && phrase.length >= 2 && phrase.length <= 12) {
            items.push(phrase)
            if (items.length >= 5) break
          }
        }
      }
      if (items.length >= 5) break
    }
    if (forceOverwrite || !keyItems.value.trim()) {
      keyItems.value = items.slice(0, 5).join('、')
    }

    // 6. 时间约束
    let extractedTime = ''
    if (otBlock.includes('成年礼') || bpBlock.includes('成年礼')) {
      extractedTime = '成年礼誓约圣典进行时，暴雨降临前夜'
    } else if (otBlock.includes('暴雨') || otBlock.includes('狂暴') || otBlock.includes('避雨')) {
      extractedTime = '雷暴骤雨深夜至破晓黎明前（濒死毒发极端时限）'
    } else if (otBlock.includes('拂晓') || otBlock.includes('黎明') || otBlock.includes('逃离')) {
      extractedTime = '黎明破晓追兵合围前刻（限时逃离生死关头）'
    } else if (otBlock.includes('五年') || bpBlock.includes('五年')) {
      extractedTime = '五年后北境初春，帝国王庭召令下达期'
    } else {
      const posM = bpBlock.match(/本章定位[：:]\s*([^\r\n]+)/)
      extractedTime = posM && posM[1] ? `主线推进阶段（${posM[1].trim()}）` : '当前主线推进关键时间段'
    }
    if (forceOverwrite || !timeConstraint.value.trim()) {
      timeConstraint.value = extractedTime
    }

    // 7. 章节指导
    let extractedGuidance = ''
    const summaryM = bpBlock.match(/本章简述[：:]\s*([^\r\n]+)/)
    const conflictM = otBlock.match(/爽点\/冲突[：:]\s*([^\r\n]+)/)
    if (summaryM && summaryM[1] && conflictM && conflictM[1]) {
      extractedGuidance = `【主线要点】${summaryM[1].trim()} 【核心张力】${conflictM[1].trim()}`
    } else if (summaryM && summaryM[1]) {
      extractedGuidance = summaryM[1].trim()
    } else if (conflictM && conflictM[1]) {
      extractedGuidance = conflictM[1].trim()
    }
    if (forceOverwrite || !chGuidance.value.trim()) {
      chGuidance.value = extractedGuidance
    }

    if (forceOverwrite) {
      saveMsg.value = `✅ 已从第 ${chNum} 章大纲与细纲自动填充 5 项剧情参数！`
      setTimeout(() => { saveMsg.value = '' }, 3000)
    }
  }

  function clearChapterParams() {
    charactersInvolved.value = ''
    keyItems.value = ''
    sceneLocation.value = ''
    timeConstraint.value = ''
    chGuidance.value = ''
    saveMsg.value = '🧹 章节参数已清空'
    setTimeout(() => { saveMsg.value = '' }, 2000)
  }

  async function syncChapterContext(num: number) {
    if (num < 1) return

    // 1. 瞬态执行状态保护性处理（后台正在运行的任务或已完成待确认的结果绝对不被中断或误清）
    if (!finalize.value.running) {
      finalize.value.result = ''
      finalize.value.progress = ''
      finalize.value.error = ''
    }

    if (!humanize.value.running) {
      // 若没有后台去AI任务运行，且非待确认结果所属章节，才做重置
      if (!humanizerPending.value) {
        _resetHumanizerPreview()
        humanize.value.result = ''
        humanize.value.error = ''
      }
    }

    if (!translateState.value.running) {
      translateState.value.result = ''
      translateState.value.progress = ''
      translateState.value.error = ''
    }
    translateResult.value = ''

    // 2. 自动从 50 章目录大纲中同步当前章的【涉及角色】与【章节简述】
    autoFillChapterParams(num)

    // 3. 自动同步当前章的【场景细纲】，无则清空
    if (!outlineText.value) {
      await loadOutlineText()
    } else {
      extractChapterToEdit(num)
    }

    // 4. 尝试从本地加载草稿正文，无则清空
    await loadChapterDraft(num)

    // 5. 尝试从本地加载出海英文译文，无则清空
    await loadChapterEn(num)

    // 5.1 尝试加载该章全套流水线产物快照（草稿、润色、清单、译文等）
    await loadChapterArtifacts(num)

    // 6. 刷新已有章节列表
    await loadExistingChapters()

    // 7. 自动同步当前章的幕间因果交接（Semantic Handoff）
    await loadHandoff(num)
  }

  async function loadHandoff(num?: number) {
    if (!filepath.value) return
    const targetNum = num ?? chapterNum.value
    handoffLoading.value = true
    try {
      const res = await generateApi.getHandoff(targetNum, filepath.value)
      handoffData.value = res.data.handoff
    } catch {
      handoffData.value = null
    }
    handoffLoading.value = false
  }

  async function doColdStartBackfill() {
    if (!filepath.value || !llmConfig.value) return
    coldStartLoading.value = true
    coldStartResult.value = null
    try {
      const res = await generateApi.coldStartBackfill({
        llm_config_name: llmConfig.value,
        filepath: filepath.value,
      })
      coldStartResult.value = res.data
      await loadHandoff()
    } catch (e: any) {
      coldStartResult.value = { success: false, message: e.message || '冷启动回溯失败' }
    }
    coldStartLoading.value = false
  }

  async function doPreWriteGateCheck() {
    if (!filepath.value || !llmConfig.value) return
    preWriteGateLoading.value = true
    preWriteGateResult.value = null
    try {
      const res = await generateApi.preWriteGate({
        llm_config_name: llmConfig.value,
        filepath: filepath.value,
        chapter_num: chapterNum.value,
      })
      preWriteGateResult.value = res.data
    } catch (e: any) {
      preWriteGateResult.value = { passed: true, summary: `体检异常: ${e.message}`, contradictions: [], continuity_warnings: [] }
    }
    preWriteGateLoading.value = false
  }

  async function doSpanRepair() {
    if (!filepath.value || !llmConfig.value || !spanRepairTarget.value.trim()) return
    spanRepairLoading.value = true
    spanRepairResult.value = null
    try {
      const res = await generateApi.spanRepair({
        llm_config_name: llmConfig.value,
        filepath: filepath.value,
        chapter_num: chapterNum.value,
        target_span: spanRepairTarget.value.trim(),
        repair_instruction: spanRepairInstruction.value.trim(),
      })
      spanRepairResult.value = res.data
      if (res.data.success && res.data.repaired_text) {
        chapter.value.result = res.data.repaired_text
      }
    } catch (e: any) {
      spanRepairResult.value = { success: false, message: e.message || '修补失败' }
    }
    spanRepairLoading.value = false
  }

  async function loadFixedTerms() {
    if (!filepath.value) return
    fixedTermsLoading.value = true
    try {
      const res = await generateApi.getFixedTerms(filepath.value)
      fixedTermsContent.value = res.data.content || ''
    } catch {
      // ignore
    } finally {
      fixedTermsLoading.value = false
    }
  }

  async function saveFixedTerms(content?: string) {
    if (!filepath.value) return
    const textToSave = content !== undefined ? content : fixedTermsContent.value
    try {
      await generateApi.saveFixedTerms(filepath.value, textToSave)
      fixedTermsContent.value = textToSave
    } catch {
      // ignore
    }
  }

  async function selectChapter(num: number) {
    if (num < 1) return
    if (pipelineRunning.value) {
      // 流水线生产中：不切换主编辑器的全局 chapterNum，而是平滑打开独立查阅器，不影响后台编译
      openQuickReader(num)
      return
    }
    if (chapterNum.value !== num) {
      chapterNum.value = num
    }
    await syncChapterContext(num)
  }

  function prevChapter() {
    if (chapterNum.value > 1) {
      if (pipelineRunning.value) {
        openQuickReader(chapterNum.value - 1)
      } else {
        selectChapter(chapterNum.value - 1)
      }
    }
  }

  function nextChapter() {
    if (chapterNum.value < numChapters.value) {
      if (pipelineRunning.value) {
        openQuickReader(chapterNum.value + 1)
      } else {
        selectChapter(chapterNum.value + 1)
      }
    }
  }

  watch(chapterNum, (newVal, oldVal) => {
    if (newVal && newVal !== oldVal && !chapter.value.running && !translateState.value.running) {
      syncChapterContext(newVal)
    }
  })

  function doHumanize() {
    _resetHumanizerPreview()
    humanizerChapterNum.value = chapterNum.value
    const s = humanize.value
    s.running = true; s.progress = ''; s.result = ''; s.error = ''; s.progressValue = undefined
    const handle = postSSE(
      '/generate/humanize',
      {
        llm_config_name: llmConfig.value,
        filepath: filepath.value,
        chapter_num: chapterNum.value,
        enable_r8: humanizerR8.value,
        user_focus: humanizerFocus.value,
        depth: humanizerDepth.value,
      },
      (msg, value) => { s.progress = msg; if (value !== undefined) s.progressValue = value },
      (content) => {
        s.result = content
        // 解析 JSON 结果，填充对比预览
        try {
          const data = JSON.parse(content)
          humanizerOriginal.value = data.original ?? ''
          humanizerHumanized.value = data.humanized ?? ''
          humanizerChanges.value = data.changes ?? ''
          humanizerChapterNum.value = data.chapter_num ?? chapterNum.value
          humanizerPending.value = true
          humanizerPreviewTab.value = 'humanized'
        } catch {
          // 非 JSON（错误信息等），直接显示
        }
      },
      (err) => { s.error = err; s.running = false },
      () => { s.running = false; s.sseHandle = null },
    )
    s.sseHandle = handle
  }

  function doBatchHumanize() {
    _resetHumanizerPreview()
    runSSE(humanize.value, '/generate/humanize/batch', {
      llm_config_name: llmConfig.value,
      filepath: filepath.value,
      start_chapter: humanizerStart.value,
      end_chapter: humanizerEnd.value,
      enable_r8: humanizerR8.value,
      user_focus: humanizerFocus.value,
      depth: humanizerDepth.value,
    })
  }

  async function doConfirmHumanize(keepHumanized: boolean) {
    const num = humanizerChapterNum.value
    const text = keepHumanized ? humanizerHumanized.value : humanizerOriginal.value
    if (!text || !num) return
    humanizerSaving.value = true
    try {
      await generateApi.saveChapter(num, text, filepath.value)
      humanize.value.result = keepHumanized
        ? `✅ 第 ${num} 章已保存去 AI 后的版本`
        : `✅ 第 ${num} 章已保留原文`
      humanizerPending.value = false
    } catch (e: unknown) {
      humanize.value.error = (e as Error).message
    }
    humanizerSaving.value = false
  }

  // ── 导出 ──────────────────────────────────────────────────────────────────
  async function doExportNovel() {
    exporting.value = true
    try {
      const res = await generateApi.exportNovel(filepath.value)
      const blob = new Blob([res.data], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'novel_export.txt'
      a.click()
      URL.revokeObjectURL(url)
      saveMsg.value = '✅ 小说已导出'
    } catch (e: unknown) {
      saveMsg.value = `❌ 导出失败: ${(e as Error).message}`
    }
    exporting.value = false
    setTimeout(() => { saveMsg.value = '' }, 3000)
  }

  // ── 续写 ──────────────────────────────────────────────────────────────────
  function doContinueArch() {
    const added = newChapters.value
    const s = continueArch.value
    s.running = true; s.progress = ''; s.result = ''; s.error = ''; s.progressValue = undefined
    const handle = postSSE(
      '/generate/architecture/continue',
      {
        llm_config_name: llmConfig.value, filepath: filepath.value,
        new_chapters: added, user_guidance: continueGuidance.value,
        arch_style_name: contStyle.value === '不使用文风' ? null : contStyle.value || null,
        xp_type: contXpType.value,
        num_characters: contNumCharacters.value,
      },
      (msg, value) => { s.progress = msg; if (value !== undefined) s.progressValue = value },
      (content) => { s.result = content },
      (err) => { s.error = err; s.running = false },
      () => {
        s.running = false; s.sseHandle = null
        if (s.result && !s.error) {
          numChapters.value = numChapters.value + added
          reloadProjectContent()
        }
      },
    )
    s.sseHandle = handle
  }

  // ── 续写分步 ──────────────────────────────────────────────────────────────
  function doContStepSeed() {
    runStepSSE(contStepSeed.value, contSeedText, '/generate/architecture/continue/step/seed', {
      llm_config_name: llmConfig.value, filepath: filepath.value,
      new_chapters: newChapters.value, user_guidance: continueGuidance.value,
      arch_style_name: contStyle.value === '不使用文风' ? null : contStyle.value || null,
      xp_type: contXpType.value,
    })
  }
  function doContStepWorld() {
    runStepSSE(contStepWorld.value, contWorldText, '/generate/architecture/continue/step/world', {
      llm_config_name: llmConfig.value, filepath: filepath.value,
      new_chapters: newChapters.value, user_guidance: continueGuidance.value,
      continuation_seed: contSeedText.value,
      arch_style_name: contStyle.value === '不使用文风' ? null : contStyle.value || null,
      xp_type: contXpType.value,
    })
  }
  function doContStepChars() {
    runStepSSE(contStepChars.value, contCharsText, '/generate/architecture/continue/step/characters', {
      llm_config_name: llmConfig.value, filepath: filepath.value,
      new_chapters: newChapters.value, user_guidance: continueGuidance.value,
      arch_style_name: contStyle.value === '不使用文风' ? null : contStyle.value || null,
      xp_type: contXpType.value,
      num_characters: contNumCharacters.value,
      continuation_seed: contSeedText.value, world_expansion: contWorldText.value,
    })
  }
  function doContSupplementChar() {
    runStepSSE(contSupplementChar.value, contSupplementResult, '/generate/architecture/supplement_characters', {
      llm_config_name: llmConfig.value,
      existing_characters: contCharsText.value,
      supplement_guidance: contSupplementGuidance.value,
      num_characters: contSupplementNum.value,
      core_seed: seedText.value,
      world_building: worldText.value,
      filepath: filepath.value,
    })
  }
  function appendContSupplementChar() {
    if (contSupplementResult.value.trim()) {
      contCharsText.value = contCharsText.value.trimEnd() + '\n\n' + contSupplementResult.value.trim()
      contSupplementResult.value = ''
      contSupplementGuidance.value = ''
    }
  }
  function doContStepArcs() {
    runStepSSE(contStepArcs.value, contArcsText, '/generate/architecture/continue/step/arcs', {
      llm_config_name: llmConfig.value, filepath: filepath.value,
      new_chapters: newChapters.value, user_guidance: continueGuidance.value,
      new_characters_text: contCharsText.value,
      arch_style_name: contStyle.value === '不使用文风' ? null : contStyle.value || null,
      xp_type: contXpType.value,
      continuation_seed: contSeedText.value, world_expansion: contWorldText.value,
    })
  }
  function doContStepCharState() {
    runStepSSE(contStepCharState.value, contCharStateText, '/generate/architecture/continue/step/char_state', {
      llm_config_name: llmConfig.value, filepath: filepath.value,
      new_characters_text: contCharsText.value,
    })
  }
  async function doContAssemble() {
    try {
      const res = await generateApi.assembleContinuation({
        filepath: filepath.value, new_chapters: newChapters.value,
        new_characters_text: contCharsText.value,
        new_arcs_text: contArcsText.value,
        new_char_state_text: contCharStateText.value,
        continuation_seed: contSeedText.value,
        world_expansion: contWorldText.value,
      })
      continueArch.value.result = res.data.content
      if (res.data.new_total_chapters) {
        numChapters.value = res.data.new_total_chapters
      }
    } catch (e: unknown) {
      continueArch.value.error = (e as Error).message
    }
  }

  async function doCompressContext() {
    compressRunning.value = true
    compressResult.value = ''
    try {
      const res = await generateApi.compressContext({
        llm_config_name: llmConfig.value,
        filepath: filepath.value,
        include_world_building: compressWorldBuilding.value,
      })
      compressResult.value = res.data.message
    } catch (e: unknown) {
      compressResult.value = `❌ 压缩失败: ${(e as Error).message}`
    }
    compressRunning.value = false
  }

  return {
    // stores
    projectStore, configStore, generateStore,
    // basic params
    llmConfig, embConfig, filepath,
    topic, genre, numChapters, wordNumber, userGuidance, xpType, xpSelectedPresets, numCharacters, contNumCharacters,
    // styles
    styleList, archStyle, bpStyle, chStyle, chNarrativeStyle, contStyle,
    // step states
    arch, bp, chapter, finalize, expand,
    // step-by-step arch
    stepMode, stepSeed, stepChar, stepCharState, stepWorld, stepPlot,
    seedText, charText, charStateText, worldText, plotText,
    // inject options
    injectCharToWorld,
    // chapter params
    injectWorldBuilding, sceneByScene,
    chapterNum, charactersInvolved, keyItems, sceneLocation, timeConstraint, chGuidance,
    // batch
    batch,
    // continue
    continueArch, newChapters, continueGuidance, contXpType,
    // continue step-by-step
    contStepMode,
    contStepSeed, contSeedText, contStepWorld, contWorldText,
    contStepChars, contStepArcs, contStepCharState,
    contCharsText, contArcsText, contCharStateText,
    // supplement characters
    supplementChar, supplementGuidance, supplementNum, supplementResult,
    doSupplementChar, appendSupplementChar,
    contSupplementChar, contSupplementGuidance, contSupplementNum, contSupplementResult,
    doContSupplementChar, appendContSupplementChar,
    // character dynamics
    characterDynamicsContent,
    // polish
    polishGuidance, polishMode,
    polishIncludeOutline, polishIncludeCharState, polishIncludeSummary, polishIncludeWorld,
    expandOriginal, expandNew, expandChapterNum, saveExpandResult,
    // profile extractor
    profileExtracted, profileShowConfirm, profileConfirmMsg, profileConfirmAppend, profileDismiss,
    // humanizer
    humanize, humanizerBatch, humanizerR8, humanizerFocus,
    humanizerStart, humanizerEnd, humanizerDepth,
    humanizerOriginal, humanizerHumanized, humanizerChanges,
    humanizerPreviewTab, humanizerPending, humanizerSaving, humanizerChapterNum,
    doHumanize, doBatchHumanize, doConfirmHumanize,
    translateState, translateStyle, translateGuidance, translateResult, translateSaving,
    doTranslateChapter, saveChapterEn, loadChapterEn, loadChapterArtifacts,
    directoryEnChapters, directoryEnRaw, directoryEnLoading, directoryEnSaving, directoryEnState, localizationTab,
    loadDirectoryEn, saveDirectoryEn, doTranslateDirectory,
    auditState, doAuditTranslation,
    selectChapter, prevChapter, nextChapter, syncChapterContext, autoFillChapterParams, clearChapterParams,
    // misc
    exporting, saveMsg, reloading,
    // functions
    reloadProjectContent, cancelSSE,
    saveArchitecture, saveBlueprint, saveChapter, saveCharacterDynamics,
    saveComponent, saveCoreSeed, saveCharDynamics, saveCharState, saveWorldBuilding, savePlotArch,
    revisionGuidance, revisionState, revisionContext, doRevise,
    doGenerateArch, doStepSeed, doStepChar, doStepCharState, doStepWorld, doStepPlot, doAssemble,
    doGenerateBP,
    detailedOutline, outlineText, outlineBatchStart, outlineBatchSize, outlineMode,
    outlineBatchResult, outlineBatchBackup, outlineRevisionGuidance, outlineRevision,
    doGenerateOutlineBatch, loadOutlineText, saveOutline, saveBatchOutline, saveSingleChapterOutline,
    doReviseOutlineBatch, revertOutlineBatch, extractChapterToEdit, currentChapterOutline,
    existingChapters, loadExistingChapters, loadChapterDraft,
    doGenerateChapter, doFinalize,
    // improv mode
    workflowMode, setWorkflowMode,
    improvBlueprint, improvOutline, improvChapter,
    improvIntent, improvBlueprintText, improvOutlineText, openThreadsText,
    doGenerateImprovBlueprint, saveImprovBlueprint, loadImprovBlueprint,
    doGenerateImprovOutline, saveImprovOutline, loadImprovOutline,
    doGenerateImprovChapter, saveImprovChapter,
    loadOpenThreads, saveOpenThreadsText,
    // improv 修订
    improvBlueprintRevise, improvOutlineRevise,
    improvBlueprintRevisionGuidance, improvOutlineRevisionGuidance,
    doReviseImprovBlueprint, doReviseImprovOutline,
    doBatchGenerate, doExpand, doExportNovel,
    doContinueArch, doContStepSeed, doContStepWorld, doContStepChars, doContStepArcs, doContStepCharState, doContAssemble,
    compressRunning, compressResult, compressWorldBuilding, doCompressContext,
    // pipeline control room
    // view mode
    workshopViewMode, setWorkshopViewMode,
    // pipeline control room
    pipelineOpen, pipelineRunning, pipelineElapsed, pipelineStages, pipelineMode, setPipelineMode, defaultPipelineStages,
    pipelineActiveTab, pipelineAutoRetry, pipelineStatusMsg, pipelineAutoAdvance,
    fastIncubating, fastIncubateProgress, doFastIncubateBook,
    pipelineProgressVal, pipelineCurrentStageId, pipelineTargetChapter, pipelineTerminalLogs,
    pipelineData, openPipelineControlRoom, closePipelineControlRoom,
    doRunPipeline, cancelPipeline,
    pipelineReviewStrength, setReviewStrength, pipelineContextToggles,
    batchQueueRunning, batchQueuePaused, batchQueueStart, batchQueueEnd, batchQueueCurrent,
    batchQueueStatusMap, doRunBatchQueue, togglePauseBatchQueue, stopBatchQueue,
    whitepaperModalOpen, openWhitepaperModal, closeWhitepaperModal,
    quickReaderOpen, quickReaderChapter, openQuickReader, closeQuickReader,
    // continuity & semantic handoff
    handoffData, handoffLoading, coldStartLoading, coldStartResult,
    preWriteGateLoading, preWriteGateResult, spanRepairLoading,
    spanRepairTarget, spanRepairInstruction, spanRepairResult,
    loadHandoff, doColdStartBackfill, doPreWriteGateCheck, doSpanRepair,
    adultMode, fixedTermsContent, fixedTermsLoading, loadFixedTerms, saveFixedTerms,
  }
}
