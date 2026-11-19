# -*- coding: utf-8 -*-
"""
novel_generator/pipeline_rules.py
小说流水线底层规则（中文生成 → 润色 → 英文翻译 → 质检）
依据 Claude 总结前七章经验提炼的全链路底层铁律与确定性脚本检测器。
"""

import os
import re
import difflib
from typing import Dict, List, Any, Tuple, Optional

# ==============================================================================
# 0. 原始规范文档（权威规则真值源）
# ==============================================================================
PIPELINE_RULES_RAW = """# 小说流水线底层规则（中文生成 → 润色 → 英文翻译 → 质检）

## 0. 通用输入（每次调用必带）
- 正史页：人物、关系、物件（持有人/位置/状态）、地点、能力、时间线、信息差、伏笔、接续点。
- 固定写法表：专有名词、颜色、药名、地名，一词一译。
- 跨章禁用表：只保留最近三章的高频词。
- 上一章结尾摘要（≤200字）。
- 已定稿章节不整章重写；修改只针对指定段落。

## 1. 中文生成
1. 按场景生成，每场景800–1500字；续写必须从上文最后一个词接着写，不得重写已有内容。
2. 每章只推进一个主冲突，只引入一个新设定，新设定后文必须引用一次。
3. 重大揭示（身份、血缘、真相）三章内最多一个；揭示之后下一章必须出现新的未解决冲突。
4. 角色只知道自己亲眼看到、听到、被告知的事；昏迷或不在场期间发生的事不得出现在其认知里。
5. 每个场景开头标明时间、地点；昼夜、天气、季节不得矛盾。
6. 主角在最重打击处写一句直接感受 + 一次生理反应，再压下去；允许一次判断失误；关键冒险决定前写一句权衡。
7. 角色说话必须可区分；每个主要角色一个固定小动作，每章≤3次。
8. 禁止作者替读者下结论（"他早就…""她从未…"）；识破、认人场景用"一个触发物 + 一个推断"。
9. 章末钩子在 悬念/反转/新人物/信息差/倒计时 中轮换，连续两章不得同类。
10. 章标题不用 aura / absolute / supreme 等大词。

## 2. 中文润色（逐条替换，输出附各项剩余次数）
1.【脚本】跨章禁用词，每词全章≤2次：pale, iron, dust, ground, dared, northern, ancient/archaic/ancestral, dormant, heavy, surged, blood welled/trickled, cold sweat, bit down, dug fingertips。
2.【脚本】否定排比（No X. No Y. / neither…nor / did not…and did not / rather than…or）全章合计≤2，按功能识别，不只匹配字面。
3. 同一比喻域（账本、法务、金属、冰）全章≤3处，且只归属固定角色。
4. 每场景精确数字≤2个；禁用医学术语（capillary, patella, respiratory 等）。
5. 同类描写（声音平静/冷/平稳）全章只留一处。
6.【脚本】连续3句同结构、分词短语收尾每段≤1次、remained 全章≤3。
7. 修仙词外溢全部替换：vitality, life force, spirit, pressure point, radiance, mortal, energy, meridians, dantian, qi, cultivation, realm。
8. 对照正史页和固定写法表核对物件位置、伤势、颜色、称谓、知情范围。
9.【脚本】连续200字以上相似内容视为重复，删除后一处。

## 3. 英文翻译（只管表达，不补内容）
1. 段落与原文一一对应，不增、不删、不重复。
2. 不逐字直译中文意象，译成英文里自然的说法。
3. 关键身份词不得泛化（Lycan King 不得写成 presence/power/energy）。
4. 禁用现代或抽象词：catalyst, processing, operational, energy grid。
5. 对话标签以 said 为主；hissed/snarled/growled 全章合计≤2。
6. 名词一词一译，严格按固定写法表。
7. 保持台词锋利度与原文一致，不得磨平。

## 4. 独立质检（单独调用，只出报告，不改写）
1. 对照原文与译文：段落是否对应，有无重复、遗漏、截断。
2. 对照正史页：物件、状态、知情范围、称谓是否冲突。
3.【脚本】统计第2节各项次数，列出超标项和所在段落。
4. 检查关键信息是否被泛化或丢失。
5. 结论：通过 / 需重写（指出段落）；重写最多两轮。

## 5. 正史页更新（每章定稿后，单独调用）
1. 只记正文明确写出的事实，每条标注章节。
2. 与旧事实冲突时不覆盖，列入"待确认冲突"，建议统一方式不得要求改已发布正文。
3. 作者确认后才合并；旧事实移入"已作废"。
4. 同时更新物件/人物状态账本、跨章禁用表（保留最近三章）、章末钩子记录、下一章接续点。
5. 整页≤1500字，早期章节压缩成摘要。

## 6. 成人向内容模块（可开关）
1. 不写性行为过程和身体细节，用转场、能量描写、事后状态呈现。
2. 失控或强迫场面必须有：施加方一次短暂的认出或克制；女主一个主动决定；事后一段真实的情绪反应。
3. 不使用 taking / violent / punish 这类把暴力浪漫化的措辞。

## 7. 固定写法表（示例，随书增补）
Ella Clare｜Blackwood Forest｜totem altar｜Sun Sand｜frost-wormwood（药瓶原料）/ frost-grass（药袋粉）｜ointment｜amber irises, dark gold rings｜Silver Moon Perception｜Silver Poisoning｜wolf-soul｜Golden Decree（法令）/ Golden Token Exam（考试）
"""

