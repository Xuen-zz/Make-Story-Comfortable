import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// ── 响应拦截器：统一错误处理 ──────────────────────────────────────────────────
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const raw = err.response?.data?.detail ?? err.message ?? '请求失败'
    const msg = Array.isArray(raw) ? raw.map((e: any) => e.msg ?? JSON.stringify(e)).join('; ') : String(raw)
    return Promise.reject(new Error(msg))
  }
)

// ── Projects ─────────────────────────────────────────────────────────────────
export const projectsApi = {
  list: () => api.get('/projects'),
  create: (name: string, filepath = '') => api.post('/projects', { name, filepath }),
  activate: (name: string) => api.post(`/projects/${encodeURIComponent(name)}/activate`),
  update: (name: string, data: Record<string, unknown>) =>
    api.put(`/projects/${encodeURIComponent(name)}`, data),
  delete: (name: string) => api.delete(`/projects/${encodeURIComponent(name)}`),
  active: () => api.get('/projects/active'),
  discover: () => api.post('/projects/discover'),
  listBackups: (name: string) =>
    api.get(`/projects/${encodeURIComponent(name)}/backups`),
  createBackup: (name: string, note = '') =>
    api.post(`/projects/${encodeURIComponent(name)}/backups`, null, { params: { note } }),
  restoreBackup: (name: string, backupId: string) =>
    api.post(`/projects/${encodeURIComponent(name)}/backups/${encodeURIComponent(backupId)}/restore`),
  deleteBackup: (name: string, backupId: string) =>
    api.delete(`/projects/${encodeURIComponent(name)}/backups/${encodeURIComponent(backupId)}`),
}

// ── Config ───────────────────────────────────────────────────────────────────
export const configApi = {
  listLLM: () => api.get('/config/llm'),
  saveLLM: (data: Record<string, unknown>) => api.post('/config/llm', data),
  deleteLLM: (name: string) => api.delete(`/config/llm/${encodeURIComponent(name)}`),
  listEmbedding: () => api.get('/config/embedding'),
  saveEmbedding: (data: Record<string, unknown>) => api.post('/config/embedding', data),
  deleteEmbedding: (name: string) =>
    api.delete(`/config/embedding/${encodeURIComponent(name)}`),
  testLLM: () => `/config/llm/test`,
  testEmbedding: () => `/config/embedding/test`,
  getProxy: () => api.get('/config/proxy'),
  saveProxy: (data: { proxy_url: string; proxy_port: string; enabled: boolean }) =>
    api.put('/config/proxy', data),
  getUserProfile: () => api.get('/config/user_profile'),
  saveUserProfile: (profile: string, enabled = true) => api.put('/config/user_profile', { profile, enabled }),
  extractPreferences: (text: string, llm_config_name: string) =>
    api.post('/config/user_profile/extract', { text, llm_config_name }),
  appendProfile: (preferences: string) =>
    api.post('/config/user_profile/append', { preferences }),
  getQualityGuard: () => api.get('/config/quality_guard'),
  saveQualityGuard: (data: Record<string, unknown>) => api.post('/config/quality_guard', data),
  testZhuque: (data: { zhuque_api_key: string }) => api.post('/config/zhuque/test', data),
  testCodex: (data: { codex_model?: string }) => api.post('/config/codex/test', data),
}

// ── Presets ──────────────────────────────────────────────────────────────────
export const presetsApi = {
  list: () => api.get('/presets'),
  activate: (name: string) => api.post(`/presets/${encodeURIComponent(name)}/activate`),
  save: (name: string, description = '') => api.post('/presets', { name, description }),
  delete: (name: string) => api.delete(`/presets/${encodeURIComponent(name)}`),
  getPrompts: () => api.get('/presets/prompts'),
  updatePrompt: (key: string, content: string) =>
    api.put(`/presets/prompts/${encodeURIComponent(key)}`, { content }),
  resetPrompt: (key: string) =>
    api.post(`/presets/prompts/${encodeURIComponent(key)}/reset`),
}

// ── Generate (SSE) ────────────────────────────────────────────────────────────

export interface SSEHandle {
  abort: () => void
}

/**
 * 创建一个 EventSource 连接到 SSE 端点（POST via fetch）。
 * 同步返回 SSEHandle，可通过 abort() 取消操作。
 */
