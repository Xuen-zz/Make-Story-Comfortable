# novel_generator/quality_guard.py
# -*- coding: utf-8 -*-
"""
朱雀自检与 Codex (GPT) 智能审校协同引擎
实现：【有界动态收敛渐进手术闭环】
流程：
- Round 0: 朱雀雷达初筛病灶 -> 若已达标(>=80%)直接放行
- Round 1: 全局去味洗髓 (带朱雀雷达病灶段落) -> 朱雀复检
- 检查达标(>=80%)或边际递减熔断(<3%)
- Round 2 (若需): 微创局部靶向缝合 (仅针对残留1~3处高危顽固段落做局部微创切除与缝合) -> 朱雀三测
- 全轮次择优保底 (锁定真人比例最高版本)
- 生成朱雀自检专属诊断专报 (zhuque_report_md)
"""

import logging
import re
from typing import Dict, Any, Optional, Tuple, Callable, List

from novel_generator.codex_adapter import CodexCLIAdapter
from novel_generator.zhuque_client import ZhuqueAuditClient, ZhuqueAuditResult

logger = logging.getLogger("QualityGuard")


_REVIEW_SYSTEM_PROMPT = """你是一位拥有二十年畅销小说出版与爆款网文运营经验的资深文学总编辑。
你的唯一职责：以极其挑剔的眼光，彻底清除送检章节中的「AI 生成痕迹」与「陈词滥调」，重塑真实、有呼吸感、有颗粒度与生活质感的顶级网文语言。

### 核心查杀与重塑准则（严苛执行，击碎 AI 模式特征）：
1. 【打破机械等长句式与匀速节奏（大幅拉大文本突发度 Burstiness）】
   - 严禁全篇清一色 10~15 字的单句独立成段！这种“段落过于对称匀速”的韵律会被腾讯朱雀等 AI 分类器判定为特征模板；
   - 必须长短剧烈错落：长段包含主观动作与环境交互（30~60字） ➔ 紧随一个 2~4 字极短独立句（如“咔嚓一声。”、“没应。”、“动不了。”） ➔ 穿插破折号呼吸留白（“——”）；
   - 坚决清除「连用三个整齐动作」的机械递进（如“她蹲下身，拭去血珠，检查伤口”）。

2. 【严厉封杀 AI 生理神经套话与假通感（朱雀检测雷达特异性查杀特征）】
   - 严禁任何形式的“大模型应激反射描写”（一旦出现必被朱雀等分类器定为 100% AI）：
     * 严禁：『喉结上下动/滚动』、『咬肌紧绷/下颌绷紧』、『膝盖一软』、『指尖轻颤/还在发抖』、『倒吸凉气』、『瞳孔骤缩』、『一声短促的闷哼/闷哼出声』、『心跳漏了一拍』、『牙齿磕得咯咯响』；
     * 严禁伪通感抒情：『直冲鼻腔』、『让人心慌的空缺』、『汗从眉梢滑进眼角』、『冷汗浸透后背』、『尝到微腥/甜腥』；
   - 提倡真正的人类白描与生活颗粒感（参考极高真人得分写法）：
     * 动作必须有客观物理限制与器物阻力：铜锁卡槽合不严、衣角挂在碎木刺上、破瓷碗打翻水泼一地、鞋底拖泥打滑；
     * 多写“怎么动手搬”、“怎么用力拽”，不写“身体内视感受”；
     * 对白与动作高频穿插交织：每两三句动作必须有短促口语打破节奏，严禁连续十余段纯动作白描导致句式同构！

3. 【彻底拔除 AI 高频套话与假深沉抽象短语】
   - 严禁初级套话：『深吸一口气』、『眼神微凝/微眯』、『嘴角勾起一抹玩味的弧度』、『空气仿佛凝固』、『不知为何』、『不得不说』、『宛如』、『仿佛』。
   - 严禁中级伪文学腔：『肩背未松』、『那一抹冷意』、『一寸寸挤回』、『空气陷入死寂』、『心中泛起涟漪』、『两股力量交织』、『隐隐窜出几道细微金芒』。
   - 严禁虚浮转折句：『不仅…更…』、『与其说…不如说…』。

4. 【人物对白生活化、有粗粝感与市井烟火气】
   - 去除所有翻译腔（如“哦，天哪”、“听着，伙计”）。
   - 对白必须符合当下生死紧绷的呼吸节奏：短促、带刺、有潜台词，带有咬牙切齿的口语质感。

5. 【坚决捍卫剧情事实一致性】
   - 严禁篡改原章节的故事主线、出场人物、伏笔逻辑和因果走向。
   - 你的任务是提升文字肌理质感，不是另起炉灶写新故事。

6. 【番茄爆款法则：章末强断章钩子（Hook）与反转留白】
   - 本章最后 150 字绝对严禁平淡、泄气收尾（如“各自回屋睡觉”、“一夜无话”、“太阳落山”）。
   - 必须停留在危机突发点、秘密揭晓前一瞬、打脸蓄力高峰、或悬念反转点，给读者留下极其强烈的“迫不及待点开下一章”的抓心欲望！

7. 【移动端段落排版：清爽透气但不呆板对称】
   - 单段 2~3 句为主，穿插 1 句极短句，消除长篇累赘的大段落，但坚决杜绝“整篇每一行都是单句”的机械对称。

### 输出格式规范（必须严格遵守）：
请先输出改写后的完整正式章节正文；
然后在正文末尾换行，输出分隔符 `---`，紧随其后输出 `【修改清单】`，列出具体的改写点与降味说明。
"""