# ==============================================================================
# 1. 默认固定写法表与专有名词映射（Section 7）
# ==============================================================================
DEFAULT_FIXED_TERMS: Dict[str, str] = {
    "Ella Clare": "艾拉·克莱尔",
    "Damian": "达米安",
    "Alexander": "亚历山大",
    "Leo": "里奥",
    "Blackwood Forest": "黑木森林（全书唯一森林名）",
    "totem altar": "图腾祭坛",
    "Sun Sand": "日阳沙",
    "frost-wormwood": "霜苦艾（药瓶原料）",
    "frost-grass": "霜草（药袋粉）",
    "ointment": "药膏",
    "amber irises, dark gold rings": "琥珀色虹膜，暗金环",
    "Silver Moon Perception": "银月感知",
    "Silver Poisoning": "银毒",
    "wolf-soul": "兽魂（狼魂）",
    "Golden Decree": "金令（法令）",
    "Golden Token Exam": "金令大考（考试）",
    "Lycan King": "狼皇（最高统治者，严禁泛化为 presence/power/energy）",
    "Pack": "部族/狼群",
    "Alpha": "首领/狼王",
    "Luna": "首领伴侣/狼后",
    "High Council": "元老院",
    "Pack Elders": "部族长老",
    "Chief Elder": "大长老",
    "enforcer": "执法者",
    "omega": "欧米伽/末位狼",
    "Fated Mate": "命定伴侣",
    "Mate Bond": "伴侣契约",
    "Blood Oath": "血誓",
    "betrothal": "婚约",
    "White Stone Capital": "白石都城",
    "Northern Iron Gate": "北铁门",
    "Silver Moon Altar": "银月祭坛",
}

# 跨章禁用高频词（Section 2.1，每词全章≤2次）
FORBIDDEN_SLIDING_WORDS_EN = [
    "pale", "iron", "dust", "ground", "dared", "northern",
    "ancient", "archaic", "ancestral", "dormant", "heavy",
    "surged", "blood welled", "blood trickled", "cold sweat",
    "bit down", "dug fingertips"
]

FORBIDDEN_SLIDING_WORDS_ZH = [
    "苍白", "铁箍", "灰尘", "地面", "竟敢", "北境",
    "古老", "远古", "祖先", "蛰伏", "沉重",
    "翻涌", "鲜血涌出", "冷汗", "咬紧牙", "指甲掐入"
]

