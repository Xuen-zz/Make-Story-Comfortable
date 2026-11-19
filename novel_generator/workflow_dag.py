# novel_generator/workflow_dag.py
# -*- coding: utf-8 -*-
"""
ComfyUI 风格节点式小说工作流编排与真 DAG 执行引擎：
- 严格分型端口规范 + 多线合流汇聚（多条 MEMORY / CHECKLIST 边自动拼接）
- 全量写作资产节点（人物小传、前章尾段、RAG知识库、伏笔池、禁用词锁、便签、合流器）
- 写前防吃书预检、确定性脚本去AI评分质检、章末断章钩子外科手术精修
- 5 套官方内置预设模板 + 用户自定义工作流持久化 + 真拓扑/局部缓存重跑/Bypass/Human Gate
"""

import json
import os
import re
import time
import logging
import threading
from uuid import uuid4
from typing import Any, Dict, List, Optional, Tuple

from utils import read_file, save_string_to_txt

logger = logging.getLogger(__name__)

from app_paths import get_data_file
WORKFLOW_STORE_FILE = get_data_file("workflow_store.json")

# ── 默认可编辑 Prompt 模板 ─────────────────────────────────────────────────────

DEFAULT_REVIEW_STRONG_PROMPT = """你是一位拥有二十年畅销网文出版与爆款运营经验的资深中文总编辑。请对以下章节草稿执行【强力去AI味 + 节奏审校】。

【审校与去AI味六大铁律】：
1. 严守剧情主线：只改表达、节奏与画面质感，严禁篡改故事主线、人物立场、设定口径与因果走向。
2. 彻底清除中文大模型机械句式壳（重点查杀）：
   - 禁绝机械对照与转折壳：『不是……而是……』『与其说……不如说……』『不仅……更……』『真正重要的是……』『本质上……』；
   - 禁绝机械三段排比与对称短句（如全篇清一色 10~15 字单句独立成段，或“她蹲下身，拭去血珠，检查伤口”式整齐三连动作）；
   - 必须拉大长短句错落感：具体动作与环境阻力长句（30~50字）➔ 突然接一个 2~5 字极短独立句（如“没应。”“咔嚓。”）➔ 穿插口语短促对白。
3. 彻底封杀 AI 生理反射套话与假深沉旁白：
   - 严禁出现：『深吸一口气』『眼底闪过一抹』『勾起一抹冷笑』『嘴角微扬』『空气仿佛凝固』『瞳孔骤缩』『喉结上下滚动』『倒吸一口凉气』『指尖轻颤』『不知为何』『不得不说』『这一刻，他终于明白了……』；
   - 严禁作者代替读者总结情绪或下结论，必须用“具体器物阻力、动作反应、带刺的口语台词”让读者自己看出来。
4. 人物对话口语化、有区分度：删去播音腔、讲义腔和翻译腔，让每个人物按身份说话带出潜台词与性格。
5. 核对事实与知情边界：对照参考资料中的细纲、角色状态、前文摘要与世界观，修正常识矛盾、物件持有或视角越界。
6. 守住章末强断章钩子：本章最后 150 字严禁平淡泄气收尾，必须卡在危机爆发、利益翻盘、反转或新人物入局的最紧绷处！

【输出格式要求】：
先输出审校润色后的完整正式章节正文；
然后另起一行输出分隔符 `---`，紧随其后输出 `【修改清单】`，用简明要点列出：删掉了哪些 AI 套话/机械句式、强化了哪几处动作与钩子。

===== 章节原文 =====
{chapter_text}
"""

DEFAULT_REVIEW_LIGHT_PROMPT = """你是一位专业中文小说审稿编辑。请对以下章节草稿执行【轻度流畅润色 + 逻辑校对】。

【润色准则】：
1. 最大程度保留原草稿的文风、句式和叙事习惯，不做大刀阔斧的改写。
2. 仅修正以下问题：错别字与语病、明显重复啰嗦的句子、零星突兀的 AI 套话（如“空气仿佛凝固”“眼底闪过一抹”）、以及对照参考资料修正人物称谓或设定矛盾。
3. 确保章末最后几句过渡自然且保有悬念，不平淡流水账收尾。

【输出格式要求】：
先输出润色后的完整正式章节正文；
然后另起一行输出分隔符 `---`，紧随其后输出 `【修改清单】`，简要说明修正的语句与校对点。

===== 章节原文 =====
{chapter_text}
"""

DEFAULT_CUSTOM_REWRITE_PROMPT = """你是一位精通畅销中文网文节奏与对话张力的金牌精修编辑。请根据下方的精修目标对章节正文做定向加强。

【精修目标】：
{instruction}

【底线要求】：
- 不篡改既定核心剧情因果与人物立场
- 保持画面感与口语化台词，杜绝 AI 套话和机械总结

【输出格式要求】：
直接输出改写后的完整章节正文；如需附修改说明，请在末尾另起一行用 `---` 分隔后写出 `【修改清单】`。

===== 章节原文 =====
{chapter_text}
"""

DEFAULT_ENDING_HOOK_PROMPT = """你是一位番茄/起点白金网文责编，专精【章末黄金断章钩子】。
下方提供了一章正文的「前情承接尾声」（仅作接续语境参考）与需要重写的「本章结尾片段」。

【任务要求】：
只重写【待重写结尾片段】，不得重复输出前情承接内容，也不得改动前面已写完的剧情事实！
请用强冲突、突如其来的反常细节、利益陡转、冷脸摊牌或新威胁逼近，把结尾卡在读者最迫不及待想点“下一章”的那一瞬间。字数与原结尾相近（约 {tail_chars} 字左右），严禁出现“这一刻他下定了决心”“未来的路还长”等泄气旁白总结！

===== 前情承接（只看不输出） =====
{prefix_context}

===== 待重写结尾片段 =====
{tail_text}

请直接输出重写后的结尾正文："""

DEFAULT_DRAFT_PROMPT_TEMPLATE = """（留空表示直接调用系统内置「中文十条铁律 + 因果交接」起草引擎；如需完全接管起草 Prompt，请填写模板，支持变量：{chapter_num}、{word_number}、{outline}、{context_bundle}、{guidance}）"""


# ── 中文网文脚本级去 AI 味评分规则 ─────────────────────────────────────────────

_ZH_AI_CLICHE_PATTERNS = [
    ("AI生理套话", r"(深吸一口气|眼底闪过一抹|勾起一抹冷笑|嘴角微扬|嘴角勾起|空气仿佛凝固|瞳孔骤缩|瞳孔猛地一缩|喉结上下滚动|倒吸一口凉气|指尖微颤|指尖轻颤|声音冰冷得不带一丝温度)"),
    ("AI机械对照壳", r"(不是[^。！？\n]{1,22}而是|与其说[^。！？\n]{1,22}不如说|不仅[^。！？\n]{1,22}更是|真正重要的是|归根结底|本质上)"),
    ("AI旁白总结", r"(不知为何|不得不说|换句话说|这一刻[，,]?[他她它]终于明白|命运的齿轮|一切才刚刚开始)"),
]


def score_chinese_webnovel_text(text: str, target_words: int = 2500) -> Dict[str, Any]:
    """对中文小说章节运行零 Token 确定性去AI与节奏脚本评分（0~100分）。"""
    from novel_generator.pipeline_rules import DeterministicRuleChecker

    clean = (text or "").strip()
    if not clean:
        return {"score": 0, "passed": False, "word_count": 0, "issues": ["正文为空"], "summary": "正文为空 (0分)"}

    base_report = DeterministicRuleChecker.run_full_script_audit(text_zh=clean)
    score = 100
    issues: List[str] = []

    for label, pat in _ZH_AI_CLICHE_PATTERNS:
        matches = re.findall(pat, clean)
        if matches:
            deduct = min(18, len(matches) * 3)
            score -= deduct
            uniq = list(dict.fromkeys(matches))[:5]
            issues.append(f"【{label}】命中 {len(matches)} 处（例：{'、'.join(uniq)}），建议删改 -{deduct}分")

    np_cnt = base_report["negative_parallelism"]["total_count"]
    if np_cnt > 2:
        deduct = min(12, (np_cnt - 2) * 4)
        score -= deduct
        issues.append(f"【否定排比偏多】共 {np_cnt} 处（上限≤2），-{deduct}分")

    if base_report["exceeded_sliding_words"]:
        deduct = min(10, len(base_report["exceeded_sliding_words"]) * 3)
        score -= deduct
        issues.append(f"【高频重复词】{', '.join(base_report['exceeded_sliding_words'])} -{deduct}分")

    if base_report["repetitive_spans"]:
        score -= 15
        issues.append(f"【疑似重复段落】检测到 {len(base_report['repetitive_spans'])} 处超长相似段落 -15分")

    # 句段节奏检测：连续过多短段落一律单行
    paras = [p.strip() for p in re.split(r"\n+", clean) if p.strip()]
    if len(paras) >= 8:
        short_uniform = sum(1 for p in paras if 8 <= len(p) <= 24)
        ratio = short_uniform / len(paras)
        if ratio > 0.72:
            score -= 8
            issues.append(f"【节奏同质化】{int(ratio*100)}% 段落集中于10~24字短句，建议拉大长短句错落 -8分")

    word_cnt = len(clean)
    if target_words > 0 and word_cnt < int(target_words * 0.65):
        score -= 10
        issues.append(f"【篇幅偏短】当前 {word_cnt} 字，低于目标 {target_words} 字的 65% -10分")

    score = max(0, min(100, score))
    header = f"🧪 脚本质检得分：{score}/100 分（正文字数：{word_cnt} 字，共发现 {len(issues)} 项隐患）"
    summary_text = header + ("\n" + "\n".join(f"- {it}" for it in issues) if issues else "\n✅ 未检测到明显 AI 机械句式或节奏隐患！")
    return {
        "score": score,
        "passed": score >= 80,
        "word_count": word_cnt,
        "issues": issues,
        "summary": summary_text,
    }


# ── 运行时会话注册表（用于 Human Gate / A-B 选版暂停与恢复、取消） ────────────────

class WorkflowRunSession:
    def __init__(self, run_id: str, chapter_num: int):
        self.run_id = run_id
        self.chapter_num = chapter_num
        self.cancelled = False
        self.gate_event = threading.Event()
        self.gate_decision: Dict[str, Any] = {}
        self.created_at = time.time()

    def reset_gate(self):
        self.gate_event.clear()
        self.gate_decision = {}

    def submit_gate(self, decision: Dict[str, Any]):
        self.gate_decision = decision or {}
        self.gate_event.set()

    def cancel(self):
        self.cancelled = True
        self.gate_decision = {"action": "cancel"}
        self.gate_event.set()


_RUN_SESSIONS: Dict[str, WorkflowRunSession] = {}
_RUN_LOCK = threading.Lock()


def get_run_session(run_id: str) -> Optional[WorkflowRunSession]:
    with _RUN_LOCK:
        return _RUN_SESSIONS.get(run_id)


def _register_session(session: WorkflowRunSession):
    with _RUN_LOCK:
        now = time.time()
        stale = [k for k, v in _RUN_SESSIONS.items() if now - v.created_at > 7200]
        for k in stale:
            _RUN_SESSIONS.pop(k, None)
        _RUN_SESSIONS[session.run_id] = session


# ── 端口数据类型色标与全量原子节点库目录 ─────────────────────────────────────────

PORT_TYPES = {
    "BOOK_PLAN": {"label": "立项参数", "color": "#60a5fa"},
    "CHAPTER_CTX": {"label": "章节与字数", "color": "#38bdf8"},
    "OUTLINE": {"label": "细纲", "color": "#f59e0b"},
    "MEMORY": {"label": "设定/记忆资产", "color": "#2dd4bf"},
    "STYLE": {"label": "文风/指令", "color": "#ec4899"},
    "MODEL": {"label": "模型配置", "color": "#22c55e"},
    "TEXT": {"label": "正文文本", "color": "#a855f7"},
    "CHECKLIST": {"label": "质检/修改清单", "color": "#94a3b8"},
}