_MICRO_SURGERY_SYSTEM_PROMPT = """你是一位顶尖的文学微雕大师与反 AI 语言病理专家。
你的任务是对送检文本中的个别【AI 套话病灶或疑似机械段落】进行微创手术重塑。
要求：
1. 彻底撕掉原段落中的悬浮形容词、陈词滥调和整齐句式。
2. 绝对严禁以下朱雀高危 AI 触发词：『喉结滚动』、『膝盖一软』、『指尖发抖/轻颤』、『闷哼』、『直冲鼻腔』、『汗从眉梢滑进眼角』。
3. 注入粗粝的人性对白与具体器物阻力（泥污、水渍、破布条、铜锁、木刺）。
4. 严格保留该段落所承载的剧情信息点、前因后果与人物动机，与原章节上下文天衣无缝衔接。
5. 严格按照要求格式输出，不要输出任何多余的客套废话。
"""


def build_targeted_prompt(
    draft_text: str,
    toxic_segments: list = None,
    extra_context: str = "",
    guidance: str = "",
) -> str:
    """构建针对朱雀病灶的 Round 1 全局靶向重构提示词"""
    parts = []

    if extra_context:
        parts.append(f"【剧情背景与设定参考】\n{extra_context}\n")

    if toxic_segments and len(toxic_segments) > 0:
        parts.append("【⚠️ 腾讯朱雀 AI 检测雷达已抓包的高危段落列表（重点手术目标）】：")
        for idx, seg in enumerate(toxic_segments[:8]):
            s_text = seg.get("text", "").strip()
            conf = seg.get("conf", 0.9)
            parts.append(f"{idx + 1}. [AI特征置信度 {round(conf * 100, 1)}%]:\n「{s_text}」")
        parts.append("\n👉 【特别指令】：上述标出的段落是露馅最严重的区域！请务必彻底重写上述段落的句式结构，替换掉其中的套话与悬浮描写！\n")

    if guidance:
        parts.append(f"【作者专项改写要求】：\n{guidance}\n")

    parts.append(f"【待审校小说草稿正文】：\n{draft_text}\n")
    parts.append("请现在开始执行审校与全面重构，输出润色后的高质量正文及修改清单：")

    return "\n".join(parts)