# 修仙外溢词（Section 2.7，严禁出现，出现必须全部替换）
XIANXIA_BANNED_WORDS_EN = [
    "vitality", "life force", "spirit", "pressure point", "radiance",
    "mortal", "energy", "meridians", "dantian", "qi", "cultivation", "realm"
]

XIANXIA_BANNED_WORDS_ZH = [
    "经脉", "丹田", "灵力", "真气", "境界", "修炼", "元气",
    "穴位", "凡人", "仙", "道心", "元神", "金丹", "筑基"
]

# 英文现代/抽象禁用词（Section 3.4）
MODERN_ABSTRACT_BANNED_WORDS_EN = [
    "catalyst", "processing", "operational", "energy grid"
]

# 医学专业禁用词（Section 2.4）
MEDICAL_TERMS = [
    "capillary", "patella", "respiratory", "synapse", "hemoglobin",
    "毛细血管", "髌骨", "呼吸道", "突触", "血红蛋白", "神经递质"
]

# 章标题禁用大词（Section 1.10）
TITLE_BANNED_WORDS = [
    "aura", "absolute", "supreme", "ultimate", "omnipotent",
    "至尊", "绝对", "无敌", "主宰", "威压"
]

# ==============================================================================
# 2. 确定性脚本分析器（Deterministic Script Analyzers）
# ==============================================================================