def get_node_catalog() -> Dict[str, Any]:
    return {
        "port_types": PORT_TYPES,
        "default_prompts": {
            "review_strong": DEFAULT_REVIEW_STRONG_PROMPT,
            "review_light": DEFAULT_REVIEW_LIGHT_PROMPT,
            "custom_rewrite": DEFAULT_CUSTOM_REWRITE_PROMPT,
            "ending_hook": DEFAULT_ENDING_HOOK_PROMPT,
            "draft_note": DEFAULT_DRAFT_PROMPT_TEMPLATE,
        },
        "categories": [
            {
                "id": "planning",
                "label": "🧭 全书开荒与大纲规划",
                "nodes": [
                    {
                        "type": "idea_seed",
                        "title": "💡 立意与全书参数",
                        "desc": "填写题材、一句话脑洞、总章数（默认200章）与每章目标字数，开启新书从零开荒流。",
                        "inputs": [],
                        "outputs": [
                            {"id": "book_brief", "label": "立项蓝图", "type": "BOOK_PLAN"},
                            {"id": "chapter_num", "label": "起始章参数", "type": "CHAPTER_CTX"},
                        ],
                        "defaultParams": {"topic": "", "genre": "都市爽文", "num_chapters": 200, "word_number": 2500, "user_guidance": ""},
                    },
                    {
                        "type": "arch_generator",
                        "title": "🏛️ 雪花架构生成器",
                        "desc": "基于立项参数自动推演全书核心种子、人物关系、世界观与主线大纲（已有架构且未勾选强制重跑则直接读取复用）。",
                        "inputs": [
                            {"id": "book_brief", "label": "立项参数", "type": "BOOK_PLAN"},
                            {"id": "model_config", "label": "模型(可选)", "type": "MODEL"},
                        ],
                        "outputs": [{"id": "arch_text", "label": "全书架构", "type": "OUTLINE"}],
                        "defaultParams": {"llm_config_name": "", "force_regen": False},
                    },
                    {
                        "type": "directory_generator",
                        "title": "🗺️ 全书目录生成器",
                        "desc": "根据全书架构分批规划 200 章全书目录骨架（支持断点复用已生成目录）。",
                        "inputs": [
                            {"id": "book_brief", "label": "立项参数", "type": "BOOK_PLAN"},
                            {"id": "arch_text", "label": "全书架构", "type": "OUTLINE"},
                            {"id": "model_config", "label": "模型(可选)", "type": "MODEL"},
                        ],
                        "outputs": [
                            {"id": "directory_text", "label": "全书目录", "type": "OUTLINE"},
                            {"id": "chapter_num", "label": "章节起点", "type": "CHAPTER_CTX"},
                        ],
                        "defaultParams": {"llm_config_name": "", "force_regen": False, "start_chapter": 1},
                    },
                    {
                        "type": "batch_outline_gate",
                        "title": "📑 分批细纲与人工审核",
                        "desc": "按 10 章一批生成可编辑分场细纲，支持自动暂停等待你过目修改，放行后直连起草节点！",
                        "inputs": [
                            {"id": "chapter_num", "label": "章节起点", "type": "CHAPTER_CTX"},
                            {"id": "directory_text", "label": "全书目录", "type": "OUTLINE"},
                            {"id": "model_config", "label": "模型(可选)", "type": "MODEL"},
                        ],
                        "outputs": [{"id": "outline", "label": "当前章细纲", "type": "OUTLINE"}],
                        "defaultParams": {"batch_start": 1, "batch_size": 10, "outline_mode": "concise", "pause_for_review": True, "force_regen": False},
                    },
                ],
            },
            {
                "id": "input",
                "label": "📥 基础资产加载",
                "nodes": [
                    {
                        "type": "chapter_input",
                        "title": "📘 书籍与章节选号",
                        "desc": "设定当前章号与目标字数，沿着连线完整透传给细纲、上下文与起草节点。",
                        "inputs": [],
                        "outputs": [{"id": "chapter_num", "label": "章节与字数", "type": "CHAPTER_CTX"}],
                        "defaultParams": {"chapter_num": 1, "word_number": 2500},
                    },
                    {
                        "type": "outline_loader",
                        "title": "📑 章节细纲加载器",
                        "desc": "读取本章规划细纲；支持节点内临时覆盖，供记忆节点、写前预检与审校校对使用。",
                        "inputs": [{"id": "chapter_num", "label": "章节", "type": "CHAPTER_CTX"}],
                        "outputs": [{"id": "outline", "label": "本章细纲", "type": "OUTLINE"}],
                        "defaultParams": {"auto_complete": True, "override_outline": ""},
                    },
                    {
                        "type": "memory_assembler",
                        "title": "🧠 记忆上下文组装器",
                        "desc": "带 5 项总开关（前文摘要、角色状态、世界观、正史、上章Handoff），可快速打包或再与细粒度资产合并。",
                        "inputs": [
                            {"id": "chapter_num", "label": "章节", "type": "CHAPTER_CTX"},
                            {"id": "outline", "label": "细纲", "type": "OUTLINE"},
                        ],
                        "outputs": [{"id": "context_bundle", "label": "基础记忆包", "type": "MEMORY"}],
                        "defaultParams": {
                            "inject_summary": True,
                            "inject_char_state": True,
                            "inject_world_building": True,
                            "inject_canon": True,
                            "inject_handoff": True,
                        },
                    },
                    {
                        "type": "style_prompt",
                        "title": "🎨 文风与导演指令",
                        "desc": "指定章节文风 DNA、叙事风格、XP 卖点标签及导演特别补充指令。",
                        "inputs": [],
                        "outputs": [{"id": "style_config", "label": "文风指令", "type": "STYLE"}],
                        "defaultParams": {
                            "style_name": "",
                            "narrative_style_name": "",
                            "xp_type": "",
                            "user_guidance": "",
                        },
                    },
                    {
                        "type": "llm_config",
                        "title": "🤖 LLM 模型配置节点",
                        "desc": "独立挂载模型与温度参数，可接给任意多个生成/改写节点复用。",
                        "inputs": [],
                        "outputs": [{"id": "model_config", "label": "模型配置", "type": "MODEL"}],
                        "defaultParams": {"llm_config_name": "Gemini 3.8 Flash (内置免密)", "temperature": 0.7},
                    },
                ],
            },
            {
                "id": "granular_assets",
                "label": "🧩 细粒度扩展资产 & 合流",
                "nodes": [
                    {
                        "type": "character_profile",
                        "title": "🎭 人物关系与人设档案",
                        "desc": "读取核心人设与人物弧光（Character_dynamics），防止长篇连载中主角或反派性格 OOC。",
                        "inputs": [{"id": "chapter_num", "label": "章节(可选)", "type": "CHAPTER_CTX"}],
                        "outputs": [{"id": "context_bundle", "label": "人物档案资产", "type": "MEMORY"}],
                        "defaultParams": {"max_chars": 2500},
                    },
                    {
                        "type": "prev_excerpt_loader",
                        "title": "📖 前章正文尾段衔接",
                        "desc": "精准截取第 N-1 章结尾原文（默认 800 字，可调 300~1500），保证开篇动作与台词无缝咬合。",
                        "inputs": [{"id": "chapter_num", "label": "章节", "type": "CHAPTER_CTX"}],
                        "outputs": [{"id": "context_bundle", "label": "前章尾段", "type": "MEMORY"}],
                        "defaultParams": {"tail_chars": 800},
                    },
                    {
                        "type": "rag_retriever",
                        "title": "🔍 RAG 向量知识库检索",
                        "desc": "基于细纲或自定义关键词从本地向量知识库检索相关设定与技法片段（可在节点内直接预览捞取结果）。",
                        "inputs": [
                            {"id": "chapter_num", "label": "章节", "type": "CHAPTER_CTX"},
                            {"id": "outline", "label": "细纲(可选)", "type": "OUTLINE"},
                        ],
                        "outputs": [{"id": "context_bundle", "label": "RAG 检索片段", "type": "MEMORY"}],
                        "defaultParams": {"top_k": 4, "query_override": ""},
                    },
                    {
                        "type": "foreshadow_loader",
                        "title": "🪝 伏笔与未收线索池",
                        "desc": "挂载全局待回收伏笔（open_threads），提醒模型在本章适时埋点或收坑。",
                        "inputs": [{"id": "chapter_num", "label": "章节(可选)", "type": "CHAPTER_CTX"}],
                        "outputs": [{"id": "context_bundle", "label": "伏笔线索", "type": "MEMORY"}],
                        "defaultParams": {"extra_foreshadow": ""},
                    },
                    {
                        "type": "forbidden_lock",
                        "title": "🚫 禁用词与称谓锁",
                        "desc": "强约束 AI 高频禁用套话黑名单与固定称谓表，写审双阶段强拦截。",
                        "inputs": [],
                        "outputs": [{"id": "context_bundle", "label": "禁用词黑名单", "type": "MEMORY"}],
                        "defaultParams": {
                            "forbidden_words": "深吸一口气, 眼底闪过一抹, 勾起一抹冷笑, 空气仿佛凝固, 瞳孔骤缩, 嘴角微扬, 不知为何, 不是……而是, 与其说……不如说",
                            "term_locks": "",
                        },
                    },
                    {
                        "type": "note_primitive",
                        "title": "📝 参考便签 (Note)",
                        "desc": "类似 ComfyUI Primitive 便签节点，记录临时剧情要求、人物台词金句并连给多个下游节点。",
                        "inputs": [],
                        "outputs": [{"id": "context_bundle", "label": "便签文本", "type": "MEMORY"}],
                        "defaultParams": {"note_title": "临时设定补充", "note_content": ""},
                    },
                    {
                        "type": "context_combiner",
                        "title": "🔀 上下文合流拼装节点",
                        "desc": "将多路细粒度资产（记忆包、人设、前章尾段、RAG、伏笔、禁用词、便签）汇聚为单一干净的记忆束往下游传递。",
                        "inputs": [
                            {"id": "ctx_1", "label": "资产源 1", "type": "MEMORY"},
                            {"id": "ctx_2", "label": "资产源 2", "type": "MEMORY"},
                            {"id": "ctx_3", "label": "资产源 3", "type": "MEMORY"},
                            {"id": "ctx_4", "label": "资产源 4", "type": "MEMORY"},
                            {"id": "ctx_5", "label": "资产源 5", "type": "MEMORY"},
                            {"id": "ctx_6", "label": "资产源 6", "type": "MEMORY"},
                        ],
                        "outputs": [{"id": "context_bundle", "label": "合并完整上下文", "type": "MEMORY"}],
                        "defaultParams": {},
                    },
                ],
            },
            {
                "id": "process",
                "label": "⚙️ 预检、AI 生成与质检精修",
                "nodes": [
                    {
                        "type": "pre_write_gate",
                        "title": "🚦 写前防吃书预检 Gate",
                        "desc": "动笔前拿细纲核对正史与 Handoff；如存在设定冲突，可输出纠偏清单或自动暂停拦截。",
                        "inputs": [
                            {"id": "chapter_num", "label": "章节", "type": "CHAPTER_CTX"},
                            {"id": "outline", "label": "待检细纲", "type": "OUTLINE"},
                            {"id": "model_config", "label": "模型(可选)", "type": "MODEL"},
                        ],
                        "outputs": [
                            {"id": "outline", "label": "放行细纲", "type": "OUTLINE"},
                            {"id": "checklist", "label": "冲突预警清单", "type": "CHECKLIST"},
                        ],
                        "defaultParams": {"llm_config_name": "Gemini 3.8 Flash (内置免密)", "on_fail": "append_hint"},
                    },
                    {
                        "type": "draft_writer",
                        "title": "✍️ AI 起草节点",
                        "desc": "根据细纲、合流记忆与文风起草正文（支持多根记忆线直连自动合并，不污染正式磁盘）。",
                        "inputs": [
                            {"id": "chapter_num", "label": "章节与字数", "type": "CHAPTER_CTX"},
                            {"id": "outline", "label": "细纲", "type": "OUTLINE"},
                            {"id": "context_bundle", "label": "记忆上下文(可多连)", "type": "MEMORY"},
                            {"id": "style_config", "label": "文风指令", "type": "STYLE"},
                            {"id": "model_config", "label": "模型(可选)", "type": "MODEL"},
                        ],
                        "outputs": [{"id": "draft_text", "label": "初稿正文", "type": "TEXT"}],
                        "defaultParams": {
                            "llm_config_name": "Gemini 3.8 Flash (内置免密)",
                            "temperature": 0.7,
                            "word_number": 0,
                            "scene_by_scene": True,
                            "writing_guidance": "",
                            "custom_prompt_template": "",
                        },
                    },
                    {
                        "type": "script_audit",
                        "title": "🧪 脚本去AI与字数质检",
                        "desc": "零 Token 瞬时统计 AI 套话、机械对照壳、节奏同质化与篇幅并打分；不达标可带清单给下游 AI 整改或暂停。",
                        "inputs": [
                            {"id": "text_in", "label": "待检正文", "type": "TEXT"},
                            {"id": "chapter_num", "label": "章节目标字数", "type": "CHAPTER_CTX"},
                        ],
                        "outputs": [
                            {"id": "text_out", "label": "检测后正文", "type": "TEXT"},
                            {"id": "checklist", "label": "脚本问题清单", "type": "CHECKLIST"},
                        ],
                        "defaultParams": {"min_score": 80, "on_fail": "pass_to_ai"},
                    },
                    {
                        "type": "deai_reviewer",
                        "title": "🛡️ 去AI味审校节点",
                        "desc": "结合细纲、记忆与上游脚本隐患清单执行强力去AI味/轻度润色，输出定稿与修改清单。",
                        "inputs": [
                            {"id": "draft_text", "label": "输入正文", "type": "TEXT"},
                            {"id": "outline", "label": "细纲(可选)", "type": "OUTLINE"},
                            {"id": "context_bundle", "label": "记忆上下文(可多连)", "type": "MEMORY"},
                            {"id": "style_config", "label": "文风(可选)", "type": "STYLE"},
                            {"id": "checklist", "label": "待改隐患(可选)", "type": "CHECKLIST"},
                            {"id": "model_config", "label": "模型(可选)", "type": "MODEL"},
                        ],
                        "outputs": [
                            {"id": "polished_text", "label": "审校定稿", "type": "TEXT"},
                            {"id": "checklist", "label": "修改清单", "type": "CHECKLIST"},
                        ],
                        "defaultParams": {
                            "llm_config_name": "Gemini 4 Hydrogen (Medium)",
                            "temperature": 0.5,
                            "review_strength": "strong",
                            "custom_guidance": "执行严格审校与强力去AI味润色，保留剧情主线并强化章末断章钩子",
                            "custom_prompt_template": DEFAULT_REVIEW_STRONG_PROMPT,
                        },
                    },
                    {
                        "type": "custom_rewrite",
                        "title": "✨ 自定义指令改写节点",
                        "desc": "插接任意多阶精修（如台词尖锐化、节奏压缩、情绪加强）。",
                        "inputs": [
                            {"id": "text_in", "label": "输入正文", "type": "TEXT"},
                            {"id": "outline", "label": "细纲(可选)", "type": "OUTLINE"},
                            {"id": "context_bundle", "label": "参考记忆(可多连)", "type": "MEMORY"},
                            {"id": "style_config", "label": "文风(可选)", "type": "STYLE"},
                            {"id": "model_config", "label": "模型(可选)", "type": "MODEL"},
                        ],
                        "outputs": [
                            {"id": "text_out", "label": "改写后正文", "type": "TEXT"},
                            {"id": "checklist", "label": "改写说明", "type": "CHECKLIST"},
                        ],
                        "defaultParams": {
                            "llm_config_name": "Gemini 4 Hydrogen (Medium)",
                            "temperature": 0.55,
                            "instruction": "重点强化主角反击时的压迫感与台词潜台词，并让章末最后120字卡在最紧绷的悬念瞬间。",
                            "custom_prompt_template": DEFAULT_CUSTOM_REWRITE_PROMPT,
                        },
                    },
                    {
                        "type": "ending_hook_rewriter",
                        "title": "✂️ 章末断章钩子精修",
                        "desc": "仅切片重写章节最后 300~600 字，绝不改动前文已定剧情，专注打磨爆款卡点结尾。",
                        "inputs": [
                            {"id": "text_in", "label": "输入正文", "type": "TEXT"},
                            {"id": "outline", "label": "细纲(可选)", "type": "OUTLINE"},
                            {"id": "model_config", "label": "模型(可选)", "type": "MODEL"},
                        ],
                        "outputs": [
                            {"id": "text_out", "label": "强化钩子后正文", "type": "TEXT"},
                            {"id": "checklist", "label": "结尾改动对比", "type": "CHECKLIST"},
                        ],
                        "defaultParams": {
                            "llm_config_name": "Gemini 4 Hydrogen (Medium)",
                            "temperature": 0.65,
                            "tail_chars": 420,
                            "custom_prompt_template": DEFAULT_ENDING_HOOK_PROMPT,
                        },
                    },
                ],
            },
            {
                "id": "control",
                "label": "🔀 验收、对比与落盘",
                "nodes": [
                    {
                        "type": "diff_preview",
                        "title": "⚖️ 红绿 Diff 对比预览",
                        "desc": "对比改写前后文本差异并展示修改清单，透传定稿文本继续往下游走。",
                        "inputs": [
                            {"id": "text_a", "label": "原稿(左)", "type": "TEXT"},
                            {"id": "text_b", "label": "新稿(右)", "type": "TEXT"},
                            {"id": "checklist", "label": "修改清单", "type": "CHECKLIST"},
                        ],
                        "outputs": [{"id": "text_out", "label": "定稿文本", "type": "TEXT"}],
                        "defaultParams": {},
                    },
                    {
                        "type": "ab_selector",
                        "title": "🔀 A/B 双分支择优对比",
                        "desc": "接入两条对比分支，运行至此暂停，人工红绿对比后点选采纳 A 或 B。",
                        "inputs": [
                            {"id": "branch_a", "label": "分支 A 正文", "type": "TEXT"},
                            {"id": "branch_b", "label": "分支 B 正文", "type": "TEXT"},
                            {"id": "checklist_a", "label": "A 清单(可选)", "type": "CHECKLIST"},
                            {"id": "checklist_b", "label": "B 清单(可选)", "type": "CHECKLIST"},
                        ],
                        "outputs": [
                            {"id": "selected_text", "label": "胜出正文", "type": "TEXT"},
                            {"id": "selected_checklist", "label": "胜出清单", "type": "CHECKLIST"},
                        ],
                        "defaultParams": {"auto_pick": "pause"},
                    },
                    {
                        "type": "human_gate",
                        "title": "✋ 人工审核放行卡点",
                        "desc": "运行至此暂停，审阅修改并点击「确认放行」后再写入正史与长期记忆。",
                        "inputs": [
                            {"id": "text_in", "label": "待审正文", "type": "TEXT"},
                            {"id": "draft_text", "label": "对照原初稿(可选)", "type": "TEXT"},
                            {"id": "checklist", "label": "修改清单(可选)", "type": "CHECKLIST"},
                        ],
                        "outputs": [{"id": "approved_text", "label": "放行正文", "type": "TEXT"}],
                        "defaultParams": {"gate_mode": "always", "note": "人工过目防崩章卡点"},
                    },
                    {
                        "type": "save_chapter",
                        "title": "💾 章节定稿保存",
                        "desc": "将最终定稿写入 chapters/chapter_N.txt 与初稿备份，供阅读器与工单台读取。",
                        "inputs": [
                            {"id": "chapter_num", "label": "章节", "type": "CHAPTER_CTX"},
                            {"id": "final_text", "label": "最终定稿", "type": "TEXT"},
                            {"id": "draft_text", "label": "初稿备份(可选)", "type": "TEXT"},
                            {"id": "checklist", "label": "修改清单(可选)", "type": "CHECKLIST"},
                        ],
                        "outputs": [{"id": "final_text", "label": "已保存正文", "type": "TEXT"}],
                        "defaultParams": {"overwrite": True},
                    },
                    {
                        "type": "memory_archive",
                        "title": "📜 正史与 Handoff 记忆归档",
                        "desc": "提炼全局摘要、角色能力表、正史演进与下一章因果交接契约。",
                        "inputs": [
                            {"id": "chapter_num", "label": "章节", "type": "CHAPTER_CTX"},
                            {"id": "final_text", "label": "已定稿正文", "type": "TEXT"},
                        ],
                        "outputs": [{"id": "handoff", "label": "下章交接记忆", "type": "MEMORY"}],
                        "defaultParams": {"llm_config_name": "Gemini 3.8 Flash (内置免密)", "update_canon": True},
                    },
                ],
            },
        ],
    }