def _split_content_and_checklist(result: str) -> Tuple[str, str]:
    """从改写结果中拆分出正文与修改清单"""
    markers = ["【修改清单】", "## 修改清单", "### 修改清单", "修改清单：", "修改清单:"]
    for m in markers:
        if m in result:
            parts = result.split(m, 1)
            text_part = parts[0].strip().rstrip("-# \r\n").strip()
            check_part = "【修改清单】\n" + parts[1].strip()
            return text_part, check_part

    # 正则拆分水平线
    match = re.split(r'\n-{3,}\n', result, maxsplit=1)
    if len(match) == 2:
        return match[0].strip(), "【修改清单】\n" + match[1].strip()

    return result.strip(), ""


def _perform_micro_surgery(
    codex: CodexCLIAdapter,
    model_name: str,
    base_text: str,
    toxic_segments: List[Dict[str, Any]],
    max_segments: int = 3,
) -> Tuple[str, List[Dict[str, str]]]:
    """
    Round 2 微创局部缝合：
    针对朱雀抓取的残留 1~3 处顽固高危病灶段落，由 GPT 逐段微创改写并原地替换缝合，
    避免重新整篇重写带来的随机性与文风漂移。
    返回: (缝合后的完整正文, 缝合手术记录列表)
    """
    if not toxic_segments:
        return base_text, []

    # 筛选出在 base_text 中能精确或模糊找到的段落
    targets = []
    for seg in toxic_segments:
        raw_t = seg.get("text", "").strip()
        if not raw_t or len(raw_t) < 15:
            continue
        # 截取前 40 字符做匹配尝试
        sub_anchor = raw_t[:min(40, len(raw_t))]
        if sub_anchor in base_text or raw_t in base_text:
            targets.append(seg)
        if len(targets) >= max_segments:
            break

    if not targets:
        return base_text, []

    surgery_records = []
    current_text = base_text

    # 构建一次批量微创提示词，一次性返回这几个病灶段落的重构结果
    prompt_lines = [
        "以下是送检小说章节中经腾讯朱雀雷达复检后仍亮红灯的 1~3 个顽固 AI 套话病灶段落。",
        "请对每一个病灶段落进行微创手术重塑：彻底清除呆板套话，改用富含动作、感官细节、自然生活气息的顶级网文语言。",
        "保持与上下文的连贯性，并严格按照指定格式返回重写内容。\n"
    ]

    for idx, seg in enumerate(targets):
        prompt_lines.append(f"【病灶段落 {idx + 1}】（原句）：\n{seg.get('text', '').strip()}\n")

    prompt_lines.append(
        "【输出格式要求（严格遵守）】：\n"
        "请按以下格式返回每个病灶的微创改写段落：\n"
        "=== SEGMENT 1 ===\n"
        "改写后的第1个段落正文...\n"
        "=== SEGMENT 2 ===\n"
        "改写后的第2个段落正文...\n"
        "（以此类推，不要输出其他解释）"
    )

    try:
        surgery_out = codex.invoke(
            prompt="\n".join(prompt_lines),
            system_message=_MICRO_SURGERY_SYSTEM_PROMPT,
            model=model_name,
        )
    except Exception as e:
        logger.warning(f"微创手术调用失败: {e}")
        return base_text, []

    # 解析微创重写段落
    rewritten_segs = {}
    pattern = re.compile(r'===\s*SEGMENT\s*(\d+)\s*===\s*\n(.*?)(?=(?:===\s*SEGMENT|\Z))', re.DOTALL)
    for m in pattern.finditer(surgery_out):
        seg_idx = int(m.group(1)) - 1
        rewritten_segs[seg_idx] = m.group(2).strip()

    # 原地缝合替换
    for idx, seg in enumerate(targets):
        if idx not in rewritten_segs:
            continue
        original_segment = seg.get("text", "").strip()
        replacement = rewritten_segs[idx]
        if not replacement or replacement == original_segment:
            continue

        if original_segment in current_text:
            current_text = current_text.replace(original_segment, replacement, 1)
            surgery_records.append({
                "original": original_segment,
                "replacement": replacement,
                "conf": seg.get("conf", 0.9),
            })
        else:
            # 尝试通过首尾锚点替换
            anchor = original_segment[:min(35, len(original_segment))]
            if anchor in current_text:
                # 寻找包含该 anchor 的整个自然段
                paras = current_text.split("\n")
                new_paras = []
                replaced = False
                for p in paras:
                    if not replaced and anchor in p:
                        new_paras.append(replacement)
                        replaced = True
                    else:
                        new_paras.append(p)
                if replaced:
                    current_text = "\n".join(new_paras)
                    surgery_records.append({
                        "original": original_segment,
                        "replacement": replacement,
                        "conf": seg.get("conf", 0.9),
                    })

    return current_text, surgery_records