class DeterministicRuleChecker:
    """按规则 2、3、4 运行的纯脚本确定性分析器"""

    @staticmethod
    def count_word_occurrences(text: str, word: str, is_english: bool = False) -> int:
        if not text:
            return 0
        if is_english:
            pattern = r'\b' + re.escape(word) + r'\b'
            return len(re.findall(pattern, text, re.IGNORECASE))
        else:
            return text.count(word)

    @classmethod
    def check_sliding_forbidden_words(cls, text_zh: str = "", text_en: str = "") -> Dict[str, Any]:
        """
        规则 2.1【脚本】：跨章禁用词，每词全章≤2次。输出各项命中次数与剩余额度。
        """
        results = {}
        # 英文检测
        if text_en:
            for word in FORBIDDEN_SLIDING_WORDS_EN:
                cnt = cls.count_word_occurrences(text_en, word, is_english=True)
                results[f"EN: {word}"] = {
                    "count": cnt,
                    "limit": 2,
                    "remaining": max(0, 2 - cnt),
                    "exceeded": cnt > 2,
                }
        # 中文检测
        if text_zh:
            for word in FORBIDDEN_SLIDING_WORDS_ZH:
                cnt = cls.count_word_occurrences(text_zh, word, is_english=False)
                results[f"ZH: {word}"] = {
                    "count": cnt,
                    "limit": 2,
                    "remaining": max(0, 2 - cnt),
                    "exceeded": cnt > 2,
                }
        return results

    @classmethod
    def check_negative_parallelism(cls, text_zh: str = "", text_en: str = "") -> Dict[str, Any]:
        """
        规则 2.2【脚本】：否定排比全章合计≤2，按功能识别。
        """
        matches_en = []
        if text_en:
            patterns_en = [
                r'\bno\s+[^.?!]+[.?!]\s*no\s+[^.?!]+',  # No X. No Y.
                r'\bneither\b[^\n,;]+?\bnor\b',          # neither...nor
                r'\bdid\s+not\b[^\n,;]+?\band\s+did\s+not\b', # did not...and did not
                r'\brather\s+than\b[^\n,;]+?\bor\b',    # rather than...or
            ]
            for p in patterns_en:
                for m in re.finditer(p, text_en, re.IGNORECASE):
                    matches_en.append(m.group(0).strip())

        matches_zh = []
        if text_zh:
            patterns_zh = [
                r'不是[^\n，。]+?也不是[^\n，。]+',
                r'没有[^\n，。]+?也没有[^\n，。]+',
                r'既不[^\n，。]+?也不[^\n，。]+',
                r'而非[^\n，。]+?或者[^\n，。]+',
            ]
            for p in patterns_zh:
                for m in re.finditer(p, text_zh):
                    matches_zh.append(m.group(0).strip())

        total_cnt = len(matches_en) + len(matches_zh)
        return {
            "total_count": total_cnt,
            "limit": 2,
            "exceeded": total_cnt > 2,
            "remaining": max(0, 2 - total_cnt),
            "matches_en": matches_en,
            "matches_zh": matches_zh,
        }

    @classmethod
    def check_xianxia_leakage(cls, text_zh: str = "", text_en: str = "") -> Dict[str, Any]:
        """
        规则 2.7：修仙词外溢全部替换（0容忍）。
        """
        hits = []
        if text_en:
            for w in XIANXIA_BANNED_WORDS_EN:
                cnt = cls.count_word_occurrences(text_en, w, is_english=True)
                if cnt > 0:
                    hits.append({"word": w, "lang": "en", "count": cnt})
        if text_zh:
            for w in XIANXIA_BANNED_WORDS_ZH:
                cnt = cls.count_word_occurrences(text_zh, w, is_english=False)
                if cnt > 0:
                    hits.append({"word": w, "lang": "zh", "count": cnt})
        return {
            "has_leakage": len(hits) > 0,
            "hits": hits,
            "message": "检测到修仙词外溢，必须替换为兽魂/血脉/体力等西方狼人术语" if hits else "无修仙词外溢"
        }

    @classmethod
    def check_modern_abstract_words(cls, text_en: str) -> Dict[str, Any]:
        """
        规则 3.4：禁用现代或抽象词：catalyst, processing, operational, energy grid
        """
        hits = []
        if text_en:
            for w in MODERN_ABSTRACT_BANNED_WORDS_EN:
                cnt = cls.count_word_occurrences(text_en, w, is_english=True)
                if cnt > 0:
                    hits.append({"word": w, "count": cnt})
        return {
            "has_modern_words": len(hits) > 0,
            "hits": hits
        }

    @classmethod
    def check_dialog_tags(cls, text_en: str) -> Dict[str, Any]:
        """
        规则 3.5：对话标签以 said 为主；hissed/snarled/growled 全章合计≤2。
        """
        if not text_en:
            return {"said_count": 0, "beast_tags_count": 0, "exceeded": False}

        said_cnt = cls.count_word_occurrences(text_en, "said", is_english=True)
        hissed_cnt = cls.count_word_occurrences(text_en, "hissed", is_english=True)
        snarled_cnt = cls.count_word_occurrences(text_en, "snarled", is_english=True)
        growled_cnt = cls.count_word_occurrences(text_en, "growled", is_english=True)
        beast_total = hissed_cnt + snarled_cnt + growled_cnt

        return {
            "said_count": said_cnt,
            "hissed_count": hissed_cnt,
            "snarled_count": snarled_cnt,
            "growled_count": growled_cnt,
            "beast_tags_count": beast_total,
            "limit": 2,
            "exceeded": beast_total > 2,
            "remaining": max(0, 2 - beast_total)
        }

    @classmethod
    def check_medical_terms(cls, text_zh: str = "", text_en: str = "") -> Dict[str, Any]:
        """
        规则 2.4：禁用医学术语（capillary, patella, respiratory 等）
        """
        hits = []
        combined = (text_zh or "") + " " + (text_en or "")
        for t in MEDICAL_TERMS:
            if re.search(r'\b' + re.escape(t) + r'\b' if re.match(r'^[a-zA-Z]+$', t) else re.escape(t), combined, re.IGNORECASE):
                hits.append(t)
        return {"has_medical_terms": len(hits) > 0, "hits": hits}

    @classmethod
    def check_repetitive_spans(cls, text: str, min_len: int = 150) -> List[Dict[str, Any]]:
        """
        规则 2.9【脚本】：连续 200 字（此处阈值设为 150-200）以上相似内容视为重复，删除后一处。
        """
        if not text or len(text) < min_len * 2:
            return []

        # 按自然段切分
        paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) >= 50]
        duplicates = []

        for i in range(len(paragraphs)):
            for j in range(i + 1, len(paragraphs)):
                p1 = paragraphs[i]
                p2 = paragraphs[j]
                if len(p1) >= min_len and len(p2) >= min_len:
                    ratio = difflib.SequenceMatcher(None, p1[:min_len], p2[:min_len]).ratio()
                    if ratio > 0.85:
                        duplicates.append({
                            "para_index_1": i + 1,
                            "para_index_2": j + 1,
                            "similarity": round(ratio, 2),
                            "sample": p2[:80] + "..."
                        })
        return duplicates

    @classmethod
    def run_full_script_audit(cls, text_zh: str = "", text_en: str = "") -> Dict[str, Any]:
        """
        执行全套底层规则脚本级检测，输出综合质检报告。
        """
        sliding = cls.check_sliding_forbidden_words(text_zh, text_en)
        neg_parallel = cls.check_negative_parallelism(text_zh, text_en)
        xianxia = cls.check_xianxia_leakage(text_zh, text_en)
        modern = cls.check_modern_abstract_words(text_en)
        tags = cls.check_dialog_tags(text_en)
        medical = cls.check_medical_terms(text_zh, text_en)
        dup_zh = cls.check_repetitive_spans(text_zh) if text_zh else []

        exceeded_sliding = [k for k, v in sliding.items() if v["exceeded"]]

        # 判定是否通过脚本硬指标
        is_clean = (
            len(exceeded_sliding) == 0 and
            not neg_parallel["exceeded"] and
            not xianxia["has_leakage"] and
            not modern["has_modern_words"] and
            not tags["exceeded"] and
            not medical["has_medical_terms"] and
            len(dup_zh) == 0
        )

        return {
            "passed": is_clean,
            "sliding_forbidden": sliding,
            "exceeded_sliding_words": exceeded_sliding,
            "negative_parallelism": neg_parallel,
            "xianxia_leakage": xianxia,
            "modern_words": modern,
            "dialog_tags": tags,
            "medical_terms": medical,
            "repetitive_spans": dup_zh,
        }

    @classmethod
    def format_script_report_as_text(cls, report: Dict[str, Any]) -> str:
        """将脚本检测结果格式化为清晰的可读文本，嵌入修改清单或质检报告"""
        lines = ["【底层规则确定性脚本检测结果】:"]
        if report["passed"]:
            lines.append("✅ 脚本硬指标全部达标（无超标禁用词、无修仙外溢、否定排比合规、标签规范）")
        else:
            lines.append("⚠️ 检测到以下硬指标未达标项（需重点核查或修正）：")

        # 跨章禁用词超标项
        if report["exceeded_sliding_words"]:
            lines.append(f"- 🚫 跨章词超标（上限≤2次）: {', '.join(report['exceeded_sliding_words'])}")

        # 否定排比
        np = report["negative_parallelism"]
        lines.append(f"- 否定排比全章出现: {np['total_count']} 次 (上限≤2次, 剩余配额: {np['remaining']})")

        # 修仙词
        xx = report["xianxia_leakage"]
        if xx["has_leakage"]:
            hits_str = ", ".join([f"{h['word']}({h['count']}次)" for h in xx["hits"]])
            lines.append(f"- ❌ 严禁修仙词外溢: {hits_str} -> 必须替换为西方兽魂/血脉/创伤")

        # 现代词
        mw = report["modern_words"]
        if mw["has_modern_words"]:
            hits_str = ", ".join([f"{h['word']}({h['count']}次)" for h in mw["hits"]])
            lines.append(f"- ❌ 英文禁用现代/抽象词: {hits_str}")

        # 对话标签
        dt = report["dialog_tags"]
        lines.append(f"- 对话标签分布: said={dt['said_count']}次, hissed/snarled/growled={dt['beast_tags_count']}次 (上限≤2次, 剩余: {dt['remaining']})")

        # 重复段落
        dups = report["repetitive_spans"]
        if dups:
            lines.append(f"- ⚠️ 检测到 {len(dups)} 处长篇相似重复段落 (已定位第 {[d['para_index_2'] for d in dups]} 段)")

        return "\n".join(lines)


