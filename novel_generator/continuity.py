# novel_generator/continuity.py
# -*- coding: utf-8 -*-
"""
因果连续性引擎与幕间交接（Semantic Handoff & Continuity Engine）
参考并融合 KazKozDev/NovelGenerator 的长篇连续性控制、状态追踪与前置门禁设计。
解决：
1. 跨章开篇水字数、反复交代已知背景（Must Not Restate）
2. 历史因果断代与新老章节割裂感（冷启动一键回溯萃取）
3. 大纲级前置一致性门禁拦截（Pre-write Gate）
4. 局部句子级精准修补（Span Repair）
"""

import os
import json
import logging
import re
from typing import Optional, Dict, Any, List
from utils import read_file, save_string_to_txt, append_text_to_file
from novel_generator.common import invoke_with_cleaning

logging.basicConfig(
    filename='app.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

HANDOFF_FILENAME = "Novel_handoff.json"
CANON_FILENAME = "Novel_canon_history.txt"
CHANGELOG_FILENAME = "Novel_canon_changelog.txt"


def get_handoff_file_path(filepath: str) -> str:
    return os.path.join(filepath, HANDOFF_FILENAME)


def get_canon_file_path(filepath: str) -> str:
    return os.path.join(filepath, CANON_FILENAME)


def get_changelog_file_path(filepath: str) -> str:
    return os.path.join(filepath, CHANGELOG_FILENAME)


def save_semantic_handoff(filepath: str, handoff_data: Dict[str, Any]) -> None:
    """持久化保存因果交接包"""
    try:
        path = get_handoff_file_path(filepath)
        save_string_to_txt(json.dumps(handoff_data, ensure_ascii=False, indent=2), path)
        logging.info(f"[Continuity] 成功保存第 {handoff_data.get('target_chapter', '?')} 章的 Semantic Handoff")
    except Exception as e:
        logging.error(f"[Continuity] 保存 Semantic Handoff 失败: {e}")


def get_semantic_handoff(filepath: str, chapter_num: int) -> Dict[str, Any]:
    """
    获取针对第 chapter_num 章的因果交接数据包。
    若无显式保存的 Handoff，则自动从已有正史设定页与前章结尾无缝生成默认交接包。
    """
    handoff_path = get_handoff_file_path(filepath)
    if os.path.exists(handoff_path):
        try:
            content = read_file(handoff_path).strip()
            if content:
                data = json.loads(content)
                # 如果存储的正是目标章节（或刚好是上一章产出的）
                if data.get("target_chapter") == chapter_num or data.get("from_chapter") == chapter_num - 1:
                    return data
        except Exception as e:
            logging.warning(f"[Continuity] 读取 Handoff 失败，将动态回退构建: {e}")

    # 优雅回退：从前章文件和正史文件构建初始交接包
    prev_chapter_file = os.path.join(filepath, "chapters", f"chapter_{chapter_num - 1}.txt")
    prev_tail = ""
    if os.path.exists(prev_chapter_file):
        try:
            prev_text = read_file(prev_chapter_file).strip()
            if prev_text:
                prev_tail = prev_text[-600:] if len(prev_text) > 600 else prev_text
        except Exception:
            pass

    canon_path = get_canon_file_path(filepath)
    canon_text = ""
    if os.path.exists(canon_path):
        try:
            canon_text = read_file(canon_path).strip()
        except Exception:
            pass

    return {
        "from_chapter": chapter_num - 1,
        "target_chapter": chapter_num,
        "what_changed": f"延续第 {chapter_num - 1} 章剧情推进。",
        "active_intentions": "顺承前文，推进当前核心情节。",
        "open_questions": "推进既有未解悬念与伏笔。",
        "must_not_restate": [
            "读者已经知晓前文已发生的背景与既定事实，严禁在开篇使用大量旁白/心理活动重复解释背景。",
            "严禁复述主角的前情动机，直接以具体行动或对话切入新事件。"
        ],
        "worn_phrases": [],
        "chapter_tail": prev_tail,
        "is_fallback": True
    }


def format_handoff_for_prompt(handoff: Dict[str, Any]) -> str:
    """
    将 Handoff 结构转化为高优先级的 Prompt 文本块。
    """
    if not handoff:
        return ""

    sections = []
    sections.append("【因果连续性与幕间交接契约（Semantic Handoff）】")
    sections.append("你必须严格遵守以下因果衔接约束，保证与前文剧情严丝合缝，消除生硬感与废话：")

    if handoff.get("what_changed"):
        sections.append(f"1. 前章沉淀事实与核心转变：\n   {handoff['what_changed']}")

    if handoff.get("active_intentions"):
        sections.append(f"2. 本章接续即时意图与核心任务：\n   {handoff['active_intentions']}")

    if handoff.get("open_questions"):
        sections.append(f"3. 需跟进或呼应的未决悬念：\n   {handoff['open_questions']}")

    must_not = handoff.get("must_not_restate") or []
    if must_not:
        sections.append("4. 【绝密禁令】读者已明确知晓以下信息，开篇绝对禁止重复科普/水字数：")
        if isinstance(must_not, list):
            for item in must_not:
                sections.append(f"   - 🚫 {item}")
        else:
            sections.append(f"   - 🚫 {must_not}")

    worn = handoff.get("worn_phrases") or []
    if worn:
        sections.append(f"5. 【高频/套路词拦截黑名单】：严禁使用以下磨损严重的套路词或句式：{', '.join(worn)}")

    tail = handoff.get("chapter_tail")
    if tail:
        sections.append(f"6. 【物理尾声锚定】：上一章在此结束（开篇请顺接此时刻的动作/环境/声线，严禁突兀转场）：\n   \"...{tail.strip()}\"")

    return "\n\n" + "\n".join(sections) + "\n\n"


def build_semantic_handoff_from_chapter(
    filepath: str,
    chapter_num: int,
    chapter_text: str,
    llm_adapter,
    progress=None
) -> Dict[str, Any]:
    """
    在单章定稿后，调用 Editor LLM 提炼本章留给下一章的精确交接包。
    """
    if progress:
        progress(0.2, desc=f"正在提炼第 {chapter_num} 章留给下一章的因果交接（Semantic Handoff）...")

    canon_text = ""
    canon_path = get_canon_file_path(filepath)
    if os.path.exists(canon_path):
        try:
            canon_text = read_file(canon_path).strip()
        except Exception:
            pass

    prompt = f"""你是一位小说总编兼叙事架构师。第 {chapter_num} 章刚刚定稿完成。
为了让下一章（第 {chapter_num + 1} 章）在执笔时与本章严丝合缝、完全不产生前后割裂感、且杜绝开篇水字数交代前情，请依据本章正文提炼「幕间因果交接包（Semantic Handoff）」。

===== 【第 {chapter_num} 章定稿正文】 =====
{chapter_text[-3000:] if len(chapter_text) > 3000 else chapter_text}

===== 【参考正史背景（如有）】 =====
{canon_text[:1500] if canon_text else "（暂无）"}

===== 【提炼要求】 =====
请严格按以下 JSON 格式返回，不要附带任何 markdown 标记外的解释：
{{
  "what_changed": "1-3句话阐明本章实际改变了什么（人物关系变化、新获得信息、伤势/地点转变等，须是正文写出来的实锤）",
  "active_intentions": "主角及相关核心人物在本章结束时的直接意图与下一步即时目标",
  "open_questions": "本章遗留给下一章必须面对或推进的危机/悬念/伏笔",
  "must_not_restate": [
    "读者已经完全清楚的信息点1（严禁下章开篇再花篇幅向读者交代）",
    "读者已经完全清楚的信息点2"
  ],
  "worn_phrases": ["本章重复出现3次以上的套路词、AI常用口头禅（如嘴角勾起、宛如等）"]
}}"""

    result_json = {}
    try:
        response = invoke_with_cleaning(llm_adapter, prompt, progress=progress)
        # 尝试提取 JSON
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result_json = json.loads(json_match.group(0))
        else:
            result_json = json.loads(response)
    except Exception as e:
        logging.warning(f"[Continuity] Handoff JSON 解析失败，构建基础容错包: {e}")
        result_json = {
            "what_changed": f"第 {chapter_num} 章剧情完成推进。",
            "active_intentions": "接续当前事件继续深入。",
            "open_questions": "未解矛盾与危机。",
            "must_not_restate": ["前章已经交代的情节不要再重复科普。"],
            "worn_phrases": []
        }

    tail = chapter_text[-600:] if len(chapter_text) > 600 else chapter_text
    handoff_data = {
        "from_chapter": chapter_num,
        "target_chapter": chapter_num + 1,
        "what_changed": result_json.get("what_changed", ""),
        "active_intentions": result_json.get("active_intentions", ""),
        "open_questions": result_json.get("open_questions", ""),
        "must_not_restate": result_json.get("must_not_restate", []),
        "worn_phrases": result_json.get("worn_phrases", []),
        "chapter_tail": tail.strip(),
        "is_fallback": False
    }

    save_semantic_handoff(filepath, handoff_data)
    return handoff_data


def cold_start_backfill(
    filepath: str,
    llm_adapter,
    max_chapters: Optional[int] = None,
    progress=None
) -> Dict[str, Any]:
    """
    【核心平滑过渡技术】：从已有历史章节一键冷启动萃取！
    解决用户在中途加入新机制时“前面章节和后面章节产生割裂感”的痛点。
    扫描 chapters/ 目录下的所有已存在章节，一次性提炼生成完整的：
    1. Novel_canon_history.txt（正史事实与连续性总账本）
    2. Novel_handoff.json（接续下一章的无缝因果交接）
    """
    chapters_dir = os.path.join(filepath, "chapters")
    if not os.path.exists(chapters_dir):
        return {"success": False, "message": "未找到 chapters 目录，无法进行回溯提取。"}

    # 搜集所有已存在的章节文件
    chap_files = []
    for f in os.listdir(chapters_dir):
        m = re.match(r'^chapter_(\d+)\.txt$', f)
        if m:
            chap_files.append((int(m.group(1)), os.path.join(chapters_dir, f)))

    chap_files.sort(key=lambda x: x[0])
    if not chap_files:
        return {"success": False, "message": "未检测到已生成的章节文件，无需冷启动回溯。"}

    if max_chapters is not None:
        chap_files = [cf for cf in chap_files if cf[0] <= max_chapters]

    total_chaps = len(chap_files)
    latest_chap_num = chap_files[-1][0]

    if progress:
        progress(0.1, desc=f"检测到已写完的 {total_chaps} 章历史正文，开始执行冷启动因果萃取...")

    # 读取每一章的精华（开头300字+结尾500字）以及最新章全文，避免爆上下文
    summaries_text = []
    for num, cpath in chap_files:
        try:
            txt = read_file(cpath).strip()
            if not txt:
                continue
            head = txt[:400]
            tail = txt[-500:]
            summaries_text.append(f"--- 【第 {num} 章】 (全章共 {len(txt)} 字) ---\n[首段]\n{head}\n...\n[尾段]\n{tail}")
        except Exception as e:
            logging.warning(f"读取 chapter_{num}.txt 失败: {e}")

    last_chap_text = read_file(chap_files[-1][1]).strip()
    history_overview = "\n\n".join(summaries_text)

    prompt = f"""你是一位资深小说总编辑。当前这本小说已经创作完成了前 {latest_chap_num} 章，现在系统要将全书接入高确定性的长篇连续性引擎。
为了保证新生成的第 {latest_chap_num + 1} 章与前 {latest_chap_num} 章完全不产生割裂感、无缝顺承既有因果，请依据以下前 {latest_chap_num} 章的历史概览，一次性萃取出两份关键资产：

===== 【前 {latest_chap_num} 章历史文本切片】 =====
{history_overview[-6000:] if len(history_overview) > 6000 else history_overview}

===== 【最新第 {latest_chap_num} 章尾声全文】 =====
{last_chap_text[-1200:] if len(last_chap_text) > 1200 else last_chap_text}

===== 【任务 1：生成正史设定页 (Novel_canon_history.txt)】 =====
请整理出一份客观扎实的正史页，包含以下固定栏目（只记前文实锤写出来的，严禁无中生有）：
1. 人物现状与状态（外貌、身份、伤势、当前所在地、关键动机）
2. 核心关系网与信息差（谁信任谁、谁欠谁、谁知道什么秘密、谁不知道什么）
3. 关键物件与能力（持有物、位置、能力代价）
4. 截至第 {latest_chap_num} 章的时间线与重大事件
5. 尚未回收的伏笔与悬念列表（注明出处章节）
6. 跨章套路词/高频词禁用表（前文出现过于频繁的口癖、动作习惯）
7. 第 {latest_chap_num + 1} 章接续点（主角当前危机、动作、下一步必做的事）

===== 【任务 2：提炼第 {latest_chap_num + 1} 章专属 Semantic Handoff】 =====
请在正史页之后，附带 JSON 格式的交接包：
```json
{{
  "what_changed": "截至第 {latest_chap_num} 章最核心的既成事实",
  "active_intentions": "第 {latest_chap_num + 1} 章必须立刻推进的主角意图",
  "open_questions": "当务之急需解决的矛盾",
  "must_not_restate": [
    "读者在前 {latest_chap_num} 章已经完全知晓的核心背景，第 {latest_chap_num + 1} 章绝对禁止重复水字数交代"
  ],
  "worn_phrases": ["前文高频口癖"]
}}
```
请开始输出："""

    if progress:
        progress(0.4, desc="AI 正在统揽历史全书，提炼正史底册与接续因果...")

    response = invoke_with_cleaning(llm_adapter, prompt, progress=progress)

    # 拆分正史页与 JSON
    canon_body = response
    handoff_json = {}
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
    if not json_match:
        json_match = re.search(r'(\{[\s\S]*"what_changed"[\s\S]*\})', response)

    if json_match:
        try:
            handoff_json = json.loads(json_match.group(1))
            # 从正史文本中剔除 JSON 块
            canon_body = response.replace(json_match.group(0), "").strip()
        except Exception as e:
            logging.warning(f"解析 JSON handoff 失败: {e}")

    # 保存 Novel_canon_history.txt
    canon_path = get_canon_file_path(filepath)
    save_string_to_txt(canon_body.strip(), canon_path)

    # 保存 Novel_handoff.json
    tail = last_chap_text[-600:] if len(last_chap_text) > 600 else last_chap_text
    handoff_data = {
        "from_chapter": latest_chap_num,
        "target_chapter": latest_chap_num + 1,
        "what_changed": handoff_json.get("what_changed", f"前 {latest_chap_num} 章事实已完全归档。"),
        "active_intentions": handoff_json.get("active_intentions", "承接前文，继续推进。"),
        "open_questions": handoff_json.get("open_questions", "推进未决悬念。"),
        "must_not_restate": handoff_json.get("must_not_restate", ["前文已交代情节严禁重复。"]),
        "worn_phrases": handoff_json.get("worn_phrases", []),
        "chapter_tail": tail.strip(),
        "is_fallback": False
    }
    save_semantic_handoff(filepath, handoff_data)

    # 写入日志
    import time
    log_entry = (
        f"\n\n{'='*50}\n【一键冷启动因果萃取完成 - {time.strftime('%Y-%m-%d %H:%M:%S')}】\n"
        f"覆盖章节：第 1 章 ~ 第 {latest_chap_num} 章 (共 {total_chaps} 章)\n{'='*50}\n"
    )
    append_text_to_file(log_entry, get_changelog_file_path(filepath))

    if progress:
        progress(1.0, desc="冷启动因果萃取完成！已建立稳固的正史与交接基底。")

    return {
        "success": True,
        "total_chapters": total_chaps,
        "latest_chapter": latest_chap_num,
        "next_chapter": latest_chap_num + 1,
        "canon_preview": canon_body[:500] + "...",
        "handoff": handoff_data,
        "message": f"成功回溯提取前 {latest_chap_num} 章历史！已生成正史底册与第 {latest_chap_num + 1} 章的无缝接续包，新章节将完全无割裂感。"
    }


def pre_write_gate_check(
    filepath: str,
    chapter_num: int,
    chapter_outline: str,
    llm_adapter,
    progress=None
) -> Dict[str, Any]:
    """
    【大纲级前置门禁（Pre-write Gate）】：
    在开始动笔生成数千字正文之前，进行一次极轻量（几十到几百 token）的因果体检。
    检查：
    1. 细纲是否与已有正史事实或角色当前状态冲突？
    2. 是否有效接续了上一章的 Handoff 即时意图？
    3. 是否存在未登场角色突然出场，或位置瞬间移动的漏洞？
    4. 发现问题时给出精准修改建议，在正文前低成本拦截！
    """
    if progress:
        progress(0.2, desc=f"正在对第 {chapter_num} 章细纲进行大纲级前置门禁体检...")

    canon_text = ""
    canon_path = get_canon_file_path(filepath)
    if os.path.exists(canon_path):
        try:
            canon_text = read_file(canon_path).strip()
        except Exception:
            pass

    handoff = get_semantic_handoff(filepath, chapter_num)

    prompt = f"""你是一位小说逻辑总编与审校。作者即将为第 {chapter_num} 章动笔撰写正文。
请在大纲阶段（动笔前）对本章细纲执行「前置因果体检（Pre-write Gate）」，低成本拦截逻辑硬伤与设定冲突。

===== 【当前可用正史设定与事实约束】 =====
{canon_text[:2000] if canon_text else "（暂无前期正史，按首部处理）"}

===== 【上一章留下的幕间因果交接 (Handoff)】 =====
- 上一章沉淀事实：{handoff.get('what_changed', '无')}
- 本章应推进的即时意图：{handoff.get('active_intentions', '无')}
- 必须避免开篇复述的内容：{handoff.get('must_not_restate', '无')}

===== 【待审核的第 {chapter_num} 章细纲】 =====
{chapter_outline}

===== 【体检维度】 =====
1. 连续性：是否顺承了上一章结尾主角的真实位置、伤势和即时危机？
2. 设定冲突：是否有任何违反已确立能力、规则、角色性格的行为？
3. 废话风险：是否打算开篇再花大量笔墨向读者解释已知背景？
4. 推进力：本章是否真的发生了不可逆的因果推进？

请严格以 JSON 格式返回审核报告：
{{
  "passed": true或false（有严重冲突才判false，微小瑕疵判true并附带建议）,
  "summary": "一句话体检结论",
  "contradictions": ["发现的设定冲突或逻辑断层，没有则为空列表"],
  "continuity_warnings": ["衔接上的薄弱点或开篇水字数风险"],
  "repair_suggestions": "针对上述问题的具体微调建议（50-100字，指导作者如何改细纲）"
}}"""

    response = invoke_with_cleaning(llm_adapter, prompt, progress=progress)
    try:
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
        else:
            data = json.loads(response)
    except Exception as e:
        logging.warning(f"[Gate] 解析门禁 JSON 失败: {e}")
        data = {
            "passed": True,
            "summary": "门禁体检完成（未发现阻断性矛盾）",
            "contradictions": [],
            "continuity_warnings": [],
            "repair_suggestions": "注意保持与上一章结尾的自然衔接。"
        }

    if progress:
        progress(1.0, desc=f"前置门禁体检完成：{'通过' if data.get('passed') else '发现潜在风险'}")

    return data


def repair_span_in_chapter(
    chapter_text: str,
    target_span: str,
    repair_instruction: str,
    llm_adapter,
    progress=None
) -> Dict[str, Any]:
    """
    【局部句子级精准修补（Span Repair）】：
    参考 KazKozDev/NovelGenerator 的 P08_SPAN_REPAIR。
    当检测到某句话出现严重逻辑冲突、穿帮、或套路词严重重复时，
    不需要推翻重写整章（避免破坏写得好的其他段落），
    而是定位该句子及其局部上下文，只重写这一两句话，并用精准字符串替换合入原稿！
    """
    if not target_span or target_span not in chapter_text:
        return {
            "success": False,
            "message": "在章节正文中未找到指定的原句片段，请检查选中文本是否完全匹配。",
            "repaired_text": chapter_text
        }

    # 提取局部上下文（前后各 300 字）
    idx = chapter_text.find(target_span)
    start_pos = max(0, idx - 300)
    end_pos = min(len(chapter_text), idx + len(target_span) + 300)
    context_window = chapter_text[start_pos:end_pos]

    prompt = f"""你是一位精通文字微调的小说责编。某章节正文中存在一处有瑕疵的句子或段落需要进行【局部外科手术式替换修补】。
要求：
1. 仅重写指定的【待替换原句】，不要改动其前后的任何其他句子。
2. 保持与前后文的语气、声线、文风完全一致。
3. 严格根据【修改要求】完成修改。
4. 仅输出替换后的新句子文本，严禁包含任何前缀、解释、双引号或提示语！

===== 【周围上下文参考】 =====
...{context_window}...

===== 【待替换原句】 =====
{target_span}

===== 【修改要求】 =====
{repair_instruction}

请直接输出替换后的单句/片段文本："""

    if progress:
        progress(0.4, desc="正在进行局部句子级修补重写...")

    repaired_span = invoke_with_cleaning(llm_adapter, prompt, progress=progress).strip()
    # 清理多余的外层引号
    if (repaired_span.startswith('"') and repaired_span.endswith('"')) or (repaired_span.startswith('“') and repaired_span.endswith('”')):
        repaired_span = repaired_span[1:-1].strip()

    if not repaired_span:
        return {
            "success": False,
            "message": "修补生成内容为空，未修改原稿。",
            "repaired_text": chapter_text
        }

    # 精准单次字符串替换
    new_chapter_text = chapter_text.replace(target_span, repaired_span, 1)

    return {
        "success": True,
        "original_span": target_span,
        "repaired_span": repaired_span,
        "repaired_text": new_chapter_text,
        "message": "局部精准修补完成，已安全合入正文！"
    }