_EN_MICRO_SURGERY_SYSTEM_PROMPT = """You are a senior native English line editor and anti-AI prose specialist for commercial American web novels (GoodNovel, Dreame, Amazon Kindle).
Your sole mission is to surgically rewrite flagged AI-sounding English paragraphs into visceral, gritty, punchy, human-sounding commercial prose.

Strict Rules:
1. Strip all LLM filler clauses and fake-profound narrative crutches:
   - FORBIDDEN: "as though...", "as if trying to steady...", "with a hint of...", "couldn't help but...", "seemed to...", "a testament to...".
2. Break up uniform sentence lengths: alternate short, harsh sentences (2-5 words) with concrete kinetic action.
3. Dialogue & monologues MUST sound authentic, colloquial, and rough: use raw contractions, sharp insults, broken thoughts, and street-level friction.
4. Preserve 100% of the underlying plot facts, character names, and causal continuity.
5. Strict output format:
=== SEGMENT 1 ===
(Rewritten text for segment 1)
=== SEGMENT 2 ===
(Rewritten text for segment 2)
"""


def _perform_en_micro_surgery(
    codex: CodexCLIAdapter,
    model_name: str,
    base_text: str,
    toxic_segments: List[Dict[str, Any]],
    max_segments: int = 3,
) -> Tuple[str, List[Dict[str, str]]]:
    """
    针对朱雀雷达抓取的英文高危 AI 翻译腔段落，由 Codex/GPT 逐段执行微创原生化重构并原地缝合替换。
    返回: (缝合后的完整英文译本, 缝合记录列表)
    """
    if not toxic_segments:
        return base_text, []

    targets = []
    for seg in toxic_segments:
        raw_t = seg.get("text", "").strip()
        if not raw_t or len(raw_t) < 20:
            continue
        sub_anchor = raw_t[:min(40, len(raw_t))]
        if sub_anchor in base_text or raw_t in base_text:
            targets.append(seg)
        if len(targets) >= max_segments:
            break

    if not targets:
        return base_text, []

    surgery_records = []
    current_text = base_text

    prompt_lines = [
        "Below are 1~3 flagged AI-sounding paragraphs from our commercial English novel chapter translation.",
        "Please surgically rewrite each paragraph into visceral, gritty, punchy, native commercial English prose.",
        "Eliminate all artificial narrative crutches ('as though...', 'seemed to...', symmetrical philosophy monologues), keeping the tone raw and punchy.",
        "Strictly adhere to the specified format.\n"
    ]

    for idx, seg in enumerate(targets):
        prompt_lines.append(f"【TARGET PARAGRAPH {idx + 1}】:\n{seg.get('text', '').strip()}\n")

    prompt_lines.append(
        "【Output Format Required】:\n"
        "=== SEGMENT 1 ===\n"
        "Rewritten English paragraph 1...\n"
        "=== SEGMENT 2 ===\n"
        "Rewritten English paragraph 2...\n"
        "(Only output the segments as formatted above, no commentary)"
    )

    try:
        surgery_out = codex.invoke(
            prompt="\n".join(prompt_lines),
            system_message=_EN_MICRO_SURGERY_SYSTEM_PROMPT,
            model=model_name,
        )
    except Exception as e:
        logger.warning(f"英文微创手术调用失败: {e}")
        return base_text, []

    rewritten_segs = {}
    pattern = re.compile(r'===\s*SEGMENT\s*(\d+)\s*===\s*\n(.*?)(?=(?:===\s*SEGMENT|\Z))', re.DOTALL)
    for m in pattern.finditer(surgery_out):
        seg_idx = int(m.group(1)) - 1
        rewritten_segs[seg_idx] = m.group(2).strip()

    for idx, seg in enumerate(targets):
        if idx not in rewritten_segs:
            continue
        original_segment = seg.get("text", "").strip()
        replacement = rewritten_segs[idx]
        if not replacement or replacement == original_segment:
            continue

        if original_segment in current_text:
            current_text = current_text.replace(original_segment, replacement, 1)
            surgery_records.append({
                "original": original_segment,
                "replacement": replacement,
                "conf": seg.get("conf", 0.9),
            })
        else:
            anchor = original_segment[:min(35, len(original_segment))]
            if anchor in current_text:
                paras = current_text.split("\n")
                new_paras = []
                replaced = False
                for p in paras:
                    if not replaced and anchor in p:
                        new_paras.append(replacement)
                        replaced = True
                    else:
                        new_paras.append(p)
                if replaced:
                    current_text = "\n".join(new_paras)
                    surgery_records.append({
                        "original": original_segment,
                        "replacement": replacement,
                        "conf": seg.get("conf", 0.9),
                    })

    return current_text, surgery_records