def _mk_node(nid: str, ntype: str, label: str, x: float, y: float, params: dict = None, parent_group: str = None) -> dict:
    catalog = get_node_catalog()
    meta = None
    for cat in catalog["categories"]:
        for item in cat["nodes"]:
            if item["type"] == ntype:
                meta = item
                break
    merged_params = dict(meta["defaultParams"] if meta else {})
    if params:
        merged_params.update(params)
    node = {
        "id": nid,
        "type": "workflowNode",
        "position": {"x": x, "y": y},
        "data": {
            "nodeType": ntype,
            "label": label or (meta["title"] if meta else ntype),
            "params": merged_params,
            "bypass": False,
            "collapsed": False,
        },
    }
    if parent_group:
        node["parentNode"] = parent_group
        node["extent"] = "parent"
    return node


def _mk_edge(eid: str, src: str, src_handle: str, tgt: str, tgt_handle: str, color: str = "#94a3b8") -> dict:
    return {
        "id": eid,
        "source": src,
        "sourceHandle": src_handle,
        "target": tgt,
        "targetHandle": tgt_handle,
        "type": "smoothstep",
        "animated": False,
        "style": {"stroke": color, "strokeWidth": 2.2},
    }


def get_builtin_workflows() -> List[Dict[str, Any]]:
    """5 套官方预设工作流模板（修复全部连线传参 + 新增全资产示范流）。"""
    # 1. 标准双模型写审链（升级版：补充人设+前章尾段+脚本去AI质检）
    standard_zh = {
        "id": "standard_zh",
        "name": "🔥 标准双模型写审链（含人设/前章/脚本质检）",
        "description": "选号与细纲 -> 记忆/人设/前章尾段合流 -> 3.8 Flash 起草 -> 脚本去AI质检 -> 4 Hydrogen 审校 -> 红绿Diff -> 保存归档",
        "builtin": True,
        "nodes": [
            _mk_node("n_book", "chapter_input", "📘 章节选号起点", 40, 140),
            _mk_node("n_style", "style_prompt", "🎨 文风与导演指令", 40, 400),
            _mk_node("n_outline", "outline_loader", "📑 章节细纲加载", 350, 60),
            _mk_node("n_memory", "memory_assembler", "🧠 记忆上下文 (5项开关)", 350, 260),
            _mk_node("n_chars", "character_profile", "🎭 人物人设档案", 350, 480),
            _mk_node("n_prev", "prev_excerpt_loader", "📖 前章尾段衔接", 350, 660),
            _mk_node("n_combine", "context_combiner", "🔀 上下文合流", 690, 320),
            _mk_node("n_draft", "draft_writer", "✍️ 3.8 Flash 分场景起草", 1030, 180),
            _mk_node("n_audit", "script_audit", "🧪 脚本去AI初检", 1370, 180),
            _mk_node("n_review", "deai_reviewer", "🛡️ 4 Hydrogen 去AI审校", 1710, 180),
            _mk_node("n_diff", "diff_preview", "⚖️ 初稿 vs 定稿红绿Diff", 2060, 400),
            _mk_node("n_save", "save_chapter", "💾 章节定稿落盘", 2060, 140),
            _mk_node("n_archive", "memory_archive", "📜 正史与Handoff归档", 2400, 140),
        ],
        "edges": [
            _mk_edge("e1", "n_book", "chapter_num", "n_outline", "chapter_num", "#38bdf8"),
            _mk_edge("e2", "n_book", "chapter_num", "n_memory", "chapter_num", "#38bdf8"),
            _mk_edge("e3", "n_outline", "outline", "n_memory", "outline", "#f59e0b"),
            _mk_edge("e_c1", "n_book", "chapter_num", "n_chars", "chapter_num", "#38bdf8"),
            _mk_edge("e_p1", "n_book", "chapter_num", "n_prev", "chapter_num", "#38bdf8"),
            _mk_edge("e_m1", "n_memory", "context_bundle", "n_combine", "ctx_1", "#2dd4bf"),
            _mk_edge("e_m2", "n_chars", "context_bundle", "n_combine", "ctx_2", "#2dd4bf"),
            _mk_edge("e_m3", "n_prev", "context_bundle", "n_combine", "ctx_3", "#2dd4bf"),
            _mk_edge("e4", "n_book", "chapter_num", "n_draft", "chapter_num", "#38bdf8"),
            _mk_edge("e5", "n_outline", "outline", "n_draft", "outline", "#f59e0b"),
            _mk_edge("e6", "n_combine", "context_bundle", "n_draft", "context_bundle", "#2dd4bf"),
            _mk_edge("e7", "n_style", "style_config", "n_draft", "style_config", "#ec4899"),
            _mk_edge("e8", "n_draft", "draft_text", "n_audit", "text_in", "#a855f7"),
            _mk_edge("e_a2", "n_book", "chapter_num", "n_audit", "chapter_num", "#38bdf8"),
            _mk_edge("e8b", "n_audit", "text_out", "n_review", "draft_text", "#a855f7"),
            _mk_edge("e8c", "n_audit", "checklist", "n_review", "checklist", "#94a3b8"),
            _mk_edge("e9", "n_outline", "outline", "n_review", "outline", "#f59e0b"),
            _mk_edge("e10", "n_combine", "context_bundle", "n_review", "context_bundle", "#2dd4bf"),
            _mk_edge("e11", "n_style", "style_config", "n_review", "style_config", "#ec4899"),
            _mk_edge("e12", "n_draft", "draft_text", "n_diff", "text_a", "#a855f7"),
            _mk_edge("e13", "n_review", "polished_text", "n_diff", "text_b", "#a855f7"),
            _mk_edge("e14", "n_review", "checklist", "n_diff", "checklist", "#94a3b8"),
            _mk_edge("e15", "n_book", "chapter_num", "n_save", "chapter_num", "#38bdf8"),
            _mk_edge("e16", "n_review", "polished_text", "n_save", "final_text", "#a855f7"),
            _mk_edge("e17", "n_draft", "draft_text", "n_save", "draft_text", "#a855f7"),
            _mk_edge("e18", "n_review", "checklist", "n_save", "checklist", "#94a3b8"),
            _mk_edge("e19", "n_book", "chapter_num", "n_archive", "chapter_num", "#38bdf8"),
            _mk_edge("e20", "n_save", "final_text", "n_archive", "final_text", "#a855f7"),
        ],
    }

    # 2. 全资产透明精细流（示范所有细粒度节点最佳接线）
    full_transparent_pro = {
        "id": "full_transparent_pro",
        "name": "🔬 全资产透明精细流（RAG/伏笔/禁用词/钩子精修）",
        "description": "把细纲写前预检、人设、前章尾段、RAG检索、伏笔池、禁用词锁、脚本质检与章末断章钩子精修全部显式连出的最强控制流",
        "builtin": True,
        "nodes": [
            {
                "id": "grp_assets",
                "type": "groupNode",
                "position": {"x": 330, "y": 240},
                "style": {"width": "680px", "height": "780px"},
                "data": {"nodeType": "group", "label": "全量细粒度资产装配区", "color": "#14b8a6"},
            },
            _mk_node("n_book", "chapter_input", "📘 章节选号起点", 30, 120),
            _mk_node("n_style", "style_prompt", "🎨 文风与导演指令", 30, 360),
            _mk_node("n_note", "note_primitive", "📝 临时剧情便签", 30, 620),
            _mk_node("n_outline", "outline_loader", "📑 章节细纲加载", 350, 40),
            _mk_node("n_pregate", "pre_write_gate", "🚦 写前防吃书预检", 690, 40),
            _mk_node("n_memory", "memory_assembler", "🧠 基础记忆开关", 20, 40, None, "grp_assets"),
            _mk_node("n_chars", "character_profile", "🎭 人物关系与人设", 20, 230, None, "grp_assets"),
            _mk_node("n_prev", "prev_excerpt_loader", "📖 前章尾段衔接", 20, 410, None, "grp_assets"),
            _mk_node("n_rag", "rag_retriever", "🔍 RAG 知识库检索", 340, 40, None, "grp_assets"),
            _mk_node("n_foreshadow", "foreshadow_loader", "🪝 伏笔未收线索", 340, 250, None, "grp_assets"),
            _mk_node("n_forbidden", "forbidden_lock", "🚫 禁用词与称谓锁", 340, 460, None, "grp_assets"),
            _mk_node("n_combine", "context_combiner", "🔀 全资产合流总束", 1070, 340),
            _mk_node("n_draft", "draft_writer", "✍️ 3.8 Flash 起草", 1410, 160),
            _mk_node("n_audit", "script_audit", "🧪 脚本去AI初检", 1750, 160),
            _mk_node("n_review", "deai_reviewer", "🛡️ 4 Hydrogen 去AI审校", 2090, 160),
            _mk_node("n_hook", "ending_hook_rewriter", "✂️ 章末断章钩子精修", 2430, 160),
            _mk_node("n_gate", "human_gate", "✋ 人工审核放行卡点", 2770, 160, {"gate_mode": "always"}),
            _mk_node("n_save", "save_chapter", "💾 定稿落盘", 3110, 160),
            _mk_node("n_archive", "memory_archive", "📜 正史与Handoff归档", 3440, 160),
        ],
        "edges": [
            _mk_edge("f1", "n_book", "chapter_num", "n_outline", "chapter_num", "#38bdf8"),
            _mk_edge("f2", "n_book", "chapter_num", "n_pregate", "chapter_num", "#38bdf8"),
            _mk_edge("f3", "n_outline", "outline", "n_pregate", "outline", "#f59e0b"),
            _mk_edge("f4", "n_book", "chapter_num", "n_memory", "chapter_num", "#38bdf8"),
            _mk_edge("f5", "n_outline", "outline", "n_memory", "outline", "#f59e0b"),
            _mk_edge("f6", "n_book", "chapter_num", "n_chars", "chapter_num", "#38bdf8"),
            _mk_edge("f7", "n_book", "chapter_num", "n_prev", "chapter_num", "#38bdf8"),
            _mk_edge("f8", "n_book", "chapter_num", "n_rag", "chapter_num", "#38bdf8"),
            _mk_edge("f9", "n_outline", "outline", "n_rag", "outline", "#f59e0b"),
            _mk_edge("f10", "n_book", "chapter_num", "n_foreshadow", "chapter_num", "#38bdf8"),
            _mk_edge("f11", "n_memory", "context_bundle", "n_combine", "ctx_1", "#2dd4bf"),
            _mk_edge("f12", "n_chars", "context_bundle", "n_combine", "ctx_2", "#2dd4bf"),
            _mk_edge("f13", "n_prev", "context_bundle", "n_combine", "ctx_3", "#2dd4bf"),
            _mk_edge("f14", "n_rag", "context_bundle", "n_combine", "ctx_4", "#2dd4bf"),
            _mk_edge("f15", "n_foreshadow", "context_bundle", "n_combine", "ctx_5", "#2dd4bf"),
            _mk_edge("f16", "n_forbidden", "context_bundle", "n_combine", "ctx_6", "#2dd4bf"),
            _mk_edge("f17", "n_book", "chapter_num", "n_draft", "chapter_num", "#38bdf8"),
            _mk_edge("f18", "n_pregate", "outline", "n_draft", "outline", "#f59e0b"),
            # 注意这里演示多线直连同一个 context_bundle 自动合并：合流束 + 临时便签
            _mk_edge("f19", "n_combine", "context_bundle", "n_draft", "context_bundle", "#2dd4bf"),
            _mk_edge("f20", "n_note", "context_bundle", "n_draft", "context_bundle", "#2dd4bf"),
            _mk_edge("f21", "n_style", "style_config", "n_draft", "style_config", "#ec4899"),
            _mk_edge("f22", "n_draft", "draft_text", "n_audit", "text_in", "#a855f7"),
            _mk_edge("f23", "n_book", "chapter_num", "n_audit", "chapter_num", "#38bdf8"),
            _mk_edge("f24", "n_audit", "text_out", "n_review", "draft_text", "#a855f7"),
            _mk_edge("f25", "n_audit", "checklist", "n_review", "checklist", "#94a3b8"),
            _mk_edge("f26", "n_pregate", "outline", "n_review", "outline", "#f59e0b"),
            _mk_edge("f27", "n_combine", "context_bundle", "n_review", "context_bundle", "#2dd4bf"),
            _mk_edge("f28", "n_style", "style_config", "n_review", "style_config", "#ec4899"),
            _mk_edge("f29", "n_review", "polished_text", "n_hook", "text_in", "#a855f7"),
            _mk_edge("f30", "n_pregate", "outline", "n_hook", "outline", "#f59e0b"),
            _mk_edge("f31", "n_hook", "text_out", "n_gate", "text_in", "#a855f7"),
            _mk_edge("f32", "n_draft", "draft_text", "n_gate", "draft_text", "#a855f7"),
            _mk_edge("f33", "n_review", "checklist", "n_gate", "checklist", "#94a3b8"),
            _mk_edge("f34", "n_book", "chapter_num", "n_save", "chapter_num", "#38bdf8"),
            _mk_edge("f35", "n_gate", "approved_text", "n_save", "final_text", "#a855f7"),
            _mk_edge("f36", "n_draft", "draft_text", "n_save", "draft_text", "#a855f7"),
            _mk_edge("f37", "n_review", "checklist", "n_save", "checklist", "#94a3b8"),
            _mk_edge("f38", "n_book", "chapter_num", "n_archive", "chapter_num", "#38bdf8"),
            _mk_edge("f39", "n_save", "final_text", "n_archive", "final_text", "#a855f7"),
        ],
    }

    # 3. 双分支 A-B 对比优选链
    ab_compare = {
        "id": "ab_compare",
        "name": "🔀 双温度 / 双分支 A-B 对比优选链",
        "description": "同一份细纲并发生成稳健版(A)与张力版(B)两份初稿，通过 A/B 节点红绿对比人工择优后再去AI审校落盘",
        "builtin": True,
        "nodes": [
            {
                "id": "grp_ab",
                "type": "groupNode",
                "position": {"x": 670, "y": 40},
                "style": {"width": "380px", "height": "600px"},
                "data": {"nodeType": "group", "label": "A/B 并发双分支试验组", "color": "#8b5cf6"},
            },
            _mk_node("n_book", "chapter_input", "📘 章节选号", 40, 140),
            _mk_node("n_style", "style_prompt", "🎨 文风指令", 40, 380),
            _mk_node("n_outline", "outline_loader", "📑 细纲加载", 340, 100),
            _mk_node("n_memory", "memory_assembler", "🧠 记忆上下文", 340, 320),
            _mk_node("n_draft_a", "draft_writer", "✍️ 分支 A · 稳健节奏 (T=0.65)", 30, 50, {"temperature": 0.65}, "grp_ab"),
            _mk_node("n_draft_b", "draft_writer", "✍️ 分支 B · 强张力狂想 (T=0.92)", 30, 330, {"temperature": 0.92}, "grp_ab"),
            _mk_node("n_ab", "ab_selector", "🔀 A/B 对比人工择优", 1120, 210),
            _mk_node("n_review", "deai_reviewer", "🛡️ 4 Hydrogen 去AI审校", 1480, 210),
            _mk_node("n_save", "save_chapter", "💾 定稿保存", 1840, 210),
            _mk_node("n_archive", "memory_archive", "📜 记忆归档", 2170, 210),
        ],
        "edges": [
            _mk_edge("ab1", "n_book", "chapter_num", "n_outline", "chapter_num", "#38bdf8"),
            _mk_edge("ab2", "n_book", "chapter_num", "n_memory", "chapter_num", "#38bdf8"),
            _mk_edge("ab3", "n_outline", "outline", "n_memory", "outline", "#f59e0b"),
            _mk_edge("ab4", "n_book", "chapter_num", "n_draft_a", "chapter_num", "#38bdf8"),
            _mk_edge("ab5", "n_outline", "outline", "n_draft_a", "outline", "#f59e0b"),
            _mk_edge("ab6", "n_memory", "context_bundle", "n_draft_a", "context_bundle", "#2dd4bf"),
            _mk_edge("ab7", "n_style", "style_config", "n_draft_a", "style_config", "#ec4899"),
            _mk_edge("ab8", "n_book", "chapter_num", "n_draft_b", "chapter_num", "#38bdf8"),
            _mk_edge("ab9", "n_outline", "outline", "n_draft_b", "outline", "#f59e0b"),
            _mk_edge("ab10", "n_memory", "context_bundle", "n_draft_b", "context_bundle", "#2dd4bf"),
            _mk_edge("ab11", "n_style", "style_config", "n_draft_b", "style_config", "#ec4899"),
            _mk_edge("ab12", "n_draft_a", "draft_text", "n_ab", "branch_a", "#a855f7"),
            _mk_edge("ab13", "n_draft_b", "draft_text", "n_ab", "branch_b", "#a855f7"),
            _mk_edge("ab14", "n_ab", "selected_text", "n_review", "draft_text", "#a855f7"),
            _mk_edge("ab15", "n_outline", "outline", "n_review", "outline", "#f59e0b"),
            _mk_edge("ab16", "n_memory", "context_bundle", "n_review", "context_bundle", "#2dd4bf"),
            _mk_edge("ab16b", "n_style", "style_config", "n_review", "style_config", "#ec4899"),
            _mk_edge("ab17", "n_book", "chapter_num", "n_save", "chapter_num", "#38bdf8"),
            _mk_edge("ab18", "n_review", "polished_text", "n_save", "final_text", "#a855f7"),
            _mk_edge("ab19", "n_ab", "selected_text", "n_save", "draft_text", "#a855f7"),
            _mk_edge("ab20", "n_review", "checklist", "n_save", "checklist", "#94a3b8"),
            _mk_edge("ab21", "n_book", "chapter_num", "n_archive", "chapter_num", "#38bdf8"),
            _mk_edge("ab22", "n_save", "final_text", "n_archive", "final_text", "#a855f7"),
        ],
    }

    # 4. 极速试写初稿链
    draft_trial = {
        "id": "draft_trial",
        "name": "⚡ 极速试写初稿链（不落盘、不污染长期记忆）",
        "description": "细纲 + 记忆 + 前章尾段 -> 3.8 Flash 起草 -> 脚本体检预览，安全试读黄金开篇",
        "builtin": True,
        "nodes": [
            _mk_node("n_book", "chapter_input", "📘 章节选号", 60, 140),
            _mk_node("n_style", "style_prompt", "🎨 文风设置", 60, 370),
            _mk_node("n_outline", "outline_loader", "📑 细纲加载", 380, 90),
            _mk_node("n_memory", "memory_assembler", "🧠 记忆上下文", 380, 290),
            _mk_node("n_prev", "prev_excerpt_loader", "📖 前章尾段", 380, 500),
            _mk_node("n_draft", "draft_writer", "✍️ 3.8 Flash 试写起草", 740, 180),
            _mk_node("n_audit", "script_audit", "🧪 脚本去AI快检", 1100, 180),
        ],
        "edges": [
            _mk_edge("t1", "n_book", "chapter_num", "n_outline", "chapter_num", "#38bdf8"),
            _mk_edge("t2", "n_book", "chapter_num", "n_memory", "chapter_num", "#38bdf8"),
            _mk_edge("t3", "n_outline", "outline", "n_memory", "outline", "#f59e0b"),
            _mk_edge("t3b", "n_book", "chapter_num", "n_prev", "chapter_num", "#38bdf8"),
            _mk_edge("t4", "n_book", "chapter_num", "n_draft", "chapter_num", "#38bdf8"),
            _mk_edge("t5", "n_outline", "outline", "n_draft", "outline", "#f59e0b"),
            _mk_edge("t6", "n_memory", "context_bundle", "n_draft", "context_bundle", "#2dd4bf"),
            _mk_edge("t6b", "n_prev", "context_bundle", "n_draft", "context_bundle", "#2dd4bf"),
            _mk_edge("t7", "n_style", "style_config", "n_draft", "style_config", "#ec4899"),
            _mk_edge("t8", "n_draft", "draft_text", "n_audit", "text_in", "#a855f7"),
            _mk_edge("t9", "n_book", "chapter_num", "n_audit", "chapter_num", "#38bdf8"),
        ],
    }

    # 5. 三阶深修 + 人工放行卡点链
    deep_3stage_gate = {
        "id": "deep_3stage_gate",
        "name": "🛡️ 三阶深修 + 人工放行卡点链（黄金章专用）",
        "description": "3.8 Flash 起草 -> 4 Hydrogen 强力去AI -> 二次钩子/台词精修 -> 人工过目放行后才写入正史与长期记忆",
        "builtin": True,
        "nodes": [
            _mk_node("n_book", "chapter_input", "📘 章节选号", 40, 140),
            _mk_node("n_style", "style_prompt", "🎨 文风设置", 40, 370),
            _mk_node("n_outline", "outline_loader", "📑 细纲加载", 340, 100),
            _mk_node("n_memory", "memory_assembler", "🧠 记忆上下文", 340, 320),
            _mk_node("n_draft", "draft_writer", "✍️ 3.8 Flash 起草", 690, 170),
            _mk_node("n_review", "deai_reviewer", "🛡️ 4 Hydrogen 强力去AI审校", 1040, 170),
            _mk_node("n_rewrite", "custom_rewrite", "✨ 二阶爽点与断章钩子精修", 1400, 170),
            _mk_node("n_gate", "human_gate", "✋ 人工审核放行卡点", 1760, 170, {"gate_mode": "always"}),
            _mk_node("n_save", "save_chapter", "💾 定稿落盘", 2100, 170),
            _mk_node("n_archive", "memory_archive", "📜 记忆归档", 2420, 170),
        ],
        "edges": [
            _mk_edge("d1", "n_book", "chapter_num", "n_outline", "chapter_num", "#38bdf8"),
            _mk_edge("d2", "n_book", "chapter_num", "n_memory", "chapter_num", "#38bdf8"),
            _mk_edge("d3", "n_outline", "outline", "n_memory", "outline", "#f59e0b"),
            _mk_edge("d4", "n_book", "chapter_num", "n_draft", "chapter_num", "#38bdf8"),
            _mk_edge("d5", "n_outline", "outline", "n_draft", "outline", "#f59e0b"),
            _mk_edge("d6", "n_memory", "context_bundle", "n_draft", "context_bundle", "#2dd4bf"),
            _mk_edge("d7", "n_style", "style_config", "n_draft", "style_config", "#ec4899"),
            _mk_edge("d8", "n_draft", "draft_text", "n_review", "draft_text", "#a855f7"),
            _mk_edge("d9", "n_outline", "outline", "n_review", "outline", "#f59e0b"),
            _mk_edge("d10", "n_memory", "context_bundle", "n_review", "context_bundle", "#2dd4bf"),
            _mk_edge("d10b", "n_style", "style_config", "n_review", "style_config", "#ec4899"),
            _mk_edge("d11", "n_review", "polished_text", "n_rewrite", "text_in", "#a855f7"),
            _mk_edge("d11b", "n_outline", "outline", "n_rewrite", "outline", "#f59e0b"),
            _mk_edge("d12", "n_memory", "context_bundle", "n_rewrite", "context_bundle", "#2dd4bf"),
            _mk_edge("d12b", "n_style", "style_config", "n_rewrite", "style_config", "#ec4899"),
            _mk_edge("d13", "n_rewrite", "text_out", "n_gate", "text_in", "#a855f7"),
            _mk_edge("d14", "n_draft", "draft_text", "n_gate", "draft_text", "#a855f7"),
            _mk_edge("d15", "n_review", "checklist", "n_gate", "checklist", "#94a3b8"),
            _mk_edge("d15b", "n_rewrite", "checklist", "n_gate", "checklist", "#94a3b8"),
            _mk_edge("d16", "n_book", "chapter_num", "n_save", "chapter_num", "#38bdf8"),
            _mk_edge("d17", "n_gate", "approved_text", "n_save", "final_text", "#a855f7"),
            _mk_edge("d18", "n_draft", "draft_text", "n_save", "draft_text", "#a855f7"),
            _mk_edge("d19", "n_review", "checklist", "n_save", "checklist", "#94a3b8"),
            _mk_edge("d19b", "n_rewrite", "checklist", "n_save", "checklist", "#94a3b8"),
            _mk_edge("d20", "n_book", "chapter_num", "n_archive", "chapter_num", "#38bdf8"),
            _mk_edge("d21", "n_save", "final_text", "n_archive", "final_text", "#a855f7"),
        ],
    }

    # 6. 从零开荒全链路模板（立意 -> 架构 -> 200章目录 -> 10章细纲审核 -> 第1章写审试写）
    book_genesis_pipeline = {
        "id": "book_genesis_pipeline",
        "name": "🧭 从零开荒全链路模板（立意 ➔ 架构 ➔ 目录 ➔ 细纲 ➔ 写审）",
        "description": "从一句话脑洞自动生成雪花架构与200章全书目录，推送到10章滚动细纲人工审核，随后无缝衔接起草与去AI审校落盘",
        "builtin": True,
        "nodes": [
            _mk_node("n_idea", "idea_seed", "💡 立意与200章参数", 40, 140),
            _mk_node("n_arch", "arch_generator", "🏛️ 雪花架构生成器", 380, 80),
            _mk_node("n_dir", "directory_generator", "🗺️ 200章全书目录", 720, 80),
            _mk_node("n_bot", "batch_outline_gate", "📑 10章细纲生成与审核", 1070, 80),
            _mk_node("n_memory", "memory_assembler", "🧠 记忆上下文", 1070, 340),
            _mk_node("n_draft", "draft_writer", "✍️ 章节起草引擎", 1430, 180),
            _mk_node("n_audit", "script_audit", "🧪 脚本去AI质检", 1770, 180),
            _mk_node("n_review", "deai_reviewer", "🛡️ 去AI味审校", 2110, 180),
            _mk_node("n_save", "save_chapter", "💾 定稿落盘", 2450, 180),
            _mk_node("n_archive", "memory_archive", "📜 记忆归档", 2780, 180),
        ],
        "edges": [
            _mk_edge("g1", "n_idea", "book_brief", "n_arch", "book_brief", "#60a5fa"),
            _mk_edge("g2", "n_idea", "book_brief", "n_dir", "book_brief", "#60a5fa"),
            _mk_edge("g3", "n_arch", "arch_text", "n_dir", "arch_text", "#f59e0b"),
            _mk_edge("g4", "n_dir", "chapter_num", "n_bot", "chapter_num", "#38bdf8"),
            _mk_edge("g5", "n_dir", "directory_text", "n_bot", "directory_text", "#f59e0b"),
            _mk_edge("g6", "n_dir", "chapter_num", "n_memory", "chapter_num", "#38bdf8"),
            _mk_edge("g7", "n_bot", "outline", "n_memory", "outline", "#f59e0b"),
            _mk_edge("g8", "n_dir", "chapter_num", "n_draft", "chapter_num", "#38bdf8"),
            _mk_edge("g9", "n_bot", "outline", "n_draft", "outline", "#f59e0b"),
            _mk_edge("g10", "n_memory", "context_bundle", "n_draft", "context_bundle", "#2dd4bf"),
            _mk_edge("g11", "n_draft", "draft_text", "n_audit", "text_in", "#a855f7"),
            _mk_edge("g12", "n_dir", "chapter_num", "n_audit", "chapter_num", "#38bdf8"),
            _mk_edge("g13", "n_audit", "text_out", "n_review", "draft_text", "#a855f7"),
            _mk_edge("g14", "n_audit", "checklist", "n_review", "checklist", "#94a3b8"),
            _mk_edge("g15", "n_bot", "outline", "n_review", "outline", "#f59e0b"),
            _mk_edge("g16", "n_memory", "context_bundle", "n_review", "context_bundle", "#2dd4bf"),
            _mk_edge("g17", "n_dir", "chapter_num", "n_save", "chapter_num", "#38bdf8"),
            _mk_edge("g18", "n_review", "polished_text", "n_save", "final_text", "#a855f7"),
            _mk_edge("g19", "n_draft", "draft_text", "n_save", "draft_text", "#a855f7"),
            _mk_edge("g20", "n_review", "checklist", "n_save", "checklist", "#94a3b8"),
            _mk_edge("g21", "n_dir", "chapter_num", "n_archive", "chapter_num", "#38bdf8"),
            _mk_edge("g22", "n_save", "final_text", "n_archive", "final_text", "#a855f7"),
        ],
    }

    return [standard_zh, full_transparent_pro, book_genesis_pipeline, ab_compare, draft_trial, deep_3stage_gate]


