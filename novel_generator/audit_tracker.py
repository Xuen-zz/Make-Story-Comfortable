# novel_generator/audit_tracker.py
# -*- coding: utf-8 -*-
"""
章节生成全链路留底与规则迭代归档系统 (Audit Tracker & Rule Iteration Engine)
职责：
1. 留底归档：将每章由 Gemini起草、朱雀初检扫描、Codex(GPT)靶向重构、朱雀复测、英文译制与正史演进的全链路数据精准持久化。
2. 历史回溯：对项目中已生成的旧章节（如 1~13 章）自动提取初稿、润色清单、英文稿并回溯构建审计档案。
3. 规则迭代：自动聚合全书各章的 AI 高频套话病灶、重构策略与质检表现，供全书完结后提炼改善优化规则。
"""

import os
import json
import re
import datetime
from typing import Dict, Any, Optional, List, Tuple


def _ensure_audit_dir(filepath: str) -> str:
    audit_dir = os.path.join(filepath, "audit_trails")
    os.makedirs(audit_dir, exist_ok=True)
    return audit_dir


def record_chapter_audit(
    filepath: str,
    chapter_num: int,
    chapter_title: str = "",
    pipeline_mode: str = "fast_zh",
    llm_draft_engine: str = "gemini-3.8-flash-low",
    reviewer_engine: str = "Codex (GPT-4o/sol)",
    word_number: int = 3000,
    draft_text: str = "",
    polished_text: str = "",
    checklist_text: str = "",
    zhuque_data: Optional[Dict[str, Any]] = None,
    translation_text: str = "",
    audit_report: str = "",
    summary: str = "",
    handoff: Optional[Dict[str, Any]] = None,
    canon_report: str = "",
    elapsed_seconds: float = 0.0,
    zhuque_report_md: str = "",
) -> Tuple[str, str]:
    """
    记录单章生成与审校留底，生成 JSON 与 Markdown 归档文件。
    返回 (json_path, md_path)
    """
    audit_dir = _ensure_audit_dir(filepath)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    zhuque_data = zhuque_data or {}
    pre_result = zhuque_data.get("pre_result") or {}
    post_result = zhuque_data.get("post_result") or {}

    pre_ai_rate = zhuque_data.get("pre_ai_rate")
    post_ai_rate = zhuque_data.get("post_ai_rate")
    rate_drop = zhuque_data.get("rate_drop", 0.0)

    toxic_segments = pre_result.get("toxic_segments") or []

    # 若有朱雀专属自检诊断专报，持久化存入专报 Markdown
    has_dedicated_report = False
    report_filename = ""
    if zhuque_report_md and zhuque_report_md.strip():
        report_filename = f"chapter_{chapter_num}_zhuque_report.md"
        report_path = os.path.join(audit_dir, report_filename)
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(zhuque_report_md)
            has_dedicated_report = True
        except Exception as e:
            pass

    # 提取修改清单中的高频关键词或违规项
    extracted_cliches = []
    if checklist_text:
        # 寻找引号中的词汇或修改项
        quoted = re.findall(r'["“「]([^"”」]{2,10})["”」]', checklist_text)
        if quoted:
            extracted_cliches = list(dict.fromkeys(quoted))[:15]

    audit_entry = {
        "chapter_num": int(chapter_num),
        "chapter_title": chapter_title or f"第{chapter_num}章",
        "timestamp": now_str,
        "pipeline_mode": pipeline_mode,
        "elapsed_seconds": round(float(elapsed_seconds), 1),
        "models": {
            "draft_engine": llm_draft_engine,
            "reviewer_engine": reviewer_engine,
            "audit_scanner": "Tencent Zhuque (EdgeOne Makers)" if zhuque_data else "None",
        },
        "metrics": {
            "target_words": word_number,
            "draft_chars": len(draft_text),
            "polished_chars": len(polished_text),
            "translation_words": len(translation_text.split()) if translation_text else 0,
            "pre_ai_rate": pre_ai_rate,
            "post_ai_rate": post_ai_rate,
            "rate_drop": rate_drop,
            "toxic_count": len(toxic_segments),
            "pass_status": "PASS" if (post_ai_rate is not None and post_ai_rate <= 30) else ("SKIPPED" if post_ai_rate is None else "WARN"),
        },
        "zhuque_diagnostics": {
            "pre_ai_rate": pre_ai_rate,
            "post_ai_rate": post_ai_rate,
            "rate_drop": rate_drop,
            "toxic_segments": toxic_segments,
            "has_dedicated_report": has_dedicated_report,
            "report_filename": report_filename,
            "rounds_history": zhuque_data.get("rounds_history", []),
            "converged_reason": zhuque_data.get("converged_reason", ""),
        },
        "gpt_review": {
            "checklist": checklist_text,
            "extracted_cliches": extracted_cliches,
        },
        "overseas_translation": {
            "word_count": len(translation_text.split()) if translation_text else 0,
            "has_translation": bool(translation_text.strip()),
            "audit_report_summary": audit_report[:500] if audit_report else "",
        },
        "continuity_archive": {
            "has_summary": bool(summary.strip()),
            "summary_chars": len(summary),
            "has_handoff": bool(handoff),
            "handoff_summary": handoff.get("scene_state", "")[:200] if isinstance(handoff, dict) else "",
        },
    }

    # 1. 写入结构化 JSON
    json_filename = f"chapter_{chapter_num}_audit.json"
    json_path = os.path.join(audit_dir, json_filename)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(audit_entry, f, ensure_ascii=False, indent=2)

    # 2. 写入便于阅读与打印的 Markdown 报告
    md_filename = f"chapter_{chapter_num}_audit.md"
    md_path = os.path.join(audit_dir, md_filename)
    md_content = _build_chapter_audit_markdown(audit_entry, draft_text, polished_text)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 3. 更新全书主账本索引 (book_audit_index.json)
    _update_master_index(filepath, audit_entry)

    return json_path, md_path