export function postSSE(
  url: string,
  body: Record<string, unknown>,
  onProgress: (msg: string, value?: number, content?: string) => void,
  onResult: (content: string) => void,
  onError: (msg: string) => void,
  onDone: () => void,
): SSEHandle {
  const controller = new AbortController()
  let operationId = ''

  const handle: SSEHandle = {
    abort: () => {
      // 通知后端取消
      if (operationId) {
        fetch('/api/generate/cancel', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ operation_id: operationId }),
        }).catch(() => {})
      }
      controller.abort()
    },
  }

  // 异步处理 SSE 流（fire-and-forget）
  ;(async () => {
    try {
      const res = await fetch(`/api${url}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        onError(err.detail ?? res.statusText)
        onDone()
        return
      }

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const parse = (raw: string) => {
        const lines = raw.split('\n')
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const json = line.slice(6).trim()
          if (!json) continue
          try {
            const event = JSON.parse(json)
            if (event.type === 'started') operationId = event.operation_id ?? ''
            else if (event.type === 'progress') onProgress(event.message ?? '', event.value, event.content)
            else if (event.type === 'result') onResult(event.content ?? '')
            else if (event.type === 'error') onError(event.message ?? '未知错误')
            else if (event.type === 'done') onDone()
          } catch {
            // ignore malformed event
          }
        }
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''
        for (const part of parts) parse(part + '\n\n')
      }
      if (buffer) parse(buffer)
    } catch (e: unknown) {
      // AbortError is normal when user cancels
      if (e instanceof DOMException && e.name === 'AbortError') {
        onDone()
      } else {
        onError((e as Error).message ?? '请求失败')
        onDone()
      }
    }
  })()

  return handle
}

export const generateApi = {
  architecture: (body: Record<string, unknown>) => `/generate/architecture`,
  blueprint: (body: Record<string, unknown>) => `/generate/blueprint`,
  chapter: (body: Record<string, unknown>) => `/generate/chapter`,
  finalize: (body: Record<string, unknown>) => `/generate/finalize`,
  expand: (body: Record<string, unknown>) => `/generate/expand`,
  status: (filepath: string) => api.get(`/generate/status`, { params: { filepath } }),
  chapters: (filepath: string) => api.get(`/generate/chapters`, { params: { filepath } }),
  dashboard: (filepath: string) => api.get(`/generate/dashboard`, { params: { filepath } }),
  getChapter: (num: number, filepath: string) =>
    api.get(`/generate/chapter/${num}`, { params: { filepath } }),
  saveChapter: (num: number, content: string, filepath: string) =>
    api.put(`/generate/chapter/${num}`, { content }, { params: { filepath } }),
  getChapterEn: (num: number, filepath: string) =>
    api.get(`/generate/chapter_en/${num}`, { params: { filepath } }),
  saveChapterEn: (num: number, content: string, filepath: string) =>
    api.put(`/generate/chapter_en/${num}`, { content }, { params: { filepath } }),
  getChapterArtifacts: (num: number, filepath: string) =>
    api.get(`/generate/chapter_artifacts/${num}`, { params: { filepath } }),
  contextPreview: (chapter_num: number, filepath: string) =>
    api.get(`/generate/chapter_context_preview`, { params: { chapter_num, filepath } }),
  pipelineChapter: () => `/generate/pipeline_chapter`,
  translateChapter: () => `/generate/translate`,
  getDirectoryEn: (filepath: string) =>
    api.get(`/generate/directory_en`, { params: { filepath } }),
  saveDirectoryEn: (body: { filepath: string; chapters?: any[]; raw_text?: string }) =>
    api.put(`/generate/directory_en`, body),
  translateDirectory: () => `/generate/translate_directory`,
  auditTranslation: () => `/generate/audit_translation`,
  saveArchitecture: (content: string, filepath: string) =>
    api.put(`/generate/architecture`, { content, filepath }),
  saveComponent: (component: string, content: string, filepath: string) =>
    api.put(`/generate/architecture/component/${component}`, { content, filepath }),
  saveBlueprint: (content: string, filepath: string) =>
    api.put(`/generate/blueprint`, { content, filepath }),
  saveCharacterDynamics: (content: string, filepath: string) =>
    api.put(`/generate/character_dynamics`, { content, filepath }),
  exportNovel: (filepath: string) =>
    api.get(`/generate/export`, { params: { filepath }, responseType: 'blob' }),
  partialSteps: (filepath: string) =>
    api.get(`/generate/architecture/partial`, { params: { filepath } }),
  assembleArch: (body: Record<string, unknown>) =>
    api.post(`/generate/architecture/assemble`, body),
  continueArch: (body: Record<string, unknown>) => `/generate/architecture/continue`,
  contStepSeed: () => `/generate/architecture/continue/step/seed`,
  contStepWorld: () => `/generate/architecture/continue/step/world`,
  continueStepCharacters: () => `/generate/architecture/continue/step/characters`,
  continueStepArcs: () => `/generate/architecture/continue/step/arcs`,
  continueStepCharState: () => `/generate/architecture/continue/step/char_state`,
  assembleContinuation: (body: Record<string, unknown>) =>
    api.post(`/generate/architecture/continue/assemble`, body),
  compressContext: (body: { llm_config_name: string; filepath: string; include_world_building?: boolean }) =>
    api.post(`/generate/compress-context`, body, { timeout: 600000 }),
  humanize: () => `/generate/humanize`,
  batchHumanize: () => `/generate/humanize/batch`,
  reviseStep: () => `/generate/architecture/step/revise`,
  detailedOutline: () => `/generate/detailed_outline`,
  getDetailedOutline: (filepath: string) =>
    api.get(`/generate/detailed_outline`, { params: { filepath } }),
  saveDetailedOutline: (content: string, filepath: string) =>
    api.put(`/generate/detailed_outline`, { content, filepath }),
  stepCoreSeed: () => `/generate/architecture/step/core_seed`,
  stepCharacters: () => `/generate/architecture/step/characters`,
  stepWorld: () => `/generate/architecture/step/world`,
  stepPlot: () => `/generate/architecture/step/plot`,
  // ── 即兴写作模式 ──
  workflowMode: (filepath: string) =>
    api.get(`/generate/workflow_mode`, { params: { filepath } }),
  blueprintSingleUrl: () => `/generate/blueprint_single`,
  blueprintSingleReviseUrl: () => `/generate/blueprint_single/revise`,
  outlineSingleUrl: () => `/generate/outline_single`,
  outlineSingleReviseUrl: () => `/generate/outline_single/revise`,
  chapterImprovUrl: () => `/generate/chapter_improv`,
  getBlueprintSingle: (num: number, filepath: string) =>
    api.get(`/generate/blueprint_single/${num}`, { params: { filepath } }),
  saveBlueprintSingle: (num: number, content: string, filepath: string) =>
    api.put(`/generate/blueprint_single/${num}`, { content, filepath }),
  getOutlineSingle: (num: number, filepath: string) =>
    api.get(`/generate/outline_single/${num}`, { params: { filepath } }),
  saveOutlineSingle: (num: number, content: string, filepath: string) =>
    api.put(`/generate/outline_single/${num}`, { content, filepath }),
  getOpenThreads: (filepath: string) =>
    api.get(`/generate/open_threads`, { params: { filepath } }),
  saveOpenThreads: (content: string, filepath: string) =>
    api.put(`/generate/open_threads`, { content, filepath }),
  // ── 因果连续性与幕间交接（Semantic Handoff & Continuity） ──
  getHandoff: (chapterNum: number, filepath: string) =>
    api.get(`/generate/handoff`, { params: { chapter_num: chapterNum, filepath } }),
  coldStartBackfill: (body: { llm_config_name: string; filepath: string; max_chapters?: number }) =>
    api.post(`/generate/cold_start_backfill`, body),
  preWriteGate: (body: { llm_config_name: string; filepath: string; chapter_num: number }) =>
    api.post(`/generate/pre_write_gate`, body),
  spanRepair: (body: { llm_config_name: string; filepath: string; chapter_num: number; target_span: string; repair_instruction: string }) =>
    api.post(`/generate/span_repair`, body),
  getCanonHistory: (filepath: string) =>
    api.get(`/generate/canon_history`, { params: { filepath } }),
  updateCanonHistory: (body: { llm_config_name: string; filepath: string; chapter_num: number }) =>
    api.post(`/generate/update_canon_history`, body),
  getFixedTerms: (filepath: string) =>
    api.get('/generate/fixed_terms', { params: { filepath } }),
  saveFixedTerms: (filepath: string, content: string) =>
    api.post('/generate/fixed_terms', { filepath, content }),
  getPipelineRules: () =>
    api.get('/generate/pipeline_rules'),
  runScriptAudit: (data: { text_zh?: string; text_en?: string }) =>
    api.post('/generate/script_audit', data),
}

// ── XP Presets ───────────────────────────────────────────────────────────────
export const xpPresetsApi = {
  list: () => api.get('/xp-presets'),
  create: (name: string, content: string) => api.post('/xp-presets', { name, content }),
  update: (name: string, data: { name?: string; content?: string }) =>
    api.put(`/xp-presets/${encodeURIComponent(name)}`, data),
  delete: (name: string) => api.delete(`/xp-presets/${encodeURIComponent(name)}`),
}

// ── Styles ───────────────────────────────────────────────────────────────────
export const stylesApi = {
  list: () => api.get('/styles'),
  get: (name: string) => api.get(`/styles/${encodeURIComponent(name)}`),
  save: (name: string, data: Record<string, unknown>) =>
    api.put(`/styles/${encodeURIComponent(name)}`, data),
  delete: (name: string) => api.delete(`/styles/${encodeURIComponent(name)}`),
  rollbackCalibration: (name: string) =>
    api.post(`/styles/${encodeURIComponent(name)}/rollback-calibration`),
  analyzeUrl: () => `/styles/analyze`,
  analyzeDNAUrl: () => `/styles/analyze-dna`,
  mergeUrl: () => `/styles/merge`,
  calibrateUrl: () => `/styles/calibrate`,
  calibrateNarrativeUrl: () => `/styles/calibrate-narrative`,
  importAuthorRef: (name: string, formData: FormData) =>
    api.post(`/styles/${encodeURIComponent(name)}/author-reference/import`, formData, {
      headers: { 'Content-Type': undefined },
    }),
  clearAuthorRef: (name: string) =>
    api.delete(`/styles/${encodeURIComponent(name)}/author-reference`),
  authorRefStatus: (name: string) =>
    api.get(`/styles/${encodeURIComponent(name)}/author-reference/status`),
}

// ── Knowledge ─────────────────────────────────────────────────────────────────
export const knowledgeApi = {
  import: (formData: FormData) =>
    api.post('/knowledge/import', formData, {
      headers: { 'Content-Type': undefined },
    }),
  clear: (filepath: string) =>
    api.delete('/knowledge', { params: { filepath } }),
}

// ── Files ────────────────────────────────────────────────────────────────────
export const filesApi = {
  list: (filepath: string) => api.get('/files', { params: { filepath } }),
  content: (filepath: string, path: string) =>
    api.get('/files/content', { params: { filepath, path } }),
  save: (filepath: string, path: string, content: string) =>
    api.put('/files/content', { content }, { params: { filepath, path } }),
}

// ── Logs ─────────────────────────────────────────────────────────────────────
export const logsApi = {
  get: (tail = 200) => api.get('/logs', { params: { tail } }),
  clear: () => api.delete('/logs'),
  getPrompts: (tail = 50, search = '') =>
    api.get('/logs/prompts', { params: { tail, search } }),
  clearPrompts: () => api.delete('/logs/prompts'),
}

// ── Consistency ───────────────────────────────────────────────────────────────
export const consistencyApi = {
  checkUrl: () => `/consistency/check`,
}

// ── Brainstorm ───────────────────────────────────────────────────────────────
export const brainstormApi = {
  chatUrl: () => `/brainstorm/chat`,
}

// ── ComfyUI Workflow Canvas ──────────────────────────────────────────────────
export const workflowApi = {
  catalog: () => api.get('/workflow/catalog'),
  list: () => api.get('/workflow/list'),
  save: (body: { id?: string; name: string; description?: string; nodes: unknown[]; edges: unknown[] }) =>
    api.post('/workflow/save', body),
  remove: (wfId: string) => api.delete(`/workflow/${encodeURIComponent(wfId)}`),
  setDefault: (workflow_id: string) => api.post('/workflow/set_default', { workflow_id }),
  executeUrl: () => `/workflow/execute`,
  gateDecision: (runId: string, body: { action: 'approve' | 'cancel'; selected_branch?: string; edited_text?: string }) =>
    api.post(`/workflow/gate/${encodeURIComponent(runId)}`, body),
  cancel: (runId: string) => api.post(`/workflow/cancel/${encodeURIComponent(runId)}`),
}

// ── 独立模型提供商与桌面系统 API ──────────────────────────────────────────────
export const providersApi = {
  list: () => api.get('/config/providers'),
  save: (body: Record<string, unknown>) => api.post('/config/providers/save', body),
  fetchModels: (body: { interface_format: string; base_url: string; api_key: string }) =>
    api.post('/config/providers/fetch_models', body),
  testConnection: (body: { interface_format: string; base_url: string; api_key: string; model_name: string }) =>
    api.post('/config/providers/test_connection', body),
}

export const systemApi = {
  info: () => api.get('/system/info'),
  setBooksRoot: (books_root: string) => api.post('/system/books_root', { books_root }),
}

// ── 核心创作记忆与资产 API (三层立体防吃书架构) ──────────────────────────────
export const assetsApi = {
  getWorldState: (filepath?: string) => api.get('/assets/world_state', { params: { filepath } }),
  saveWorldState: (body: { filepath?: string; state: Record<string, unknown> }) =>
    api.post('/assets/world_state', body),
  getEntities: (filepath?: string) => api.get('/assets/entities', { params: { filepath } }),
  saveEntity: (body: { filepath?: string; item: Record<string, unknown> }) =>
    api.post('/assets/entities', body),
  deprecateEntity: (body: { filepath?: string; entity_id: string; chapter_num: number }) =>
    api.post('/assets/entities/deprecate', body),
  extractDelta: (body: {
    filepath?: string
    chapter_num: number
    chapter_text: string
    character_names?: string[]
    auto_apply?: boolean
    llm_config_name?: string
  }) => api.post('/assets/extract_delta', body),
}
