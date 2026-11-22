# -*- mode: python ; coding: utf-8 -*-
"""
novel_generator/state_tracker.py

结构化世界与角色状态追踪器 (Structured World & Character State Tracker)
- 提供角色当前生死、地理位置、伤势、随身物品/法宝、阵营好感度等结构化数据
- 提供常驻绝对铁律与不可变锚点 (Mandatory Anchor)
- 提供章后基于 LLM 的 Delta (差量演进) 自动提取与写入合并
"""

from __future__ import annotations
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional


DEFAULT_WORLD_STATE: Dict[str, Any] = {
    "mandatory_anchors": {
        "world_iron_laws": "1. 境界压制绝对不可逆，跨大境界对决必须借助特定神物或巨大代价。\n2. 人死不可无代价复活，天道轮回不可逆。\n3. 本方天地灵气有限，因果业力真实存在。",
        "protagonist_core_persona": "性格沉稳冷静，杀伐果断但不滥杀无辜；绝不轻易信奉任何宗门宣讲；言出必行；对外极度谨慎，永远隐藏真实底牌；不可触碰逆鳞为至亲挚友。",
        "current_volume_goal": "在第一卷中立足落日城，隐藏天机神物，突破至筑基期，查清家族覆灭的初步线索。",
    },
    "characters": {},
    "factions": {},
    "world_flags": {
        "current_chapter": 1,
        "active_timeline": "天武历三万两千四百年",
    },
}


def _get_world_state_path(filepath: str) -> str:
    return os.path.join(filepath, "world_state.json")


def load_world_state(filepath: str) -> Dict[str, Any]:
    """读取当前书籍的结构化状态数据。若不存在则初始化默认状态。"""
    path = _get_world_state_path(filepath)
    if not os.path.exists(path):
        save_world_state(filepath, DEFAULT_WORLD_STATE)
        return json.loads(json.dumps(DEFAULT_WORLD_STATE))
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 补全缺失结构
            for k, v in DEFAULT_WORLD_STATE.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception as e:
        logging.error(f"读取 world_state.json 失败: {e}")
        return json.loads(json.dumps(DEFAULT_WORLD_STATE))


def save_world_state(filepath: str, state: Dict[str, Any]) -> None:
    """持久化保存当前书籍的结构化状态数据。"""
    path = _get_world_state_path(filepath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"保存 world_state.json 失败: {e}")


def get_mandatory_anchors(filepath: str) -> Dict[str, str]:
    """获取常驻绝对锚点上下文（铁律、主角底色、当前卷目标）。"""
    state = load_world_state(filepath)
    return state.get("mandatory_anchors", DEFAULT_WORLD_STATE["mandatory_anchors"])


def format_mandatory_anchors_for_prompt(filepath: str) -> str:
    """格式化为强制塞入 Prompt 顶层的绝对规则文本。"""
    anchors = get_mandatory_anchors(filepath)
    laws = anchors.get("world_iron_laws", "").strip()
    persona = anchors.get("protagonist_core_persona", "").strip()
    goal = anchors.get("current_volume_goal", "").strip()

    parts = []
    if laws:
        parts.append(f"【世界观绝对铁律（不可违背）】\n{laws}")
    if persona:
        parts.append(f"【核心主角底层人设（不可漂移）】\n{persona}")
    if goal:
        parts.append(f"【当前卷核心终极目标】\n{goal}")

    if not parts:
        return ""
    return "=== 🏛️ 常驻绝对核心锚点（100% 优先遵循，绝对不可违背） ===\n" + "\n\n".join(parts) + "\n=================================================="


def get_characters_snapshot(filepath: str, names: Optional[List[str]] = None) -> Dict[str, Any]:
    """按角色名精确查询状态快照。若 names 为空则返回全部角色。"""
    state = load_world_state(filepath)
    chars = state.get("characters", {})
    if not names:
        return chars

    result = {}
    clean_names = [n.strip() for n in names if n.strip()]
    for query_name in clean_names:
        matched = False
        for cname, cinfo in chars.items():
            if query_name in cname or cname in query_name:
                result[cname] = cinfo
                matched = True
        if not matched:
            result[query_name] = {
                "is_alive": True,
                "current_location": "随剧情主线",
                "physical_condition": "正常",
                "inventory": [],
                "note": "尚未录入详细状态",
            }
    return result