def _build_chapter_audit_markdown(entry: Dict[str, Any], draft_text: str, polished_text: str) -> str:
    m = entry["metrics"]
    diag = entry["zhuque_diagnostics"]
    ch = entry["chapter_num"]
    title = entry["chapter_title"]

    status_icon = "🟢" if m["pass_status"] == "PASS" else ("⚪" if m["pass_status"] == "SKIPPED" else "🟡")

    toxic_section = ""
    if diag.get("toxic_segments"):
        lines = ["\n### 🎯 朱雀扫描捕获的病灶段落与诊断"]
        for seg in diag["toxic_segments"]:
            idx = seg.get("paragraph_index", 0) + 1
            conf = round(float(seg.get("ai_confidence", 0.0)) * 100, 1)
            reasons = "、".join(seg.get("reasons", ["公式化句式"]))
            txt = seg.get("text", "")[:120]
            lines.append(f"- **段落 #{idx}**（AI置信度: `{conf}%` · 病因: `{reasons}`）\n  > {txt}…")
        toxic_section = "\n".join(lines)
    else:
        toxic_section = "\n### 🎯 朱雀扫描结果\n未发现高危机械病灶或未接入客观雷达打分。"

    checklist_sec = ""
    if entry["gpt_review"]["checklist"]:
        checklist_sec = f"\n### 📋 Codex (GPT) 审校修改清单\n```text\n{entry['gpt_review']['checklist'][:2500]}\n```"

    report_link_sec = ""
    if diag.get("has_dedicated_report") and diag.get("report_filename"):
        report_link_sec = f"\n> 📄 **朱雀专属自检诊断专报**：本章已生成有界渐进收敛诊断专报，详见同级归档文件 `audit_trails/{diag['report_filename']}`\n"

    is_zh_only = (entry["pipeline_mode"] == "fast_zh")
    en_row = "" if is_zh_only else f'\n| **英文译制** | -- | {m["translation_words"]} 词 | {"已译制并质检" if m["translation_words"] > 0 else "待译制"} |'
    mode_label = "🇨🇳 纯中文出稿流水线" if is_zh_only else "🌐 英文出海双语流水线"

    md = f"""# 第 {ch} 章全链路生产与质量留底档案

- **章节名称**：{title}
- **归档时间**：{entry["timestamp"]}
- **流水线模式**：`{mode_label}`
- **生成总耗时**：`{entry["elapsed_seconds"]} 秒`
- **质量门禁裁决**：{status_icon} `{m["pass_status"]}`

---

## 📊 核心指标矩阵

| 指标维度 | 初始起草 ({entry.get("llm_draft_engine", "gemini-3.8-flash-low")}) | 审校定稿 ({entry.get("reviewer_engine", "gemini-4-hydrogen-medium")}) | 演进结果 |
| :--- | :--- | :--- | :--- |
| **字符规模** | {m["draft_chars"]} 字 | {m["polished_chars"]} 字 | 净变动 {m["polished_chars"] - m["draft_chars"]} 字 |{en_row}

---

## 🛡️ AI 审校修改留底
{checklist_sec}

---

## 📜 文本前后比对摘要（前 200 字与后 150 字钩子）

### 【起草版首段】
> {draft_text[:200]}...

### 【审校定稿版首段】
> {polished_text[:200]}...

### 【章末 150 字断章钩子（Hook）检验】
> ...{polished_text[-180:] if len(polished_text) >= 180 else polished_text}

---
*本档案由 AI Novel Studio 质量追踪留底系统自动生成，供全书完结后提炼迭代规则。*
"""
    return md


