# -*- coding: utf-8 -*-
import os

print("=== 更新前端流水线双模式切换 ===")

# 1. 更新 frontend/src/composables/useWorkshopState.ts
ws_path = "frontend/src/composables/useWorkshopState.ts"
with open(ws_path, "r", encoding="utf-8") as f:
    ws = f.read()

# 增加 pipelineMode 响应式变量与根据模式切换 stages 的函数
target_default_stages = """  const defaultPipelineStages = (): PipelineStageInfo[] => [
    { id: 1, name: '细纲与因果交接装配', subtitle: '装配上章交接契约(Handoff)、开篇禁令与正史设定', icon: '🔗', status: 'idle', progress: 0, targetProgress: 0 },
    { id: 2, name: '中文分场景起草', subtitle: '分场景起草，直写情绪与动作指纹', icon: '✍️', status: 'idle', progress: 0, targetProgress: 0 },
    { id: 3, name: '朱雀自检与 GPT 审校', subtitle: '腾讯朱雀 AI 雷达病灶扫描 + Codex (GPT) 靶向改写', icon: '🛡️', status: 'idle', progress: 0, targetProgress: 0 },
    { id: 4, name: '出海美式英文译制', subtitle: '高忠实度、纯正母语、专有词表映射', icon: '🇺🇸', status: 'idle', progress: 0, targetProgress: 0 },
    { id: 5, name: '双语质量独立审计', subtitle: '双语对照严格自检，超标智能重试1次', icon: '⚖️', status: 'idle', progress: 0, targetProgress: 0 },
    { id: 6, name: '正史演进与交接归档', subtitle: '提炼下章交接契约(Handoff)、演进正史页与全书记忆', icon: '📜', status: 'idle', progress: 0, targetProgress: 0 },
  ]"""

replacement_default_stages = """  const pipelineMode = ref<'fast_zh' | 'bilingual'>('fast_zh')

  const defaultPipelineStages = (): PipelineStageInfo[] => {
    if (pipelineMode.value === 'fast_zh') {
      return [
        { id: 1, name: '细纲与因果交接装配', subtitle: '装配上章交接契约(Handoff)、开篇禁令与正史设定', icon: '🔗', status: 'idle', progress: 0, targetProgress: 0 },
        { id: 2, name: '中文分场景起草', subtitle: '分场景起草，直写情绪与动作指纹 (Gemini Low 极速出字)', icon: '✍️', status: 'idle', progress: 0, targetProgress: 0 },
        { id: 3, name: '朱雀自检与 GPT 审校', subtitle: '腾讯朱雀 AI 雷达病灶扫描 + Codex (GPT) 靶向改写', icon: '🛡️', status: 'idle', progress: 0, targetProgress: 0 },
        { id: 4, name: '正史演进与交接归档', subtitle: '提炼下章交接契约(Handoff)、演进正史页与全书记忆', icon: '📜', status: 'idle', progress: 0, targetProgress: 0 },
      ]
    }
    return [
      { id: 1, name: '细纲与因果交接装配', subtitle: '装配上章交接契约(Handoff)、开篇禁令与正史设定', icon: '🔗', status: 'idle', progress: 0, targetProgress: 0 },
      { id: 2, name: '中文分场景起草', subtitle: '分场景起草，直写情绪与动作指纹', icon: '✍️', status: 'idle', progress: 0, targetProgress: 0 },
      { id: 3, name: '朱雀自检与 GPT 审校', subtitle: '腾讯朱雀 AI 雷达病灶扫描 + Codex (GPT) 靶向改写', icon: '🛡️', status: 'idle', progress: 0, targetProgress: 0 },
      { id: 4, name: '出海美式英文译制', subtitle: '高忠实度、纯正母语、专有词表映射', icon: '🇺🇸', status: 'idle', progress: 0, targetProgress: 0 },
      { id: 5, name: '双语质量独立审计', subtitle: '双语对照严格自检，超标智能重试1次', icon: '⚖️', status: 'idle', progress: 0, targetProgress: 0 },
      { id: 6, name: '正史演进与交接归档', subtitle: '提炼下章交接契约(Handoff)、演进正史页与全书记忆', icon: '📜', status: 'idle', progress: 0, targetProgress: 0 },
    ]
  }"""

# 在 doRunPipeline 中传递 pipeline_mode
target_payload = """        auto_retry_translation: pipelineAutoRetry.value,
        scene_by_scene: sceneByScene.value,"""

replacement_payload = """        auto_retry_translation: pipelineAutoRetry.value,
        scene_by_scene: sceneByScene.value,
        pipeline_mode: pipelineMode.value,"""

# 在 return 对象中导出 pipelineMode 和 defaultPipelineStages
target_return = "    pipelineOpen, pipelineRunning, pipelineElapsed, pipelineStages,"
replacement_return = "    pipelineOpen, pipelineRunning, pipelineElapsed, pipelineStages, pipelineMode, defaultPipelineStages,"