# ==============================================================================
# 3. 各阶段专用 Prompt 指令装配器
# ==============================================================================

def get_zh_chapter_generation_rules_prompt() -> str:
    """纯中文出稿流水线：中文分场景起草核心规范（不包含任何出海/译制/特定题材词表约束）"""
    return """
【中文创作核心规范】（必须严格遵守）：
1.【分场景篇幅】：每个场景篇幅紧凑扎实，紧贴细纲推进；续写必须从上文最后一个词紧密咬合接续，严禁重写已有内容。
2.【单章推进原则】：每章集中推进一个主冲突或核心事件，严禁注水空转。
3.【信息差与知情视界】：角色只知道自己亲眼看到、亲耳听到、被当面告知的事；昏迷、未在场期间发生的事情绝对不能出现在其认知或心理活动中。
4.【时空锚点清晰】：每个场景开头必须明确体现时间、地点与人物站位；全章昼夜、天气、随身物品不得前后矛盾。
5.【人物情绪与生理细节】：关键冲突处直写主角情绪与真实生理反应，随后紧接反击或抉择；允许角色判断失误一次，避免全程开挂式全知全能。
6.【对白辨识度】：不同角色说话语气、用词习惯必须截然可区分，遮住人名也能认出是谁在说话。
7.【禁止替读者下结论】：用动作、物件和台词矛盾展示信息，严禁作者视角空洞说教。
8.【章末强钩子】：章末最后 150 字必须留在危机爆发、反转、新人物入局或悬念节点，严禁平淡收尾。
"""