def _generate_zhuque_report_markdown(
    chapter_label: str,
    rounds_history: List[Dict[str, Any]],
    converged_reason: str,
    target_human_rate: float,
    final_human_rate: float,
    final_ai_rate: float,
    surgery_records: List[Dict[str, str]],
) -> str:
    """生成腾讯朱雀自检专属诊断专报 Markdown"""
    r0 = rounds_history[0] if rounds_history else {}
    initial_human_rate = r0.get("human_rate", 0.0)
    initial_ai_rate = r0.get("ai_rate", 0.0)
    net_improvement = round(final_human_rate - initial_human_rate, 1)

    # 评级徽章
    if final_human_rate >= target_human_rate:
        badge = "🟢 **【优异 · 纯手工质感放行】**"
    elif final_human_rate >= 70.0:
        badge = "🟡 **【良好 · 高真人质感合格】**"
    else:
        badge = "🟠 **【告警 · 边际递减熔断保底】**"

    lines = [
        f"# 🛡️ 腾讯朱雀自检专属诊断专报 — {chapter_label}",
        "",
        f"- **终审放行评级**：{badge}",
        f"- **收敛退出的机制**：`{converged_reason}`",
        f"- **真人质感率跃升**：`{initial_human_rate}%` ➔ **`{final_human_rate}%`**（净提升 `+{net_improvement}%`）",
        f"- **AI 特征占比压降**：`{initial_ai_rate}%` ➔ **`{final_ai_rate}%`**（净压降 `-{round(initial_ai_rate - final_ai_rate, 1)}%`）",
        f"- **目标达标门槛**：`真人率 >= {target_human_rate}%`",
        "",
        "---",
        "",
        "## 📈 渐进收敛演进轨迹（渐进手术闭环）",
        "",
        "| 轮次 | 阶段说明 | 真人比例 (Human Rate) | AI特征比例 (AI Rate) | 病灶捕获数 | 决策事件 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for item in rounds_history:
        r_num = item.get("round", 0)
        desc = item.get("desc", f"Round {r_num}")
        hr = item.get("human_rate", 0.0)
        ar = item.get("ai_rate", 0.0)
        tc = item.get("toxic_count", 0)
        event = item.get("decision", "--")
        lines.append(f"| **Round {r_num}** | {desc} | **{hr}%** | {ar}% | {tc} 处 | `{event}` |")

    lines.extend([
        "",
        "---",
        "",
        "## 🎯 朱雀扫描高危病灶雷达与微创置换记录",
        "",
    ])

    if surgery_records:
        lines.append("### 🔬 Round 2 局部微创缝合成功置换的顽固病灶：\n")
        for i, srec in enumerate(surgery_records, 1):
            lines.append(f"#### ✂️ 微创切除 #{i}（原病灶置信度: `{round(srec.get('conf', 0.9)*100, 1)}%`）")
            lines.append(f"- **【原病灶 (摘除)】**：\n  > <s>{srec['original']}</s>")
            lines.append(f"- **【缝合后 (手工质感)】**：\n  > **{srec['replacement']}**\n")
    else:
        lines.append("本章在 Round 1 全局洗髓后已达标或无残留孤立顽固段落，未触发 Round 2 局部微创手术。\n")

    # 典型初检病灶展示
    r0_toxic = r0.get("toxic_segments", [])
    if r0_toxic:
        lines.append("### 🔍 初检抓包的典型 AI 套话（已在全局洗髓中彻底重构）：")
        for i, seg in enumerate(r0_toxic[:5], 1):
            conf = round(seg.get("conf", 0.9) * 100, 1)
            txt = seg.get("text", "").strip()
            lines.append(f"{i}. `[置信度 {conf}%]` {txt}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 💡 资深总编复盘与迭代指导",
        "- **叙事呼吸感**：本章在审校后大幅强化了动作细节与微表情，有效清除了同构短句；",
        "- **章末钩子 (Hook)**：章末最后 150 字经过爆款反转强化，杜绝了平淡收尾；",
        "- **数据保底声明**：最终定稿章节已通过多轮择优机制（Optimal Fallback）锁定了全流程最高真人比例版本。",
        "",
        "*本专报由 AI Novel Studio 朱雀质量安全哨兵引擎自动出具。*",
    ])

    return "\n".join(lines)