# ── 用户工作流读写持久化 ───────────────────────────────────────────────────────

def load_workflow_store() -> Dict[str, Any]:
    data = {"default_workflow_id": "standard_zh", "workflows": []}
    if os.path.exists(WORKFLOW_STORE_FILE):
        try:
            with open(WORKFLOW_STORE_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data["default_workflow_id"] = loaded.get("default_workflow_id", "standard_zh")
                    data["workflows"] = loaded.get("workflows", []) or []
        except Exception as e:
            logger.warning(f"读取 workflow_store.json 失败: {e}")
    return data


def save_workflow_store(store: Dict[str, Any]):
    with open(WORKFLOW_STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def list_all_workflows() -> Dict[str, Any]:
    store = load_workflow_store()
    builtins = get_builtin_workflows()
    customs = store.get("workflows", [])
    return {
        "default_workflow_id": store.get("default_workflow_id", "standard_zh"),
        "builtins": builtins,
        "customs": customs,
    }


def save_custom_workflow(wf: Dict[str, Any]) -> Dict[str, Any]:
    store = load_workflow_store()
    wf_id = (wf.get("id") or "").strip()
    if not wf_id or any(b["id"] == wf_id for b in get_builtin_workflows()):
        wf_id = f"custom_{str(uuid4())[:8]}"
    record = {
        "id": wf_id,
        "name": wf.get("name") or f"自定义工作流 ({wf_id})",
        "description": wf.get("description") or "",
        "builtin": False,
        "nodes": wf.get("nodes", []),
        "edges": wf.get("edges", []),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    customs = [w for w in store.get("workflows", []) if w.get("id") != wf_id]
    customs.insert(0, record)
    store["workflows"] = customs
    save_workflow_store(store)
    return record


def delete_custom_workflow(wf_id: str) -> bool:
    store = load_workflow_store()
    before = len(store.get("workflows", []))
    store["workflows"] = [w for w in store.get("workflows", []) if w.get("id") != wf_id]
    if store.get("default_workflow_id") == wf_id:
        store["default_workflow_id"] = "standard_zh"
    save_workflow_store(store)
    return len(store["workflows"]) < before


def set_default_workflow(wf_id: str):
    store = load_workflow_store()
    store["default_workflow_id"] = wf_id
    save_workflow_store(store)


# ── DAG 拓扑解析与资产合并辅助 ──────────────────────────────────────────────────

def _topological_sort(nodes: List[dict], edges: List[dict]) -> Tuple[List[str], Dict[str, List[dict]]]:
    active_nodes = [n for n in nodes if n.get("type") != "groupNode" and n.get("data", {}).get("nodeType") != "group"]
    node_ids = {n["id"] for n in active_nodes}
    in_degree = {nid: 0 for nid in node_ids}
    adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
    incoming: Dict[str, List[dict]] = {nid: [] for nid in node_ids}

    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src in node_ids and tgt in node_ids and src != tgt:
            adj[src].append(tgt)
            incoming[tgt].append(edge)
            in_degree[tgt] += 1

    pos_map = {n["id"]: (n.get("position", {}).get("x", 0), n.get("position", {}).get("y", 0)) for n in active_nodes}
    queue = sorted([nid for nid, deg in in_degree.items() if deg == 0], key=lambda k: pos_map.get(k, (0, 0)))
    order: List[str] = []

    while queue:
        curr = queue.pop(0)
        order.append(curr)
        for nxt in adj[curr]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)
                queue.sort(key=lambda k: pos_map.get(k, (0, 0)))

    if len(order) != len(node_ids):
        raise ValueError("工作流存在闭环连线（Cycle），请检查并断开循环连接后再运行。")
    return order, incoming


def _get_downstream_set(start_id: str, edges: List[dict]) -> set:
    downstream = {start_id}
    changed = True
    while changed:
        changed = False
        for e in edges:
            if e.get("source") in downstream and e.get("target") not in downstream:
                downstream.add(e["target"])
                changed = True
    return downstream


def _merge_memory_bundles(existing: Any, incoming_val: Any) -> Dict[str, Any]:
    """合并多路连入同一个 MEMORY 端口的资产束（避免后者覆盖前者）。"""
    def _as_dict(v: Any) -> Dict[str, Any]:
        if isinstance(v, dict):
            return dict(v)
        if isinstance(v, str) and v.strip():
            return {"text": v.strip()}
        return {}

    a = _as_dict(existing)
    b = _as_dict(incoming_val)
    texts = [t for t in [a.get("text", "").strip(), b.get("text", "").strip()] if t]
    merged: Dict[str, Any] = {
        "text": "\n\n".join(texts),
        "inject_summary": a.get("inject_summary", b.get("inject_summary", True)),
        "inject_char_state": a.get("inject_char_state", b.get("inject_char_state", True)),
        "inject_world_building": a.get("inject_world_building", b.get("inject_world_building", True)),
        "inject_canon": a.get("inject_canon", b.get("inject_canon", True)),
        "inject_handoff": a.get("inject_handoff", b.get("inject_handoff", True)),
    }
    canon_parts = [c for c in [a.get("canon_txt", ""), b.get("canon_txt", "")] if c]
    if canon_parts:
        merged["canon_txt"] = "\n".join(canon_parts)
    for k in ("extra_guidance",):
        vals = [v for v in [a.get(k, ""), b.get(k, "")] if v]
        if vals:
            merged[k] = "\n\n".join(vals)
    return merged


def _extract_chapter_ctx(val: Any, fallback_ch: int, fallback_words: int) -> Tuple[int, int]:
    if isinstance(val, dict):
        return int(val.get("chapter_num") or fallback_ch), int(val.get("word_number") or fallback_words)
    if isinstance(val, (int, float)) and val > 0:
        return int(val), fallback_words
    return fallback_ch, fallback_words


# ── DAG 实时执行核心入口 ───────────────────────────────────────────────────────

def execute_workflow_dag(
    web_app: Any,
    graph: Dict[str, Any],
    filepath: str,
    chapter_num: int,
    llm_config_name: str = "",
    emb_config_name: str = "",
    word_number: int = 2500,
    run_id: str = "",
    start_from_node_id: str = "",
    initial_cache: Optional[Dict[str, Dict[str, Any]]] = None,
    is_batch_mode: bool = False,
    batch_gate_policy: str = "manual",
    progress=None,
) -> str:
    run_id = run_id or str(uuid4())[:12]
    session = WorkflowRunSession(run_id, int(chapter_num))
    _register_session(session)

    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    cache_in = initial_cache or {}

    def emit(event_name: str, payload: dict, val: float = 0.0, log_msg: str = ""):
        body = {"workflow_event": event_name, "run_id": run_id, **payload}
        if progress:
            progress(val, desc=log_msg, content=json.dumps(body, ensure_ascii=False))

    try:
        order, incoming_edges = _topological_sort(nodes, edges)
    except Exception as e:
        emit("run_error", {"error": str(e)}, 0.0, f"❌ 拓扑检查失败: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    node_map = {n["id"]: n for n in nodes}
    total_steps = max(1, len(order))
    recompute_set = _get_downstream_set(start_from_node_id, edges) if start_from_node_id else set(order)

    emit(
        "run_started",
        {"chapter_num": chapter_num, "order": order, "recompute": list(recompute_set)},
        0.02,
        f"🚀 启动工作流 (Run={run_id}) · 第 {chapter_num} 章 · 共 {total_steps} 个节点",
    )

    node_outputs: Dict[str, Dict[str, Any]] = {}
    all_configs = web_app.config.get("llm_configs", {}) if hasattr(web_app, "config") else {}
    emb_configs = web_app.config.get("embedding_configs", {}) if hasattr(web_app, "config") else {}
    default_llm = llm_config_name or web_app.config.get("choose_configs", {}).get("chapter_llm") or next(iter(all_configs.keys()), "")
    default_emb = emb_config_name or next(iter(emb_configs.keys()), "")

    def resolve_llm(preferred_name: str = "") -> Tuple[str, dict]:
        name = preferred_name if (preferred_name and preferred_name in all_configs) else default_llm
        conf = all_configs.get(name, {})
        return name, conf

    def gather_inputs(nid: str) -> Dict[str, Any]:
        resolved: Dict[str, Any] = {}
        for edge in incoming_edges.get(nid, []):
            src_id = edge.get("source")
            src_handle = edge.get("sourceHandle") or "output"
            tgt_handle = edge.get("targetHandle") or "input"
            src_out = node_outputs.get(src_id, {})
            if src_handle in src_out:
                val = src_out[src_handle]
            elif src_out:
                val = next(iter(src_out.values()))
            else:
                continue

            # 多线汇聚支持：MEMORY & CHECKLIST 自动合并，不互相覆盖
            if tgt_handle in resolved:
                if tgt_handle == "context_bundle" or tgt_handle.startswith("ctx_"):
                    resolved[tgt_handle] = _merge_memory_bundles(resolved[tgt_handle], val)
                elif tgt_handle == "checklist" or tgt_handle.startswith("checklist"):
                    parts = [str(resolved[tgt_handle]).strip(), str(val).strip()]
                    resolved[tgt_handle] = "\n\n".join(p for p in parts if p)
                else:
                    resolved[tgt_handle] = val
            else:
                resolved[tgt_handle] = val
        return resolved

    try:
        for idx, nid in enumerate(order):
            if session.cancelled or (progress and getattr(progress, "cancelled", False)):
                emit("run_cancelled", {"node_id": nid}, idx / total_steps, "🛑 工作流已取消")
                return json.dumps({"success": False, "cancelled": True, "outputs": node_outputs}, ensure_ascii=False)

            node = node_map[nid]
            data = node.get("data", {})
            ntype = data.get("nodeType", "")
            label = data.get("label", ntype)
            params = data.get("params", {}) or {}
            bypass = bool(data.get("bypass", False))
            base_val = idx / total_steps

            # 1) 局部重跑命中上游缓存
            if start_from_node_id and nid not in recompute_set and nid in cache_in:
                node_outputs[nid] = dict(cache_in[nid])
                emit(
                    "node_status",
                    {
                        "node_id": nid,
                        "status": "cached",
                        "elapsed_ms": 0,
                        "message": "复用上次运行缓存",
                        "outputs": node_outputs[nid],
                    },
                    (idx + 1) / total_steps,
                    f"♻️ [{label}] 命中缓存，跳过重跑",
                )
                continue

            inputs = gather_inputs(nid)

            # 2) Bypass 旁路透传
            if bypass:
                passthrough: Dict[str, Any] = {}
                primary_in = (
                    inputs.get("draft_text")
                    or inputs.get("text_in")
                    or inputs.get("final_text")
                    or inputs.get("branch_a")
                    or inputs.get("outline")
                    or inputs.get("context_bundle")
                    or inputs.get("chapter_num")
                    or ""
                )
                if ntype == "deai_reviewer":
                    passthrough = {"polished_text": primary_in, "checklist": ""}
                elif ntype in ("custom_rewrite", "ending_hook_rewriter", "diff_preview"):
                    passthrough = {"text_out": primary_in, "checklist": inputs.get("checklist", "")}
                elif ntype == "script_audit":
                    passthrough = {"text_out": primary_in, "checklist": ""}
                elif ntype == "pre_write_gate":
                    passthrough = {"outline": inputs.get("outline", ""), "checklist": ""}
                elif ntype == "human_gate":
                    passthrough = {"approved_text": primary_in}
                elif ntype == "ab_selector":
                    passthrough = {"selected_text": inputs.get("branch_a") or inputs.get("branch_b") or "", "selected_checklist": ""}
                elif ntype == "save_chapter":
                    passthrough = {"final_text": primary_in}
                elif ntype in ("character_profile", "prev_excerpt_loader", "rag_retriever", "foreshadow_loader", "forbidden_lock", "note_primitive", "memory_assembler", "context_combiner"):
                    passthrough = {"context_bundle": {"text": ""}}
                else:
                    passthrough = {"output": primary_in}
                node_outputs[nid] = passthrough
                emit(
                    "node_status",
                    {"node_id": nid, "status": "bypassed", "elapsed_ms": 0, "message": "已旁路跳过", "outputs": passthrough},
                    (idx + 1) / total_steps,
                    f"⏭️ [{label}] Bypass 跳过",
                )
                continue

            t0 = time.time()
            emit(
                "node_status",
                {"node_id": nid, "status": "running", "progress": 10, "message": "正在执行..."},
                base_val,
                f"⚡ 开始执行 [{label}]...",
            )

            out: Dict[str, Any] = {}
            ch, ctx_words = _extract_chapter_ctx(
                inputs.get("chapter_num"),
                int(params.get("chapter_num") or chapter_num),
                int(word_number or 2500),
            )

            # ── 各节点真实逻辑执行 ──────────────────────────────────────────────
            if ntype == "idea_seed":
                pcfg = web_app.load_project_config(filepath) if hasattr(web_app, "load_project_config") else {}
                topic_val = (params.get("topic") or pcfg.get("topic") or "").strip()
                genre_val = (params.get("genre") or pcfg.get("genre") or "都市").strip()
                n_ch = int(params.get("num_chapters") or pcfg.get("num_chapters") or 200)
                w_num = int(params.get("word_number") or pcfg.get("word_number") or word_number or 2500)
                guidance_val = (params.get("user_guidance") or pcfg.get("user_guidance") or "").strip()
                start_ch = int(chapter_num or 1)
                out = {
                    "book_brief": {
                        "topic": topic_val,
                        "genre": genre_val,
                        "num_chapters": n_ch,
                        "word_number": w_num,
                        "user_guidance": guidance_val,
                    },
                    "chapter_num": {"chapter_num": start_ch, "word_number": w_num},
                }

            elif ntype == "arch_generator":
                brief = inputs.get("book_brief") or {}
                mcfg = inputs.get("model_config") or {}
                arch_file = os.path.join(filepath, "Novel_architecture.txt")
                force_regen = bool(params.get("force_regen", False))
                arch_txt = read_file(arch_file).strip() if os.path.exists(arch_file) else ""

                if not arch_txt or force_regen:
                    arch_llm, _ = resolve_llm(mcfg.get("llm_config_name") or params.get("llm_config_name", ""))
                    if not brief.get("topic"):
                        raise ValueError("雪花架构生成器需要「立意/脑洞」输入，请在起点节点或项目参数中填写 topic。")
                    def _arch_gen_prog(v=None, desc="", total=None, content=""):
                        emit("node_status", {"node_id": nid, "status": "running", "progress": min(95, int((v or 0.3) * 100)), "message": desc or "推演雪花架构..."}, base_val)
                    web_app.generate_architecture(
                        llm_config_name=arch_llm,
                        topic=brief.get("topic", ""),
                        genre=brief.get("genre", "都市"),
                        num_chapters=int(brief.get("num_chapters", 200)),
                        word_number=int(brief.get("word_number", 2500)),
                        filepath=filepath,
                        user_guidance=brief.get("user_guidance", ""),
                        progress=_arch_gen_prog,
                    )
                    arch_txt = read_file(arch_file).strip() if os.path.exists(arch_file) else ""
                out = {"arch_text": arch_txt}

            elif ntype == "directory_generator":
                brief = inputs.get("book_brief") or {}
                mcfg = inputs.get("model_config") or {}
                bp_file = os.path.join(filepath, "Novel_directory.txt")
                force_regen = bool(params.get("force_regen", False))
                bp_txt = read_file(bp_file).strip() if os.path.exists(bp_file) else ""
                n_ch = int(brief.get("num_chapters") or 200)
                w_num = int(brief.get("word_number") or word_number or 2500)

                if not bp_txt or force_regen:
                    bp_llm, _ = resolve_llm(mcfg.get("llm_config_name") or params.get("llm_config_name", ""))
                    def _bp_prog(v=None, desc="", total=None, content=""):
                        emit("node_status", {"node_id": nid, "status": "running", "progress": min(95, int((v or 0.3) * 100)), "message": desc or "规划全书目录..."}, base_val)
                    web_app.generate_blueprint(
                        llm_config_name=bp_llm,
                        filepath=filepath,
                        num_chapters=n_ch,
                        user_guidance=brief.get("user_guidance", ""),
                        progress=_bp_prog,
                    )
                    bp_txt = read_file(bp_file).strip() if os.path.exists(bp_file) else ""
                start_ch = int(chapter_num or params.get("start_chapter") or 1)
                out = {
                    "directory_text": bp_txt,
                    "chapter_num": {"chapter_num": start_ch, "word_number": w_num},
                }

            elif ntype == "batch_outline_gate":
                mcfg = inputs.get("model_config") or {}
                b_size = int(params.get("batch_size") or 10)
                b_start = max(1, int(chapter_num or params.get("batch_start") or 1))
                b_end = b_start + b_size - 1
                force_regen = bool(params.get("force_regen", False))

                ot_file = os.path.join(filepath, "Novel_detailed_outline.txt")
                ch_outline = ""
                if os.path.exists(ot_file) and not force_regen:
                    try:
                        from novel_generator.detailed_outline import get_chapter_outline
                        ch_outline = (get_chapter_outline(read_file(ot_file), ch) or "").strip()
                    except Exception:
                        ch_outline = ""

                if not ch_outline or force_regen:
                    ot_llm, _ = resolve_llm(mcfg.get("llm_config_name") or "")
                    def _ot_prog(v=None, desc="", total=None, content=""):
                        emit("node_status", {"node_id": nid, "status": "running", "progress": min(95, int((v or 0.3) * 100)), "message": desc or f"推演第 {b_start}-{b_end} 章细纲..."}, base_val)
                    res_ot = web_app.generate_detailed_outline(
                        llm_config_name=ot_llm,
                        filepath=filepath,
                        start_chapter=b_start,
                        end_chapter=b_end,
                        num_chapters=200,
                        user_guidance="",
                        outline_mode=params.get("outline_mode", "concise"),
                        progress=_ot_prog,
                    )
                    if res_ot and not str(res_ot).startswith("❌"):
                        existing_ot = read_file(ot_file) if os.path.exists(ot_file) else ""
                        merged_ot = (existing_ot.rstrip() + "\n\n" + str(res_ot).strip()) if existing_ot.strip() else str(res_ot).strip()
                        save_string_to_txt(merged_ot, ot_file)
                    if os.path.exists(ot_file):
                        from novel_generator.detailed_outline import get_chapter_outline
                        ch_outline = (get_chapter_outline(read_file(ot_file), ch) or "").strip()

                if bool(params.get("pause_for_review", True)) and not (is_batch_mode and batch_gate_policy == "auto_pass"):
                    session.reset_gate()
                    emit(
                        "gate_waiting",
                        {
                            "node_id": nid,
                            "node_type": "human_gate",
                            "title": f"{label} · 审核第 {ch} 章细纲",
                            "text_in": ch_outline,
                            "draft_text": "",
                            "checklist": f"本批已规划范围：第 {b_start}-{b_end} 章，请核对/微调当前第 {ch} 章细纲后放行开写。",
                        },
                        base_val,
                        f"✋ [{label}] 第 {ch} 章细纲已生成，等待您确认/编辑后放行起草...",
                    )
                    session.gate_event.wait(timeout=1800)
                    if session.cancelled or session.gate_decision.get("action") == "cancel":
                        emit("run_cancelled", {"node_id": nid}, base_val, "🛑 用户取消细纲放行")
                        return json.dumps({"success": False, "cancelled": True}, ensure_ascii=False)
                    if session.gate_decision.get("edited_text"):
                        ch_outline = session.gate_decision["edited_text"]

                out = {"outline": ch_outline}

            elif ntype == "chapter_input":
                ch = int(chapter_num or params.get("chapter_num") or 1)
                w_num = int(word_number or params.get("word_number") or 2500)
                if params.get("word_number") and int(params.get("word_number")) > 0 and word_number == 2500:
                    w_num = int(params["word_number"])
                out = {
                    "chapter_num": {"chapter_num": ch, "word_number": w_num},
                    "word_number": w_num,
                }

            elif ntype == "style_prompt":
                out = {
                    "style_config": {
                        "style_name": params.get("style_name", ""),
                        "narrative_style_name": params.get("narrative_style_name", ""),
                        "xp_type": params.get("xp_type", ""),
                        "user_guidance": params.get("user_guidance", ""),
                    }
                }

            elif ntype == "llm_config":
                lname, lconf = resolve_llm(params.get("llm_config_name", ""))
                out = {
                    "model_config": {
                        "llm_config_name": lname,
                        "temperature": float(params.get("temperature", lconf.get("temperature", 0.7))),
                    }
                }

            elif ntype == "outline_loader":
                override_ot = (params.get("override_outline") or "").strip()
                ch_outline = override_ot
                if not ch_outline:
                    ot_file = os.path.join(filepath, "Novel_detailed_outline.txt")
                    if os.path.exists(ot_file):
                        try:
                            from novel_generator.detailed_outline import get_chapter_outline
                            ch_outline = (get_chapter_outline(read_file(ot_file), ch) or "").strip()
                        except Exception:
                            ch_outline = ""
                if not ch_outline and params.get("auto_complete", True):
                    bp_file = os.path.join(filepath, "Novel_directory.txt")
                    if os.path.exists(bp_file):
                        try:
                            from novel_generator.blueprint import get_chapter_info_from_blueprint
                            bp_info = get_chapter_info_from_blueprint(read_file(bp_file), ch) or {}
                            ch_outline = bp_info.get("chapter_summary", "")
                        except Exception:
                            pass
                out = {"outline": ch_outline}

            elif ntype == "memory_assembler":
                from novel_generator.architecture import read_world_building, read_character_state
                inject_summary = bool(params.get("inject_summary", True))
                inject_char_state = bool(params.get("inject_char_state", True))
                inject_world = bool(params.get("inject_world_building", True))
                inject_canon = bool(params.get("inject_canon", True))
                inject_handoff = bool(params.get("inject_handoff", True))

                parts = []
                outline_str = inputs.get("outline", "")
                if outline_str:
                    parts.append(f"【本章细纲】\n{outline_str}")
                if inject_summary:
                    sf = os.path.join(filepath, "global_summary.txt")
                    if os.path.exists(sf):
                        summary_txt = read_file(sf).strip()
                        if summary_txt:
                            parts.append(f"【前文全局摘要】\n{summary_txt}")
                if inject_char_state:
                    cs_txt = (read_character_state(filepath) or "").strip()
                    if cs_txt:
                        parts.append(f"【角色状态表】\n{cs_txt}")
                if inject_world:
                    wb_txt = (read_world_building(filepath) or "").strip()
                    if wb_txt:
                        parts.append(f"【世界观设定】\n{wb_txt}")
                canon_txt = ""
                if inject_canon:
                    cf = os.path.join(filepath, "Novel_canon_history.txt")
                    if os.path.exists(cf):
                        canon_txt = read_file(cf).strip()
                        if canon_txt:
                            parts.append(f"【正史设定与事实约束】\n{canon_txt}")
                handoff_txt = ""
                if inject_handoff and ch > 1:
                    try:
                        from novel_generator.continuity import get_semantic_handoff
                        h = get_semantic_handoff(filepath, ch - 1)
                        if h:
                            handoff_txt = json.dumps(h.to_dict(), ensure_ascii=False, indent=2)
                            # 修复断层1：实打实注入 Handoff 给起草和去AI审校节点使用
                            parts.append(f"【上章因果交接契约 (Semantic Handoff)】\n{handoff_txt}")
                    except Exception:
                        pass

                bundle = "\n\n".join(parts)
                out = {
                    "context_bundle": {
                        "text": bundle,
                        "inject_summary": inject_summary,
                        "inject_char_state": inject_char_state,
                        "inject_world_building": inject_world,
                        "inject_canon": inject_canon,
                        "inject_handoff": inject_handoff,
                        "canon_txt": canon_txt,
                    }
                }

            elif ntype == "character_profile":
                from novel_generator.architecture import read_character_dynamics, read_core_seed
                max_c = int(params.get("max_chars") or 2500)
                dyn = (read_character_dynamics(filepath) or "").strip()
                seed = (read_core_seed(filepath) or "").strip()
                segs = []
                if dyn:
                    segs.append(f"【人物核心性格与关系档案】\n{dyn[:max_c]}")
                if seed:
                    segs.append(f"【故事核心种子】\n{seed[:800]}")
                txt = "\n\n".join(segs)
                out = {"context_bundle": {"text": txt, "extra_guidance": txt}}

            elif ntype == "prev_excerpt_loader":
                tail_chars = int(params.get("tail_chars") or 800)
                txt = ""
                if ch > 1:
                    prev_file = os.path.join(filepath, "chapters", f"chapter_{ch - 1}.txt")
                    if os.path.exists(prev_file):
                        prev_raw = read_file(prev_file).strip()
                        if prev_raw:
                            excerpt = prev_raw[-tail_chars:] if len(prev_raw) > tail_chars else prev_raw
                            txt = f"【第 {ch - 1} 章结尾衔接原文（紧贴最后一句续写）】\n...{excerpt}"
                out = {"context_bundle": {"text": txt, "extra_guidance": txt}}

            elif ntype == "rag_retriever":
                top_k = int(params.get("top_k") or 4)
                query = (params.get("query_override") or "").strip() or (inputs.get("outline") or "")[:240]
                txt = ""
                if query:
                    try:
                        from embedding_adapters import create_embedding_adapter
                        from novel_generator.vectorstore_utils import get_relevant_context_from_vector_store
                        emb_conf = emb_configs.get(default_emb, {})
                        if emb_conf.get("model_name") or emb_conf.get("base_url"):
                            emb_adapter = create_embedding_adapter(
                                emb_conf.get("interface_format", default_emb),
                                emb_conf.get("api_key", ""),
                                emb_conf.get("base_url", ""),
                                emb_conf.get("model_name", ""),
                            )
                            retrieved = get_relevant_context_from_vector_store(
                                embedding_adapter=emb_adapter,
                                query=query,
                                filepath=filepath,
                                k=top_k,
                            )
                            if retrieved and retrieved.strip():
                                txt = f"【本地知识库 RAG 检索参考】\n{retrieved.strip()}"
                    except Exception as _re:
                        logger.info(f"[WorkflowRAG] 知识库未启用或检索跳过: {_re}")
                out = {"context_bundle": {"text": txt, "extra_guidance": txt}}

            elif ntype == "foreshadow_loader":
                from novel_generator.improv import read_open_threads
                ot = (read_open_threads(filepath) or "").strip()
                extra_f = (params.get("extra_foreshadow") or "").strip()
                segs = []
                if ot:
                    segs.append(f"【全书未收伏笔线索池】\n{ot}")
                if extra_f:
                    segs.append(f"【本章重点埋设/回收伏笔】\n{extra_f}")
                txt = "\n\n".join(segs)
                out = {"context_bundle": {"text": txt, "extra_guidance": txt}}

            elif ntype == "forbidden_lock":
                fw = (params.get("forbidden_words") or "").strip()
                tl = (params.get("term_locks") or "").strip()
                segs = []
                if fw:
                    segs.append(f"【严禁出现以下 AI 套话与禁用词】\n{fw}")
                if tl:
                    segs.append(f"【称谓/专有名词死锁】\n{tl}")
                txt = "\n\n".join(segs)
                out = {"context_bundle": {"text": txt, "extra_guidance": txt}}

            elif ntype == "note_primitive":
                title_n = (params.get("note_title") or "参考便签").strip()
                content_n = (params.get("note_content") or "").strip()
                txt = f"【{title_n}】\n{content_n}" if content_n else ""
                out = {"context_bundle": {"text": txt, "extra_guidance": txt}}

            elif ntype == "context_combiner":
                combined: Dict[str, Any] = {}
                for slot in ("ctx_1", "ctx_2", "ctx_3", "ctx_4", "ctx_5", "ctx_6"):
                    if slot in inputs:
                        combined = _merge_memory_bundles(combined, inputs[slot]) if combined else _merge_memory_bundles({}, inputs[slot])
                out = {"context_bundle": combined}

            elif ntype == "pre_write_gate":
                outline_in = inputs.get("outline") or ""
                mcfg = inputs.get("model_config") or {}
                gate_llm, _ = resolve_llm(mcfg.get("llm_config_name") or params.get("llm_config_name", ""))
                res = web_app.pre_write_gate_web(llm_config_name=gate_llm, filepath=filepath, chapter_num=ch)
                passed = bool(res.get("passed", True))
                warnings = (res.get("contradictions") or []) + (res.get("continuity_warnings") or [])
                report_str = f"写前门禁：{'✅ 通过' if passed else '⚠️ 检测到连续性冲突'}\n摘要：{res.get('summary', '')}"
                if warnings:
                    report_str += "\n冲突点：\n" + "\n".join(f"- {w}" for w in warnings)

                on_fail = params.get("on_fail", "append_hint")
                out_outline = outline_in
                if not passed and warnings and on_fail == "append_hint":
                    out_outline = f"{outline_in}\n\n【⚠️ 写前纠偏提醒（写作时必须规避）】\n" + "\n".join(f"- {w}" for w in warnings)
                elif not passed and on_fail == "pause":
                    session.reset_gate()
                    emit(
                        "gate_waiting",
                        {
                            "node_id": nid,
                            "node_type": "human_gate",
                            "title": f"{label} · 发现吃书/断层冲突",
                            "text_in": out_outline,
                            "draft_text": "",
                            "checklist": report_str,
                        },
                        base_val,
                        f"✋ [{label}] 发现设定冲突，已暂停等待人工确认",
                    )
                    session.gate_event.wait(timeout=1800)
                    if session.cancelled or session.gate_decision.get("action") == "cancel":
                        emit("run_cancelled", {"node_id": nid}, base_val, "🛑 用户在写前预检取消运行")
                        return json.dumps({"success": False, "cancelled": True}, ensure_ascii=False)
                    if session.gate_decision.get("edited_text"):
                        out_outline = session.gate_decision["edited_text"]

                out = {"outline": out_outline, "checklist": report_str, "passed": passed}

            elif ntype == "draft_writer":
                from novel_generator.chapter import generate_chapter_draft
                mcfg = inputs.get("model_config") or {}
                scfg = inputs.get("style_config") or {}
                mem_obj = inputs.get("context_bundle") or {}
                if isinstance(mem_obj, str):
                    mem_obj = {"text": mem_obj}

                llm_name, llm_conf = resolve_llm(mcfg.get("llm_config_name") or params.get("llm_config_name", ""))
                temp = float(mcfg.get("temperature") if "temperature" in mcfg else params.get("temperature", llm_conf.get("temperature", 0.7)))
                eff_words = int(params.get("word_number") or 0) or ctx_words
                style_name = scfg.get("style_name") or None
                narrative_name = scfg.get("narrative_style_name") or None
                xp_type = scfg.get("xp_type") or ""
                writing_style = web_app.get_style_content(style_name) if (style_name and hasattr(web_app, "get_style_content")) else ""
                narr_instr = (web_app.get_narrative_instructions(narrative_name).get("for_chapter", "") if (narrative_name and hasattr(web_app, "get_narrative_instructions")) else "")

                guidance_parts = [g for g in [
                    inputs.get("outline", ""),
                    scfg.get("user_guidance", ""),
                    params.get("writing_guidance", ""),
                    mem_obj.get("extra_guidance", ""),
                ] if g and str(g).strip()]
                canon_txt = mem_obj.get("canon_txt", "")
                if canon_txt:
                    guidance_parts.append(f"【正史约束】\n{canon_txt}")
                combined_guidance = "\n\n".join(guidance_parts)
                if xp_type and hasattr(web_app, "_build_xp_guidance"):
                    combined_guidance = web_app._build_xp_guidance(xp_type, combined_guidance)

                custom_tmpl = (params.get("custom_prompt_template") or "").strip()
                custom_prompt_text = None
                if custom_tmpl and not custom_tmpl.startswith("（留空表示直接调用"):
                    custom_prompt_text = (
                        custom_tmpl
                        .replace("{chapter_num}", str(ch))
                        .replace("{word_number}", str(eff_words))
                        .replace("{outline}", inputs.get("outline", ""))
                        .replace("{context_bundle}", mem_obj.get("text", ""))
                        .replace("{guidance}", combined_guidance)
                    )

                emb_conf = emb_configs.get(default_emb, {"api_key": "", "base_url": "", "model_name": "", "retrieval_k": 3})

                def _draft_prog(v=None, desc="", total=None, content=""):
                    emit("node_status", {"node_id": nid, "status": "running", "progress": min(95, int((v or 0.3) * 100)), "message": desc or "起草中..."}, base_val)

                draft_res = generate_chapter_draft(
                    api_key=llm_conf.get("api_key", "auto"),
                    base_url=llm_conf.get("base_url", ""),
                    model_name=llm_conf.get("model_name", "gemini-3.8-flash-low"),
                    filepath=filepath,
                    novel_number=ch,
                    word_number=eff_words,
                    temperature=temp,
                    user_guidance=combined_guidance,
                    embedding_api_key=emb_conf.get("api_key", ""),
                    embedding_url=emb_conf.get("base_url", ""),
                    embedding_interface_format=emb_conf.get("interface_format", default_emb),
                    embedding_model_name=emb_conf.get("model_name", ""),
                    embedding_retrieval_k=emb_conf.get("retrieval_k", 3),
                    interface_format=llm_conf.get("interface_format", "Codex"),
                    max_tokens=int(llm_conf.get("max_tokens", 8192)),
                    timeout=int(llm_conf.get("timeout", 300)),
                    enable_thinking=bool(llm_conf.get("enable_thinking", False)),
                    thinking_budget=int(llm_conf.get("thinking_budget", 0)),
                    writing_style=writing_style,
                    narrative_instruction=narr_instr,
                    inject_world_building=bool(mem_obj.get("inject_world_building", True)),
                    author_style_name=style_name or "",
                    styles_dir=web_app.get_styles_dir() if hasattr(web_app, "get_styles_dir") else "",
                    scene_by_scene=bool(params.get("scene_by_scene", True)) and custom_prompt_text is None,
                    custom_prompt_text=custom_prompt_text,
                    progress=_draft_prog,
                    pipeline_mode="fast_zh",
                    inject_summary=bool(mem_obj.get("inject_summary", True)),
                    inject_char_state=bool(mem_obj.get("inject_char_state", True)),
                    save_to_disk=False,
                )
                out = {"draft_text": draft_res or ""}

            elif ntype == "script_audit":
                src_text = inputs.get("text_in") or ""
                min_score = int(params.get("min_score") or 80)
                on_fail = params.get("on_fail", "pass_to_ai")
                audit = score_chinese_webnovel_text(src_text, target_words=ctx_words)
                score = audit["score"]
                is_pass = score >= min_score

                if not is_pass and on_fail == "pause":
                    session.reset_gate()
                    emit(
                        "gate_waiting",
                        {
                            "node_id": nid,
                            "node_type": "human_gate",
                            "title": f"{label} · 得分 {score} 低于阈值 {min_score}",
                            "text_in": src_text,
                            "draft_text": "",
                            "checklist": audit["summary"],
                        },
                        base_val,
                        f"✋ [{label}] 得分 {score}/{min_score}，等待人工确认或改后放行",
                    )
                    session.gate_event.wait(timeout=1800)
                    if session.cancelled or session.gate_decision.get("action") == "cancel":
                        emit("run_cancelled", {"node_id": nid}, base_val, "🛑 用户在脚本质检环节取消运行")
                        return json.dumps({"success": False, "cancelled": True}, ensure_ascii=False)
                    if session.gate_decision.get("edited_text"):
                        src_text = session.gate_decision["edited_text"]

                out = {
                    "text_out": src_text,
                    "checklist": audit["summary"],
                    "score": score,
                    "passed": is_pass,
                }

            elif ntype == "deai_reviewer":
                from novel_generator.finalization import expand_scenes
                src_text = inputs.get("draft_text") or ""
                if not src_text.strip():
                    raise ValueError("去AI审校节点未收到输入正文（请检查上游连线）。")
                mcfg = inputs.get("model_config") or {}
                scfg = inputs.get("style_config") or {}
                mem_obj = inputs.get("context_bundle") or {}
                mem_txt = mem_obj.get("text", "") if isinstance(mem_obj, dict) else str(mem_obj or "")

                # 修复断层2：显式消费连入的 outline 与 narrative_instruction 及上游脚本检查清单
                outline_in = (inputs.get("outline") or "").strip()
                extra_parts = []
                if outline_in and outline_in not in mem_txt:
                    extra_parts.append(f"【本章细纲（校对剧情依据）】\n{outline_in}")
                if mem_txt.strip():
                    extra_parts.append(mem_txt.strip())
                merged_context = "\n\n".join(extra_parts)

                pref_reviewer = mcfg.get("llm_config_name") or params.get("llm_config_name") or "Gemini 4 Hydrogen (Medium)"
                _, rev_conf = resolve_llm(pref_reviewer)
                temp = float(mcfg.get("temperature") if "temperature" in mcfg else params.get("temperature", rev_conf.get("temperature", 0.5)))
                strength = params.get("review_strength", "strong")
                mode = "editorial_review_light" if strength == "light" else "editorial_review"
                custom_prompt = (params.get("custom_prompt_template") or "").strip()

                style_name = scfg.get("style_name") or None
                narrative_name = scfg.get("narrative_style_name") or None
                writing_style = web_app.get_style_content(style_name) if (style_name and hasattr(web_app, "get_style_content")) else ""
                narr_instr = (web_app.get_narrative_instructions(narrative_name).get("for_chapter", "") if (narrative_name and hasattr(web_app, "get_narrative_instructions")) else "")

                guidance_list = [params.get("custom_guidance", "")]
                in_checklist = (inputs.get("checklist") or "").strip()
                if in_checklist:
                    guidance_list.append(f"【请优先定点整改以下质检隐患】\n{in_checklist}")
                if scfg.get("user_guidance"):
                    guidance_list.append(f"【导演指令】{scfg['user_guidance']}")
                final_guidance = "\n\n".join(g for g in guidance_list if g)

                def _rev_prog(v=None, desc="", total=None, content=""):
                    emit("node_status", {"node_id": nid, "status": "running", "progress": min(95, int((v or 0.4) * 100)), "message": desc or "审校去AI味中..."}, base_val)

                res = expand_scenes(
                    chapter_text=src_text,
                    sensuality_level="",
                    api_key=rev_conf.get("api_key", "auto"),
                    base_url=rev_conf.get("base_url", ""),
                    model_name=rev_conf.get("model_name", "gemini-4-hydrogen-medium"),
                    temperature=temp,
                    interface_format=rev_conf.get("interface_format", "Codex"),
                    max_tokens=int(rev_conf.get("max_tokens", 8192)),
                    timeout=int(rev_conf.get("timeout", 300)),
                    writing_style=writing_style,
                    narrative_instruction=narr_instr,
                    polish_guidance=final_guidance,
                    polish_mode=mode,
                    extra_context=merged_context,
                    progress=_rev_prog,
                    custom_prompt_override=custom_prompt,
                )
                polished, checklist = res, ""
                if "\n---" in res:
                    p0, p1 = res.split("\n---", 1)
                    polished, checklist = p0.strip(), p1.strip()
                elif "【修改清单】" in res:
                    p0, p1 = res.split("【修改清单】", 1)
                    polished, checklist = p0.strip().rstrip("-# \r\n"), "【修改清单】" + p1.strip()
                out = {"polished_text": polished, "checklist": checklist, "raw_input_text": src_text}

            elif ntype == "custom_rewrite":
                from novel_generator.finalization import expand_scenes
                src_text = inputs.get("text_in") or ""
                if not src_text.strip():
                    raise ValueError("自定义改写节点未收到输入正文。")
                mcfg = inputs.get("model_config") or {}
                scfg = inputs.get("style_config") or {}
                mem_obj = inputs.get("context_bundle") or {}
                mem_txt = mem_obj.get("text", "") if isinstance(mem_obj, dict) else str(mem_obj or "")
                outline_in = (inputs.get("outline") or "").strip()
                extra_ctx = "\n\n".join(p for p in [f"【本章细纲】\n{outline_in}" if outline_in and outline_in not in mem_txt else "", mem_txt] if p)

                pref = mcfg.get("llm_config_name") or params.get("llm_config_name") or "Gemini 4 Hydrogen (Medium)"
                _, rew_conf = resolve_llm(pref)
                temp = float(mcfg.get("temperature") if "temperature" in mcfg else params.get("temperature", 0.55))
                instr = params.get("instruction", "提升故事节奏与台词感染力")
                tmpl = (params.get("custom_prompt_template") or DEFAULT_CUSTOM_REWRITE_PROMPT).replace("{instruction}", instr)
                style_name = scfg.get("style_name") or None
                writing_style = web_app.get_style_content(style_name) if (style_name and hasattr(web_app, "get_style_content")) else ""

                res = expand_scenes(
                    chapter_text=src_text,
                    sensuality_level="",
                    api_key=rew_conf.get("api_key", "auto"),
                    base_url=rew_conf.get("base_url", ""),
                    model_name=rew_conf.get("model_name", "gemini-4-hydrogen-medium"),
                    temperature=temp,
                    interface_format=rew_conf.get("interface_format", "Codex"),
                    max_tokens=int(rew_conf.get("max_tokens", 8192)),
                    timeout=int(rew_conf.get("timeout", 300)),
                    writing_style=writing_style,
                    polish_guidance=instr,
                    polish_mode="modify",
                    extra_context=extra_ctx,
                    custom_prompt_override=tmpl,
                )
                text_out, checklist = res, ""
                if "\n---" in res:
                    p0, p1 = res.split("\n---", 1)
                    text_out, checklist = p0.strip(), p1.strip()
                out = {"text_out": text_out, "checklist": checklist, "raw_input_text": src_text}

            elif ntype == "ending_hook_rewriter":
                from llm_adapters import create_llm_adapter
                from novel_generator.common import invoke_with_cleaning
                src_text = (inputs.get("text_in") or "").strip()
                if not src_text:
                    raise ValueError("章末钩子精修节点未收到输入正文。")
                tail_chars = max(150, min(1000, int(params.get("tail_chars") or 420)))
                split_idx = max(0, len(src_text) - tail_chars)
                # 尽量按自然段落边界切分，避免截断半句话
                if split_idx > 100:
                    nl_pos = src_text.find("\n", split_idx - 80, split_idx + 80)
                    if nl_pos != -1:
                        split_idx = nl_pos + 1
                head_keep = src_text[:split_idx]
                tail_old = src_text[split_idx:].strip()
                prefix_ctx = head_keep[-600:] if len(head_keep) > 600 else head_keep

                mcfg = inputs.get("model_config") or {}
                pref = mcfg.get("llm_config_name") or params.get("llm_config_name") or "Gemini 4 Hydrogen (Medium)"
                _, hk_conf = resolve_llm(pref)
                temp = float(mcfg.get("temperature") if "temperature" in mcfg else params.get("temperature", 0.65))
                tmpl = (params.get("custom_prompt_template") or DEFAULT_ENDING_HOOK_PROMPT)
                prompt = (
                    tmpl.replace("{tail_chars}", str(tail_chars))
                    .replace("{prefix_context}", prefix_ctx)
                    .replace("{tail_text}", tail_old)
                )
                outline_in = (inputs.get("outline") or "").strip()
                if outline_in:
                    prompt = f"【本章细纲参考】\n{outline_in}\n\n{prompt}"

                adapter = create_llm_adapter(
                    interface_format=hk_conf.get("interface_format", "Codex"),
                    base_url=hk_conf.get("base_url", ""),
                    model_name=hk_conf.get("model_name", "gemini-4-hydrogen-medium"),
                    api_key=hk_conf.get("api_key", "auto"),
                    temperature=temp,
                    max_tokens=2048,
                    timeout=int(hk_conf.get("timeout", 240)),
                )
                new_tail = (invoke_with_cleaning(adapter, prompt) or tail_old).strip()
                merged_text = (head_keep.rstrip() + "\n\n" + new_tail).strip() if head_keep.strip() else new_tail
                diff_summary = f"【章末钩子切片精修】已重铸结尾 {len(new_tail)} 字（原结尾 {len(tail_old)} 字），前文 {len(head_keep)} 字原封保留。"
                out = {"text_out": merged_text, "checklist": diff_summary, "raw_input_text": src_text}

            elif ntype == "diff_preview":
                text_a = inputs.get("text_a") or ""
                text_b = inputs.get("text_b") or text_a
                checklist = inputs.get("checklist") or ""
                out = {"text_out": text_b, "text_a": text_a, "text_b": text_b, "checklist": checklist}

            elif ntype == "ab_selector":
                branch_a = inputs.get("branch_a") or ""
                branch_b = inputs.get("branch_b") or ""
                ck_a = inputs.get("checklist_a") or ""
                ck_b = inputs.get("checklist_b") or ""
                auto_pick = params.get("auto_pick", "pause")

                chosen_branch = "A"
                if auto_pick == "b" or (is_batch_mode and batch_gate_policy == "auto_pass"):
                    chosen_branch = "B" if (auto_pick == "b" and branch_b) else "A"
                elif branch_a and branch_b:
                    session.reset_gate()
                    emit(
                        "gate_waiting",
                        {
                            "node_id": nid,
                            "node_type": "ab_selector",
                            "title": label,
                            "branch_a": branch_a,
                            "branch_b": branch_b,
                            "checklist_a": ck_a,
                            "checklist_b": ck_b,
                        },
                        base_val,
                        f"⏸️ [{label}] 等待您在画布红绿对比并选择采纳分支 A 或 B...",
                    )
                    session.gate_event.wait(timeout=1800)
                    if session.cancelled or session.gate_decision.get("action") == "cancel":
                        emit("run_cancelled", {"node_id": nid}, base_val, "🛑 用户在 A/B 对比环节取消运行")
                        return json.dumps({"success": False, "cancelled": True}, ensure_ascii=False)
                    chosen_branch = session.gate_decision.get("selected_branch", "A")
                    override_txt = session.gate_decision.get("edited_text")
                    if override_txt:
                        out = {
                            "selected_text": override_txt,
                            "selected_branch": chosen_branch,
                            "selected_checklist": ck_b if chosen_branch == "B" else ck_a,
                            "branch_a": branch_a,
                            "branch_b": branch_b,
                        }
                if not out:
                    sel_txt = branch_b if chosen_branch == "B" and branch_b else (branch_a or branch_b)
                    out = {
                        "selected_text": sel_txt,
                        "selected_branch": chosen_branch,
                        "selected_checklist": ck_b if chosen_branch == "B" else ck_a,
                        "branch_a": branch_a,
                        "branch_b": branch_b,
                    }

            elif ntype == "human_gate":
                text_in = inputs.get("text_in") or ""
                draft_in = inputs.get("draft_text") or ""
                checklist_in = inputs.get("checklist") or ""
                gate_mode = params.get("gate_mode", "always")

                should_pause = (
                    gate_mode == "always" and not (is_batch_mode and batch_gate_policy == "auto_pass")
                ) or (
                    gate_mode == "single_only" and not is_batch_mode
                )
                if is_batch_mode and batch_gate_policy == "always_pause":
                    should_pause = True

                approved = text_in
                if should_pause:
                    session.reset_gate()
                    emit(
                        "gate_waiting",
                        {
                            "node_id": nid,
                            "node_type": "human_gate",
                            "title": label,
                            "text_in": text_in,
                            "draft_text": draft_in,
                            "checklist": checklist_in,
                            "note": params.get("note", ""),
                        },
                        base_val,
                        f"✋ [{label}] 已暂停，等待人工审核确认放行...",
                    )
                    session.gate_event.wait(timeout=1800)
                    if session.cancelled or session.gate_decision.get("action") == "cancel":
                        emit("run_cancelled", {"node_id": nid}, base_val, "🛑 用户拒绝放行，已停止后续写入与归档")
                        return json.dumps({"success": False, "cancelled": True}, ensure_ascii=False)
                    if session.gate_decision.get("edited_text"):
                        approved = session.gate_decision["edited_text"]
                out = {"approved_text": approved, "text_in": text_in, "draft_text": draft_in, "checklist": checklist_in}

            elif ntype == "save_chapter":
                final_txt = inputs.get("final_text") or inputs.get("draft_text") or ""
                draft_txt = inputs.get("draft_text") or final_txt
                checklist_txt = inputs.get("checklist") or ""
                if not final_txt.strip():
                    raise ValueError("章节保存节点未收到正文输入。")
                chapters_dir = os.path.join(filepath, "chapters")
                os.makedirs(chapters_dir, exist_ok=True)
                draft_path = os.path.join(chapters_dir, f"chapter_{ch}_draft.txt")
                final_path = os.path.join(chapters_dir, f"chapter_{ch}.txt")
                save_string_to_txt(draft_txt, draft_path)
                save_string_to_txt(final_txt, final_path)
                if checklist_txt:
                    save_string_to_txt(checklist_txt, os.path.join(chapters_dir, f"chapter_{ch}_polish_checklist.txt"))
                out = {"final_text": final_txt, "saved_path": final_path}

            elif ntype == "memory_archive":
                final_txt = inputs.get("final_text") or ""
                chapters_dir = os.path.join(filepath, "chapters")
                final_path = os.path.join(chapters_dir, f"chapter_{ch}.txt")
                if final_txt.strip() and not os.path.exists(final_path):
                    os.makedirs(chapters_dir, exist_ok=True)
                    save_string_to_txt(final_txt, final_path)

                arch_llm, _ = resolve_llm(params.get("llm_config_name", ""))
                def _arch_prog(v=None, desc="", total=None, content=""):
                    emit("node_status", {"node_id": nid, "status": "running", "progress": min(95, int((v or 0.5) * 100)), "message": desc or "正在提炼记忆与交接..."}, base_val)

                web_app.finalize_chapter_web(
                    llm_config_name=arch_llm,
                    emb_config_name=default_emb,
                    filepath=filepath,
                    chapter_num=ch,
                    word_number=ctx_words,
                    progress=_arch_prog,
                )
                canon_report = ""
                if params.get("update_canon", True) and hasattr(web_app, "update_canon_history_web"):
                    canon_report = web_app.update_canon_history_web(
                        llm_config_name=arch_llm,
                        filepath=filepath,
                        chapter_num=ch,
                        progress=_arch_prog,
                    )
                handoff_dict = None
                try:
                    from novel_generator.continuity import get_semantic_handoff
                    lh = get_semantic_handoff(filepath, ch)
                    if lh:
                        handoff_dict = lh.to_dict()
                except Exception:
                    pass
                out = {"handoff": json.dumps(handoff_dict, ensure_ascii=False) if handoff_dict else "已归档", "canon_report": str(canon_report or "")}

            else:
                out = {"output": next(iter(inputs.values()), "") if inputs else ""}

            elapsed_ms = int((time.time() - t0) * 1000)
            node_outputs[nid] = out
            done_msg = f"完成 ({elapsed_ms/1000:.1f}s)"
            if ntype == "script_audit" and "score" in out:
                done_msg = f"质检得分 {out['score']}/100 ({'通过' if out.get('passed') else '有隐患'})"

            emit(
                "node_status",
                {
                    "node_id": nid,
                    "status": "completed",
                    "progress": 100,
                    "elapsed_ms": elapsed_ms,
                    "message": done_msg,
                    "outputs": out,
                },
                (idx + 1) / total_steps,
                f"✅ [{label}] {done_msg}",
            )

        emit("run_completed", {"chapter_num": chapter_num, "outputs": node_outputs}, 1.0, f"🎉 第 {chapter_num} 章工作流执行完毕！")
        return json.dumps({"success": True, "run_id": run_id, "chapter_num": chapter_num, "outputs": node_outputs}, ensure_ascii=False)

    except Exception as e:
        logger.error(f"[WorkflowDAG] 执行失败: {e}", exc_info=True)
        emit("run_error", {"error": str(e)}, 1.0, f"❌ 工作流执行异常: {e}")
        return json.dumps({"success": False, "error": str(e), "outputs": node_outputs}, ensure_ascii=False)