def get_chapter_generation_rules_prompt(adult_mode: bool = False) -> str:
    """生成阶段 1 & 2：中文分场景起草的核心规则约束"""
    adult_clause = """
【成人向亲密描写规则（当前启用）】：
1. 不写性行为过程和身体细节，使用转场、能量共鸣描写、事后疲惫/连接状态呈现。
2. 失控或强迫场面必须具备三要素：
   - 施加方一次短暂的认出或克制；
   - 女主一个主动决定；
   - 事后一段真实的情绪反应（痛楚、愤怒或决绝）。
3. 严禁使用 taking / violent / punish 等将暴力浪漫化的措辞。
""" if adult_mode else """
【亲密场景约束】：严禁描写直白生理性行为与露骨细节，遵循全年龄出海出版级标准。
"""

    return f"""
【小说流水线底层规则 · 中文生成十条铁律】（必须严格遵守）：
1.【分场景篇幅】：每个场景篇幅严格控制在 800–1500 字；续写必须从上文最后一个词紧密咬合接续，严禁重写已有内容。
2.【单章推进原则】：每章只推进一个主冲突；每章最多引入一个新设定，且新设定在后文中必须明确被引用一次。
3.【重大揭示限额】：重大揭示（身份、血缘、真相）三章内最多出现一个；揭示发生后，下一章必须立即引出新的未解决冲突。
4.【信息差与知情视界】：角色只知道自己亲眼看到、亲耳听到、被当面告知的事；昏迷、未在场期间发生的事情绝对不能出现在其认知或心理活动中。
5.【时空锚点清晰】：每个场景开头必须明确标注或自然体现时间与地点；全章的昼夜、天气、季节不得出现前后矛盾。
6.【主角心理与生理反应】：主角在遭受最重打击处，必须写一句直接内心感受 + 一次生理反应（如喉头发紧、手指发颤），随后强行压下去；主角允许出现一次判断失误；在关键冒险决定前必须写一句权衡。
7.【台词辨识度与动作特征】：角色说话风格必须截然可区分；每个主要角色设计一个固定小动作（如整理袖口、转动戒指、抚摸狼牙），全章出现不得超过 3 次。
8.【禁止替读者下结论】：严禁作者视角代读者判断（禁止出现"他早就看透""她从未料到"等说教句）；识破、认人场景必须采用"一个具体触发物 + 一个推断"的推导过程。
9.【章末钩子轮换】：章末悬念必须在【悬念 / 反转 / 新人物 / 信息差 / 倒计时】五类中轮换，连续两章不得使用同类钩子。
10.【章节标题规范】：章标题严禁使用 aura / absolute / supreme / 至尊 / 绝对 等空泛大词。
{adult_clause}
"""