ws_norm = ws.replace("\r\n", "\n")
t_stages_norm = target_default_stages.replace("\r\n", "\n")
r_stages_norm = replacement_default_stages.replace("\r\n", "\n")
t_pay_norm = target_payload.replace("\r\n", "\n")
r_pay_norm = replacement_payload.replace("\r\n", "\n")
t_ret_norm = target_return.replace("\r\n", "\n")
r_ret_norm = replacement_return.replace("\r\n", "\n")

if t_stages_norm in ws_norm and t_pay_norm in ws_norm and t_ret_norm in ws_norm:
    ws_norm = ws_norm.replace(t_stages_norm, r_stages_norm, 1)
    ws_norm = ws_norm.replace(t_pay_norm, r_pay_norm, 1)
    ws_norm = ws_norm.replace(t_ret_norm, r_ret_norm, 1)
    with open(ws_path, "w", encoding="utf-8") as f:
        f.write(ws_norm)
    print("✅ useWorkshopState.ts 升级双模式支持成功")
else:
    print("❌ useWorkshopState.ts 目标未找到:", t_stages_norm in ws_norm, t_pay_norm in ws_norm, t_ret_norm in ws_norm)

# 2. 更新 frontend/src/components/workshop/PipelineControlRoom.vue
pcr_path = "frontend/src/components/workshop/PipelineControlRoom.vue"
with open(pcr_path, "r", encoding="utf-8") as f:
    pcr = f.read()

# 在 handleNodeClick 中兼容 4 步模式
target_node_click = """    case 6:
      props.state.pipelineActiveTab.value = 'continuity'
      props.state.loadHandoff(props.state.chapterNum.value)
      fetchCanonHistory()
      break"""

replacement_node_click = """    case 4:
      if (props.state.pipelineMode?.value === 'fast_zh') {
        props.state.pipelineActiveTab.value = 'continuity'
        props.state.loadHandoff(props.state.chapterNum.value)
        fetchCanonHistory()
      } else {
        props.state.pipelineActiveTab.value = 'translation'
        if (!displayTranslation.value) {
          props.state.loadChapterEn(props.state.chapterNum.value)
        }
      }
      break
    case 6:
      props.state.pipelineActiveTab.value = 'continuity'
      props.state.loadHandoff(props.state.chapterNum.value)
      fetchCanonHistory()
      break"""

# 在控制台头部插入模式选择胶囊
target_header_btns = """        <div class="flex items-center gap-3">
          <!-- 智能重试开关 -->"""

mode_toggle_html = """        <div class="flex items-center gap-3">
          <!-- 🍅 番茄/纯中文模式 VS 🌐 出海双语模式 切换器 -->
          <div class="flex items-center bg-stone-900 border border-stone-800 p-0.5 rounded-lg text-xs">
            <button
              @click="state.pipelineMode.value = 'fast_zh'; state.pipelineStages.value = state.defaultPipelineStages()"
              :class="[
                'px-2.5 py-1 rounded font-semibold transition-all cursor-pointer flex items-center gap-1',
                state.pipelineMode.value === 'fast_zh' ? 'bg-rose-950 text-rose-300 border border-rose-800/80 shadow-sm' : 'text-stone-400 hover:text-stone-200'
              ]"
              type="button"
            >
              <span>🍅</span><span>番茄/纯中文模式 (极速4步)</span>
            </button>
            <button
              @click="state.pipelineMode.value = 'bilingual'; state.pipelineStages.value = state.defaultPipelineStages()"
              :class="[
                'px-2.5 py-1 rounded font-semibold transition-all cursor-pointer flex items-center gap-1',
                state.pipelineMode.value === 'bilingual' ? 'bg-cyan-950 text-cyan-300 border border-cyan-800/80 shadow-sm' : 'text-stone-400 hover:text-stone-200'
              ]"
              type="button"
            >
              <span>🌐</span><span>出海双语模式 (完整6步)</span>
            </button>
          </div>

          <!-- 智能重试开关 -->"""

pcr_norm = pcr.replace("\r\n", "\n")
t_nc_norm = target_node_click.replace("\r\n", "\n")
r_nc_norm = replacement_node_click.replace("\r\n", "\n")
t_hb_norm = target_header_btns.replace("\r\n", "\n")
r_hb_norm = mode_toggle_html.replace("\r\n", "\n")

if t_nc_norm in pcr_norm and t_hb_norm in pcr_norm:
    pcr_norm = pcr_norm.replace(t_nc_norm, r_nc_norm, 1)
    pcr_norm = pcr_norm.replace(t_hb_norm, r_hb_norm, 1)
    with open(pcr_path, "w", encoding="utf-8") as f:
        f.write(pcr_norm)
    print("✅ PipelineControlRoom.vue 胶囊切换按钮与节点点击适配完成")
else:
    print("❌ PipelineControlRoom.vue 目标未找到:", t_nc_norm in pcr_norm, t_hb_norm in pcr_norm)

print("=== 前端双模式支持更新完成 ===")