def format_characters_for_prompt(filepath: str, names: Optional[List[str]] = None) -> str:
    """格式化出场角色最新状态为写前约束注入 Prompt。"""
    snapshot = get_characters_snapshot(filepath, names)
    if not snapshot:
        return ""

    lines = ["=== 📊 出场人物实时状态硬约束（严格基于事实，禁止吃书） ==="]
    for name, info in snapshot.items():
        alive_str = "存活" if info.get("is_alive", True) else "已死亡/消散"
        loc = info.get("current_location", "未知")
        cond = info.get("physical_condition", "正常")
        inv = ", ".join(info.get("inventory", [])) or "无特殊随身道具"
        affil = info.get("affiliations") or info.get("faction") or ""
        attitude = info.get("attitude_to_mc") or ""

        detail = f"• 【{name}】[{alive_str}] 所在位置: {loc} | 状态/伤势: {cond} | 随身关键物品: {inv}"
        if affil:
            detail += f" | 阵营归属: {affil}"
        if attitude:
            detail += f" | 对主角态度: {attitude}"
        lines.append(detail)
    lines.append("==========================================================")
    return "\n".join(lines)


def apply_state_delta(filepath: str, delta: Dict[str, Any], chapter_num: int = 1) -> Dict[str, Any]:
    """将一章产生的状态差量 (Delta) 合并入持久化状态表中。"""
    state = load_world_state(filepath)
    chars = state.setdefault("characters", {})

    char_deltas = delta.get("character_deltas", {})
    for name, changes in char_deltas.items():
        target_key = name
        for existing in list(chars.keys()):
            if name in existing or existing in name:
                target_key = existing
                break

        current = chars.setdefault(target_key, {
            "is_alive": True,
            "current_location": "随主线",
            "physical_condition": "正常",
            "inventory": [],
        })

        if "is_alive" in changes:
            current["is_alive"] = bool(changes["is_alive"])
        if "location" in changes and changes["location"]:
            current["current_location"] = str(changes["location"])
        if "physical_condition" in changes and changes["physical_condition"]:
            current["physical_condition"] = str(changes["physical_condition"])
        if "attitude_to_mc" in changes and changes["attitude_to_mc"]:
            current["attitude_to_mc"] = str(changes["attitude_to_mc"])
        if "affiliations" in changes and changes["affiliations"]:
            current["affiliations"] = str(changes["affiliations"])

        # 随身物品变动：支持增量与消耗
        inv = list(current.get("inventory", []))
        if "items_acquired" in changes and isinstance(changes["items_acquired"], list):
            for itm in changes["items_acquired"]:
                if itm and itm not in inv:
                    inv.append(itm)
        if "items_consumed" in changes and isinstance(changes["items_consumed"], list):
            for itm in changes["items_consumed"]:
                if itm in inv:
                    inv.remove(itm)
        current["inventory"] = inv
        current["last_updated_chapter"] = chapter_num

    # 世界标记增量更新
    world_flags_delta = delta.get("world_flags_delta", {})
    if world_flags_delta:
        state.setdefault("world_flags", {}).update(world_flags_delta)
    state.setdefault("world_flags", {})["current_chapter"] = chapter_num

    save_world_state(filepath, state)
    return state


def extract_chapter_delta_with_llm(
    llm_adapter,
    filepath: str,
    chapter_text: str,
    chapter_num: int,
    character_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """利用 LLM 自动对比本章正文，提取角色与世界状态增量 (Delta)。"""
    if not chapter_text or not chapter_text.strip():
        return {}

    snapshot = get_characters_snapshot(filepath, character_names)
    snapshot_json = json.dumps(snapshot, ensure_ascii=False, indent=2)

    prompt = f"""你是一名严谨的网文状态总编与因果追踪管家。
请阅读【第 {chapter_num} 章正文】，对比【本章开始前的角色状态卡】，严格提取本章正文中发生的客观状态演进与变更。

【本章开始前的角色状态卡】：
{snapshot_json}

【第 {chapter_num} 章正文】：
{chapter_text[:8000]}

请严格输出合法的 JSON 格式数据，不得包含解释或 Markdown 格式以外的废话：
```json
{{
  "character_deltas": {{
    "角色姓名": {{
      "is_alive": true,
      "location": "本章结束时所在的具体位置",
      "physical_condition": "本章结束时的最新伤势/功力状态",
      "items_acquired": ["本章新获得的物品或战利品"],
      "items_consumed": ["本章用掉或损毁的物品"],
      "attitude_to_mc": "本章产生的对主角好感度或态度转变",
      "summary": "一句话概括此人本章经历"
    }}
  }},
  "world_flags_delta": {{
    "本章发生的重要大事件或天下局势标记": "描述"
  }}
}}
```"""

    try:
        reply = llm_adapter.generate(prompt)
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", reply)
        raw_json = match.group(1) if match else reply.strip()
        delta = json.loads(raw_json)
        return delta
    except Exception as e:
        logging.warning(f"提取章节状态 Delta 失败: {e}")
        return {}