def _update_master_index(filepath: str, entry: Dict[str, Any]):
    """更新全书流水线总账本索引"""
    audit_dir = _ensure_audit_dir(filepath)
    index_file = os.path.join(audit_dir, "book_audit_index.json")

    data = {"project_filepath": filepath, "chapters": {}}
    if os.path.exists(index_file):
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    ch_key = str(entry["chapter_num"])
    data["chapters"][ch_key] = {
        "chapter_num": entry["chapter_num"],
        "chapter_title": entry["chapter_title"],
        "timestamp": entry["timestamp"],
        "pipeline_mode": entry["pipeline_mode"],
        "draft_chars": entry["metrics"]["draft_chars"],
        "polished_chars": entry["metrics"]["polished_chars"],
        "translation_words": entry["metrics"]["translation_words"],
        "pre_ai_rate": entry["metrics"]["pre_ai_rate"],
        "post_ai_rate": entry["metrics"]["post_ai_rate"],
        "rate_drop": entry["metrics"]["rate_drop"],
        "pass_status": entry["metrics"]["pass_status"],
    }

    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def backfill_historical_audits(filepath: str) -> List[Dict[str, Any]]:
    """
    自动对项目中已存在的所有章节（如第 1~13 章）进行回溯审计归档。
    即使是在开启自动留底前生成的章节，也能无缝补齐档案。
    """
    chapters_dir = os.path.join(filepath, "chapters")
    if not os.path.exists(chapters_dir):
        return []

    en_dir = os.path.join(filepath, "chapters_en")
    handoff_file = os.path.join(filepath, "Novel_handoff.json")

    handoffs_all = {}
    if os.path.exists(handoff_file):
        try:
            with open(handoff_file, "r", encoding="utf-8") as hf:
                handoffs_all = json.load(hf)
        except Exception:
            pass

    results = []

    # 扫描已有的 chapter_{n}.txt
    chapter_files = [f for f in os.listdir(chapters_dir) if re.match(r"^chapter_\d+\.txt$", f)]
    chapter_files.sort(key=lambda x: int(re.search(r"\d+", x).group()))

    for cf in chapter_files:
        ch_num = int(re.search(r"\d+", cf).group())
        final_path = os.path.join(chapters_dir, cf)
        raw_path = os.path.join(chapters_dir, f"chapter_{ch_num}_raw_draft.txt")
        chk_path = os.path.join(chapters_dir, f"chapter_{ch_num}_polish_checklist.txt")
        en_path = os.path.join(en_dir, f"chapter_{ch_num}_en.txt")

        final_text = ""
        raw_text = ""
        chk_text = ""
        en_text = ""

        if os.path.exists(final_path):
            with open(final_path, "r", encoding="utf-8", errors="ignore") as f:
                final_text = f.read()
        if os.path.exists(raw_path):
            with open(raw_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
        if os.path.exists(chk_path):
            with open(chk_path, "r", encoding="utf-8", errors="ignore") as f:
                chk_text = f.read()
        if os.path.exists(en_path):
            with open(en_path, "r", encoding="utf-8", errors="ignore") as f:
                en_text = f.read()

        ch_handoff = handoffs_all.get(str(ch_num)) or handoffs_all.get(ch_num)

        # 估算/提取修改清单中的特征
        p_mode = "bilingual" if en_text.strip() else "fast_zh"

        record_chapter_audit(
            filepath=filepath,
            chapter_num=ch_num,
            chapter_title=f"第{ch_num}章",
            pipeline_mode=p_mode,
            llm_draft_engine="gemini-3.8-flash-low",
            reviewer_engine="Codex (GPT-4o/sol)",
            word_number=3000,
            draft_text=raw_text or final_text,
            polished_text=final_text,
            checklist_text=chk_text,
            zhuque_data=None,  # 历史章节未经过当时朱雀打分的做静态留底
            translation_text=en_text,
            audit_report="",
            summary="",
            handoff=ch_handoff,
            elapsed_seconds=0.0,
        )
        results.append({"chapter_num": ch_num, "status": "backfilled"})

    # 生成全书汇总分析与迭代建议
    generate_book_iteration_report(filepath)
    return results


def generate_book_iteration_report(filepath: str) -> str:
    """
    全书完结或阶段性复盘：自动汇总所有章节档案，生成《全书AI痕迹消杀与写作规则迭代白皮书》
    """
    audit_dir = _ensure_audit_dir(filepath)
    index_file = os.path.join(audit_dir, "book_audit_index.json")

    chapters = {}
    if os.path.exists(index_file):
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                chapters = json.load(f).get("chapters", {})
        except Exception:
            pass

    total_chapters = len(chapters)
    total_draft_chars = sum(c.get("draft_chars", 0) for c in chapters.values())
    total_polished_chars = sum(c.get("polished_chars", 0) for c in chapters.values())
    total_en_words = sum(c.get("translation_words", 0) for c in chapters.values())

    # 收集各章 checklist 中的高频词
    all_cliches = {}
    for ch_k in chapters.keys():
        ch_json_p = os.path.join(audit_dir, f"chapter_{ch_k}_audit.json")
        if os.path.exists(ch_json_p):
            try:
                with open(ch_json_p, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                    for w in cdata.get("gpt_review", {}).get("extracted_cliches", []):
                        all_cliches[w] = all_cliches.get(w, 0) + 1
            except Exception:
                pass

    top_cliches = sorted(all_cliches.items(), key=lambda x: x[1], reverse=True)[:15]

    report_lines = [
        "# 📘 全书生成质量追踪留底与规则迭代白皮书",
        f"\n**生成时间**：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**追踪章节总数**：{total_chapters} 章",
        f"**全书起草总规模**：约 {total_draft_chars:,} 字",
        f"**全书审校定稿总规模**：约 {total_polished_chars:,} 字",
        f"**全书出海英译总规模**：约 {total_en_words:,} 词",
        "\n---",
        "\n## 📈 章节质量全景台账",
        "\n| 章节 | 模式 | 初稿字数 | 定稿字数 | 朱雀初检 | GPT改写后 | 门禁裁决 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for ch_k in sorted(chapters.keys(), key=lambda x: int(x)):
        c = chapters[ch_k]
        pre_ai = f"{c.get('pre_ai_rate')}%" if c.get('pre_ai_rate') is not None else "--"
        post_ai = f"{c.get('post_ai_rate')}%" if c.get('post_ai_rate') is not None else "--"
        report_lines.append(
            f"| 第 {c['chapter_num']} 章 | `{c.get('pipeline_mode')}` | {c.get('draft_chars', 0)} | {c.get('polished_chars', 0)} | {pre_ai} | {post_ai} | `{c.get('pass_status')}` |"
        )

    report_lines.extend([
        "\n---",
        "\n## 🎯 提炼出的高频 AI 模板词与套话排行榜（规则优化优先库）",
    ])

    if top_cliches:
        for idx, (word, cnt) in enumerate(top_cliches, 1):
            report_lines.append(f"{idx}. **「{word}」**：在全书审查中被检出/开刀修改 **{cnt}** 次")
    else:
        report_lines.append("- 暂未提取到足够频次的套话样本。")

    report_lines.extend([
        "\n---",
        "\n## 💡 下一阶段规则迭代优化建议",
        "1. **Prompt 负向词表前置注入**：将上述高频套话直接注入 Stage 2 起草 Prompt 的【强制禁用词库】，从源头阻断产生此类词汇。",
        "2. **章末钩子张力增强**：依据各章章末 150 字的张力表现，提高危机与悬念反转密度。",
        "3. **审校模型复盘**：持续结合 Gemini 4 Hydrogen (Medium) 输出的修改清单优化起草提示词。",
    ])

    report_text = "\n".join(report_lines)
    report_file = os.path.join(audit_dir, "book_iteration_whitepaper.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_text)

    return report_text