def get_polish_rules_prompt() -> str:
    """生成阶段 3：中文润色规则"""
    return """
【小说流水线底层规则 · 中文润色九大铁律】（逐条替换，输出必须附带修改清单与剩余额度）：
1.【跨章禁用词】：控制高频跨章词（pale, iron, dust, ground, dared, northern, ancient, dormant, heavy, surged, blood welled, cold sweat, bit down, 苍白, 铁箍, 灰尘, 地面, 竟敢, 北境, 沉重, 翻涌, 冷汗, 咬牙, 指甲掐入），每词全章不得超过 2 次。
2.【否定排比裁剪】：否定排比（No X. No Y. / 不是A也不是B / 既不...也不...）全章合计不得超过 2 处，多余的合并为简洁肯定句。
3.【比喻域隔离】：同一比喻域（账本、法务、金属、冰霜）全章不得超过 3 处，且只能归属于对应固定角色。
4.【精确数字与医学术语】：每个场景精确数字不得超过 2 个；严禁使用现代医学术语（毛细血管、髌骨、呼吸道等）。
5.【同类描写归一】：同类描写（如"声音平静""目光冰冷"）全章只保留最有力的一处，其余替换为具体动作。
6.【句式节奏】：严禁连续 3 句使用相同结构；段落结尾分词短语每段最多 1 次；"依然/依旧/remained"全章不得超过 3 次。
7.【修仙词外溢全面清除】：彻底替换修仙词（经脉、丹田、灵力、真气、境界、修炼、凡人、元气），一律改写为狼人设定的"兽魂、血脉、创伤、体力"。
8.【正史与固定表核对】：严格对照正史页与固定写法表，核查物件持有人、位置、伤势、颜色、称谓、知情范围。
9.【消除长篇重复】：检查是否存在连续 200 字以上的相似重复描述，若有删除后一处。

【输出格式要求】：
请先输出润色后的完整正文，随后另起一行分割线输出：
【修改清单与配额剩余】
- 跨章词替换处数及剩余可用配额
- 否定排比优化处数及全章剩余
- 修仙词替换明细
- 重复段落清理情况
"""

def get_translation_rules_prompt(fixed_terms_str: str = "") -> str:
    """生成阶段 4：英文翻译规则"""
    terms_block = f"\n【固定写法表（严格一词一译，不得自创同义词）】：\n{fixed_terms_str}\n" if fixed_terms_str else ""
    return f"""
【小说流水线底层规则 · 英文翻译八大铁律】（只管精准表达，绝不擅自增删内容）：
1.【段落一一对应】：英文译文必须与中文原文段落一一严格对应，不增加、不删除、不重复、不截断。
2.【地道自然表达】：严禁逐字直译中文意象与四字成语，必须译成母语级地道自然的欧美流行网文表达。
3.【关键身份词绝不泛化】：核心身份词不得弱化（如 Lycan King 绝对不得写成 vague presence / power / energy）。
4.【禁用现代/抽象词】：严禁使用现代科技或抽象词汇：catalyst, processing, operational, energy grid 等。
5.【对话标签规范】：对话标签以平实自然的 'said' 为主；强情绪词（hissed, snarled, growled）全章合计不得超过 2 次。
6.【名词统一】：专有名词、地点、药草严格按固定写法表一词一译。
7.【保持台词锋利度】：角色的反击、嘲讽与交锋台词必须保持原文的尖锐与张力，不得磨平成温吞白话。
8.【击碎 AI 翻译腔与假深沉修饰（朱雀 AIGC 英文防线）】：
   - 严禁任何形式的英文大模型拟态副句与心理虚饰：
     * 严禁：『as though...』、『as if trying to steady...』、『with a hint of...』、『couldn't help but...』、『seemed to...』、『a testament to...』；
   - 严禁工整对称的书面哲理自言自语（如 "He spoke slowly, as though steadying the words would make the fact immovable"）；
   - 人物独白与对话必须是粗粝、直接、破碎的欧美本土网文口吻（short punchy vernacular sentences, active kinetic verbs, no academic or melodramatic posturing）。
{terms_block}
"""