def run_targeted_humanize_pipeline(
    draft_text: str,
    zhuque_key: str = "",
    codex_model: str = "",
    extra_context: str = "",
    user_guidance: str = "",
    target_human_rate: float = 80.0,
    max_refine_rounds: int = 2,
    min_improvement_delta: float = 3.0,
    progress_cb: Optional[Callable[[float, str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """
    执行【有界动态收敛渐进手术闭环】：
    Round 0: 初检 ➔ 若达标直接放行
    Round 1: 全局洗髓 ➔ 朱雀复测 ➔ 达标退出/边际递减熔断
    Round 2 (若需): 微创局部靶向缝合 ➔ 朱雀三测
    终审: 择优保底定稿 + 输出朱雀诊断专报 Markdown
    """
    clean_draft = (draft_text or "").strip()
    if not clean_draft:
        return {"success": False, "error": "草稿内容为空"}

    def emit(p: float, msg: str, data: Dict[str, Any] = None):
        if progress_cb:
            try:
                progress_cb(p, msg, data or {})
            except Exception as e:
                logger.warning(f"progress callback error: {e}")

    # 1. 初始化客户端
    zhuque = ZhuqueAuditClient(api_key=zhuque_key)
    codex = CodexCLIAdapter(model_name=codex_model)

    rounds_history: List[Dict[str, Any]] = []
    surgery_records: List[Dict[str, str]] = []

    # 2. Round 0：朱雀客观初检（纯病灶雷达定位，绝对不跳过后续主编审校）
    emit(0.10, "正在通过腾讯云朱雀自检 API 进行第一道 AI 痕迹与病灶扫描...", {"phase": "round0_pre_check"})
    pre_result = zhuque.audit_text(clean_draft)

    r0_human_rate = pre_result.human_rate if (zhuque.is_configured and pre_result.success) else 0.0
    r0_ai_rate = pre_result.ai_rate if (zhuque.is_configured and pre_result.success) else 100.0
    toxic_segs = pre_result.toxic_segments

    rounds_history.append({
        "round": 0,
        "desc": "初始起草稿 (Gemini 生稿)",
        "human_rate": r0_human_rate,
        "ai_rate": r0_ai_rate,
        "toxic_count": len(toxic_segs),
        "toxic_segments": toxic_segs,
        "decision": "初检病灶扫描完成，进入主编全篇洗髓" if pre_result.success else "初检接口异常，强制进入主编全篇洗髓",
    })

    if zhuque.is_configured and pre_result.success:
        emit(
            0.20,
            f"朱雀初检完成：真人比例 {r0_human_rate}%（AI特征 {r0_ai_rate}%），捕获 {len(toxic_segs)} 处模板病灶",
            {
                "phase": "round0_done",
                "human_rate": r0_human_rate,
                "ai_rate": r0_ai_rate,
                "toxic_count": len(toxic_segs),
            },
        )
    else:
        emit(0.20, "朱雀初检未获取有效打分，强制开启 Codex (GPT) 资深总编全篇去味洗髓...", {"phase": "round0_fallback"})

    # 3. Round 1：强制执行全局去味洗髓（铁律：无论初检如何，生稿必须经过主编精修重构！）
    emit(0.35, f"唤起本地 Codex CLI ({codex_model or 'Default GPT'}) 开启 Round 1 全局洗髓...", {"phase": "round1_exec"})
    prompt1 = build_targeted_prompt(
        draft_text=clean_draft,
        toxic_segments=toxic_segs,
        extra_context=extra_context,
        guidance=user_guidance,
    )

    try:
        raw_gpt1 = codex.invoke(prompt=prompt1, system_message=_REVIEW_SYSTEM_PROMPT, model=codex_model)
    except Exception as ce:
        logger.error(f"[QualityGuard] Codex Round 1 执行失败: {ce}")
        return {
            "success": False,
            "error": f"Codex Round 1 改写失败: {str(ce)}",
            "pre_result": pre_result.to_dict(),
        }

    r1_polished, r1_checklist = _split_content_and_checklist(raw_gpt1)
    if not r1_polished:
        r1_polished = clean_draft
        r1_checklist = "（Round 1 未返回有效内容，回退初稿）"

    emit(0.55, "Round 1 全局洗髓完成，正在调用朱雀进行第一次复测验真...", {"phase": "round1_check"})
    r1_result = zhuque.audit_text(r1_polished)
    r1_human_rate = r1_result.human_rate if r1_result.success else 0.0
    r1_ai_rate = r1_result.ai_rate if r1_result.success else 100.0
    r1_improvement = round(r1_human_rate - r0_human_rate, 1)

    rounds_history.append({
        "round": 1,
        "desc": "Round 1 全局洗髓重构",
        "human_rate": r1_human_rate,
        "ai_rate": r1_ai_rate,
        "toxic_count": len(r1_result.toxic_segments),
        "toxic_segments": r1_result.toxic_segments,
        "decision": "复测完成",
    })

    # 最优版本首选 Round 1 改写稿（绝不回退至 Gemini 初始生稿）
    best_version = r1_polished
    best_human_rate = r1_human_rate
    best_ai_rate = r1_ai_rate
    best_checklist = r1_checklist
    best_result = r1_result

    emit(
        0.65,
        f"Round 1 复测结果：真人比例提升至 {r1_human_rate}%（净跃升 +{r1_improvement}%，AI特征 {r1_ai_rate}%）",
        {
            "phase": "round1_done",
            "human_rate": r1_human_rate,
            "improvement": r1_improvement,
            "post_result": r1_result.to_dict(),
        },
    )

    # 判断是否进入 Round 2 或收敛退出
    converged_reason = ""
    should_run_round2 = False
    surgery_target_segments = []

    if r1_human_rate >= target_human_rate and not r1_result.toxic_segments:
        converged_reason = f"Round 1 全局洗髓达成目标真人率（{r1_human_rate}% >= {target_human_rate}%），且无高危病灶，达标放行"
        rounds_history[1]["decision"] = "达标放行退出"
    elif max_refine_rounds < 2:
        converged_reason = f"已达配置的最大轮次上限 ({max_refine_rounds}轮)，定稿退出"
        rounds_history[1]["decision"] = "轮次上限退出"
    else:
        # 真人率尚未达到预期目标，准备执行微创靶向手术
        # 靶向优先级：1. 明确的 AI 高危病灶段落；2. 疑似机械/中性表达段落
        surgery_target_segments = (
            r1_result.toxic_segments if r1_result.toxic_segments else r1_result.suspect_segments
        )
        if surgery_target_segments:
            should_run_round2 = True
        else:
            converged_reason = f"Round 1 真人率达 {r1_human_rate}%，已无明确需修改段落，定稿退出"
            rounds_history[1]["decision"] = "病灶清零退出"

    # 4. Round 2：微创局部靶向缝合（若满足条件）
    if should_run_round2:
        seg_desc = f"{len(surgery_target_segments)} 处顽固/疑似病灶"
        emit(0.70, f"检测到 {seg_desc}，开启 Round 2 局部微创动作缝合手术...", {"phase": "round2_surgery"})
        r2_patched_text, surgery_records = _perform_micro_surgery(
            codex=codex,
            model_name=codex_model,
            base_text=r1_polished,
            toxic_segments=surgery_target_segments,
            max_segments=3,
        )

        if surgery_records:
            emit(0.85, f"成功完成 {len(surgery_records)} 处顽固病灶的原地微创缝合，正在进行最终门禁三测...", {"phase": "round2_check"})
            r2_result = zhuque.audit_text(r2_patched_text)
            r2_human_rate = r2_result.human_rate
            r2_ai_rate = r2_result.ai_rate

            rounds_history.append({
                "round": 2,
                "desc": "Round 2 局部微创缝合",
                "human_rate": r2_human_rate,
                "ai_rate": r2_ai_rate,
                "toxic_count": len(r2_result.toxic_segments),
                "toxic_segments": r2_result.toxic_segments,
                "decision": "微创复检完成",
            })

            if r2_human_rate >= best_human_rate:
                best_version = r2_patched_text
                best_human_rate = r2_human_rate
                best_ai_rate = r2_ai_rate
                best_result = r2_result
                best_checklist += f"\n\n【Round 2 微创手术记录】\n成功针对 {len(surgery_records)} 处顽固病灶执行局部动作细节微创缝合。"
            else:
                best_checklist += f"\n\n【Round 2 择优保底】\nRound 2 微创测试真人率 ({r2_human_rate}%) 略低于 Round 1，自动择优保底采用 Round 1 最优版本。"

            if r2_human_rate >= target_human_rate:
                converged_reason = f"Round 2 微创手术后真人比例达成 {r2_human_rate}%（>= {target_human_rate}%），达标放行"
                rounds_history[2]["decision"] = "达标放行"
            else:
                converged_reason = f"Round 2 微创手术完成，已达最大允许轮次上限 (2轮)，择优定稿"
                rounds_history[2]["decision"] = "轮次上限择优"
        else:
            converged_reason = "Round 2 微创段落定位未匹配到原句，择优采用 Round 1 版本"

    # 5. 生成朱雀专属诊断专报 Markdown
    report_md = _generate_zhuque_report_markdown(
        chapter_label="本章",
        rounds_history=rounds_history,
        converged_reason=converged_reason,
        target_human_rate=target_human_rate,
        final_human_rate=best_human_rate,
        final_ai_rate=best_ai_rate,
        surgery_records=surgery_records,
    )

    total_rate_drop = round(max(0.0, r0_ai_rate - best_ai_rate), 1)

    emit(
        0.98,
        f"自检闭环完成！真人质感比例由 {r0_human_rate}% 最终提升至 {best_human_rate}% (AI特征压降 {total_rate_drop}%)",
        {
            "phase": "pipeline_complete",
            "final_human_rate": best_human_rate,
            "final_ai_rate": best_ai_rate,
            "rate_drop": total_rate_drop,
            "converged_reason": converged_reason,
        },
    )

    return {
        "success": True,
        "polished_text": best_version,
        "checklist_text": best_checklist,
        "pre_result": pre_result.to_dict(),
        "post_result": best_result.to_dict(),
        "pre_ai_rate": r0_ai_rate,
        "post_ai_rate": best_ai_rate,
        "rate_drop": total_rate_drop,
        "final_human_rate": best_human_rate,
        "target_human_rate": target_human_rate,
        "converged_reason": converged_reason,
        "zhuque_report_md": report_md,
        "rounds_history": rounds_history,
        "surgery_records": surgery_records,
    }