def get_audit_rules_prompt(fixed_terms_str: str = "", script_report_str: str = "") -> str:
    """生成阶段 5：独立双语质检规则"""
    terms_block = f"\n【固定写法对照表】：\n{fixed_terms_str}\n" if fixed_terms_str else ""
    script_block = f"\n{script_report_str}\n" if script_report_str else ""
    return f"""
【小说流水线底层规则 · 独立双语质检五大铁律】（单独调用，只出审计报告，严禁改写正文）：
1.【段落对应审计】：逐段核对中文与英文，检查是否存在段落错位、遗漏、意外合并或重复。
2.【正史事实与知情范围审计】：核对正史页中记录的角色伤势、持有物件、当前位置、信息差是否在双语中产生冲突。
3.【频次指标审计】：核查跨章禁用词、否定排比（≤2）、修仙外溢词、对话标签（hissed/snarled/growled≤2）。
4.【关键信息与身份保真审计】：检查关键身份词（Lycan King）、核心悬念或交锋台词是否被泛化磨平。
5.【最终裁决结论】：明确给出【通过】或【需重写（并具体指出哪一段落需针对性修改）】。

{script_block}
{terms_block}
"""

def get_canon_update_rules_prompt() -> str:
    """生成阶段 6：正史页更新规则"""
    return """
【小说流水线底层规则 · 正史页更新五大铁律】（每章定稿后单独调用）：
1.【事实精准度】：只记录正文明确写出的既定事实（人物、关系、物件持有/位置/状态、地点、能力、时间线、信息差、伏笔），每条必须标注来源章节（如 [第X章]）。
2.【冲突隔离保护】：若发现本章事实与旧章节事实冲突，绝对不得直接覆盖旧事实！必须单独列入【待确认冲突】，建议协调方案，但严禁要求修改已发布的定稿正文。
3.【作废机制】：仅在作者确认后才可合并修改，被推翻的旧事实移入【已作废档案】。
4.【状态与动态更新】：同时更新物件/人物状态账本、跨章套路禁用表（只保留最近三章的高频词）、本章章末钩子类型记录、下一章关键接续点。
5.【整页篇幅控制】：正史页全页严格控制在 ≤1500 字以内，早期章节事实自动压缩提炼为背景摘要。
"""

# ==============================================================================
# 4. 项目固定词表初始化与读取工具
# ==============================================================================

def get_fixed_terms_file_path(filepath: str) -> str:
    return os.path.join(filepath, "Novel_fixed_terms.txt")

def ensure_fixed_terms_file(filepath: str) -> str:
    """确保项目中存在 Novel_fixed_terms.txt，若无则自动初始化默认词表"""
    p = get_fixed_terms_file_path(filepath)
    if not os.path.exists(p):
        lines = ["# 项目固定写法表（一词一译，随书增补）"]
        for en, zh in DEFAULT_FIXED_TERMS.items():
            lines.append(f"{en} ｜ {zh}")
        content = "\n".join(lines) + "\n"
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass
        return content
    else:
        try:
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""
