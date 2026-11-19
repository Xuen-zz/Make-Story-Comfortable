#novel_generator/finalization.py
# -*- coding: utf-8 -*-
"""
定稿章节和扩写章节（finalize_chapter、enrich_chapter_text）
"""
import os
import re
import logging
from llm_adapters import create_llm_adapter
from embedding_adapters import create_embedding_adapter
import prompt_definitions
from novel_generator.common import invoke_with_cleaning
from utils import read_file, clear_file_content, save_string_to_txt
from novel_generator.vectorstore_utils import update_vector_store
from chapter_directory_parser import get_chapter_info_from_blueprint
logging.basicConfig(
    filename='app.log',      # 日志文件名
    filemode='a',            # 追加模式（'w' 会覆盖）
    level=logging.INFO,      # 记录 INFO 及以上级别的日志
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
def parse_character_blocks(state_text: str) -> list[tuple[str, str]]:
    """
    将角色状态文档按角色拆分。
    返回 [(角色名, 该角色完整文本), ...] 列表。
    角色块以"顶格文字 + 中/英文冒号"开头（如 "男主（园艺师青木）："），
    下一个角色块或文档末尾为结束。
    排除 markdown 标记（*#->+）和树状符号开头的行，避免误匹配子标题。
    """
    # 匹配行首非树状符号、非 markdown 标记开头、以冒号结尾的行作为角色名
    pattern = re.compile(r'^([^\s├│└─\-*#>+\n][^\n├│└]*)[：:][ \t]*$', re.MULTILINE)
    matches = list(pattern.finditer(state_text))
    if not matches:
        return [("全部角色", state_text)]

    blocks = []
    for idx, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(state_text)
        block_text = state_text[start:end].strip()
        blocks.append((name, block_text))

    # 将首个匹配之前的文本（如 markdown 格式的角色描述）合并到第一个角色块
    if matches and matches[0].start() > 0:
        prefix = state_text[:matches[0].start()].strip()
        if prefix and blocks:
            blocks[0] = (blocks[0][0], prefix + "\n\n" + blocks[0][1])

    return blocks


def _name_matches(keywords: list[str], block_name: str, block_text: str = "") -> bool:
    """
    判断关键词列表中是否有任何一个与角色块名或块文本前部匹配。
    支持灵活匹配：将关键词按括号拆分为子片段，任一片段（≥2字）命中即可。
    例如关键词 '男主（青木）' 拆出 '男主' 和 '青木'，能匹配 '男主（园艺师青木）'。
    同时检查 block_text 的前几行，以处理"男主角名：\n陈玉"这类角色名不在标题行的情况。
    """
    # 取 block_text 前3行用于辅助匹配
    head_lines = "\n".join(block_text.split("\n")[:3]) if block_text else ""
    search_text = block_name + "\n" + head_lines

    for kw in keywords:
        # 直接子串匹配（同时搜索块标题和前几行）
        if kw in search_text or block_name in kw:
            return True
        # 拆分括号内外片段再匹配
        tokens = re.split(r'[（）()·\s]+', kw)
        for token in tokens:
            if token and len(token) >= 2 and token in search_text:
                return True
    return False


def filter_character_state(character_state_text: str, characters_involved: str) -> str:
    """
    按需过滤角色状态，只保留本章涉及的角色。
    1. characters_involved 为空 → 返回全文
    2. 按分隔符拆分为关键词列表
    3. parse_character_blocks 拆分角色状态
    4. 子串匹配：关键词 in 角色名 → 保留该角色块
    5. 无匹配 → 安全回退返回全文
    6. 返回匹配的角色块拼接
    """
    if not characters_involved or not characters_involved.strip():
        return character_state_text
    if not character_state_text or not character_state_text.strip():
        return character_state_text

    # 拆分关键词
    keywords = re.split(r'[,，;；\s\n]+', characters_involved.strip())
    keywords = [kw.strip() for kw in keywords if kw.strip()]
    if not keywords:
        return character_state_text

    blocks = parse_character_blocks(character_state_text)
    if len(blocks) <= 1:
        return character_state_text

    matched = []
    for name, block_text in blocks:
        if _name_matches(keywords, name, block_text):
            matched.append(block_text)

    # 无匹配 → 安全回退返回全文
    if not matched:
        return character_state_text

    return "\n\n".join(matched)


def auto_detect_characters(character_state_text: str, *text_sources: str) -> list[str]:
    """
    从 character_state 中提取角色名列表，
    在 text_sources 中检测哪些角色名出现，返回匹配的角色名。
    """
    if not character_state_text or not character_state_text.strip():
        return []
    blocks = parse_character_blocks(character_state_text)
    if len(blocks) <= 1 and blocks and blocks[0][0] == "全部角色":
        return []

    search_text = " ".join(text_sources)
    if not search_text.strip():
        return []

    # 收集所有角色的关键词，用于排除"单字但同时是其他角色子串"的误匹配
    all_names = [n for n, _ in blocks]

    matched_names = []
    for name, _ in blocks:
        # 跳过非角色条目（如"待登场角色"）
        if re.match(r'^待登场', name):
            continue

        # 提取关键词：括号内外分别作为关键词
        keywords = []
        # 分离括号内外部分（支持中英文括号）
        outer = re.sub(r'[（(][^）)]*[）)]', '', name).strip()
        inner_matches = re.findall(r'[（(]([^）)]*)[）)]', name)
        if outer:
            keywords.append(outer)
            # 取末尾2字短名（如 "千堂静" → "堂静"）
            if len(outer) >= 3:
                short = outer[-2:]
                if short not in keywords:
                    keywords.append(short)
            # 取末尾1字（如 "千堂静" → "静"），由后续过滤决定是否保留
            if len(outer) >= 2:
                single = outer[-1]
                if single not in keywords:
                    keywords.append(single)
        for inner in inner_matches:
            inner = inner.strip()
            if inner:
                keywords.append(inner)
                # 对括号内文本，尝试提取末尾人名（去掉职业等前缀）
                # 例如 "园艺师青木" → 也加入 "青木"
                if len(inner) >= 3:
                    short = inner[-2:]
                    if short not in keywords:
                        keywords.append(short)

        # 过滤：去掉长度 ≤ 1 的关键词，但保留那些不会导致大量误匹配的单字角色名
        # 单字角色名（如"绫"）：如果它不是其他任何角色名的子串，保留它
        filtered = []
        for kw in keywords:
            if len(kw) >= 2:
                filtered.append(kw)
            elif len(kw) == 1:
                # 单字：检查是否为其他角色名的子串（排除自己）
                is_ambiguous = any(kw in other_name and other_name != name
                                   for other_name in all_names)
                if not is_ambiguous:
                    filtered.append(kw)
        keywords = filtered

        # 子串匹配（单字关键词要求前后不能紧邻其他汉字，避免"冷静"匹配"静"）
        for kw in keywords:
            if len(kw) == 1:
                # 单字：检查每个出现位置，要求至少有一处前或后不紧邻汉字
                for m in re.finditer(re.escape(kw), search_text):
                    pos = m.start()
                    before = search_text[pos - 1] if pos > 0 else ""
                    after = search_text[pos + 1] if pos + 1 < len(search_text) else ""
                    # 前后至少有一侧不是汉字（标点、空格、行首行尾等）
                    before_ok = not re.match(r'[\u4e00-\u9fff]', before) if before else True
                    after_ok = not re.match(r'[\u4e00-\u9fff]', after) if after else True
                    if before_ok or after_ok:
                        matched_names.append(name)
                        break
                else:
                    continue
                break
            else:
                if kw in search_text:
                    matched_names.append(name)
                    break

    return matched_names


def _update_character_states_by_role(
    chapter_text: str,
    old_character_state: str,
    llm_adapter,
    characters_involved: str = "",
) -> str:
    """
    分角色更新状态：解析现有角色状态，对每个角色单独调用 LLM 更新，
    最后合并。大幅减少单次 prompt 大小。
    仅更新本章涉及的角色，未出场角色保留原状态。
    """
    blocks = parse_character_blocks(old_character_state)
    logging.info(f"[Finalize] 角色状态拆分为 {len(blocks)} 个角色块: "
                 f"{[name for name, _ in blocks]}")

    # 解析涉及角色名单
    involved_names = set()
    if characters_involved:
        for name in re.split(r'[,，、;；\s]+', characters_involved):
            name = name.strip()
            if name:
                involved_names.add(name)

    # 如果只有1个角色块或解析失败，回退到整体更新
    if len(blocks) <= 1:
        logging.info("[Finalize] 仅1个角色块，使用整体更新")
        prompt = prompt_definitions.update_character_state_prompt.format(
            chapter_text=chapter_text,
            old_state=old_character_state
        )
        result = invoke_with_cleaning(llm_adapter, prompt)
        return result if result.strip() else old_character_state

    involved_keywords = list(involved_names) if involved_names else []

    updated_blocks = []
    for name, block_text in blocks:
        # 判断该角色是否在本章出场
        if involved_keywords and not _name_matches(involved_keywords, name, block_text):
            logging.info(f"[Finalize] 跳过未出场角色: {name}")
            updated_blocks.append(block_text)
            continue

        logging.info(f"[Finalize] 更新角色: {name} (状态长度={len(block_text)}字)")
        prompt = f"""以下是新完成的章节文本：
{chapter_text}

这是角色「{name}」的当前状态：
{block_text}

请根据章节内容更新该角色的状态。要求：
- 保持原有树状结构格式不变
- 更新物品、能力、状态、关系网、事件等变化
- 语言简洁有条理
- 仅返回该角色更新后的状态文本，不要解释任何内容。"""
        result = invoke_with_cleaning(llm_adapter, prompt)
        if result.strip():
            updated_blocks.append(result.strip())
        else:
            logging.warning(f"[Finalize] 角色 {name} 更新失败，保留原状态")
            updated_blocks.append(block_text)

    return "\n\n".join(updated_blocks)


def finalize_chapter(
    novel_number: int,
    word_number: int,
    api_key: str,
    base_url: str,
    model_name: str,
    temperature: float,
    filepath: str,
    embedding_api_key: str,
    embedding_url: str,
    embedding_interface_format: str,
    embedding_model_name: str,
    interface_format: str,
    max_tokens: int,
    timeout: int = 600,
    workflow_mode: str = "outlined",
):
    """
    对指定章节做最终处理：更新前文摘要、更新角色状态、插入向量库等。
    默认无需再做扩写操作，若有需要可在外部调用 enrich_chapter_text 处理后再定稿。
    """
    chapters_dir = os.path.join(filepath, "chapters")
    chapter_file = os.path.join(chapters_dir, f"chapter_{novel_number}.txt")
    chapter_text = read_file(chapter_file).strip()
    import re
    chapter_text = re.sub(r'^[\u2705\u274c\u26a0].*?\n+', '', chapter_text).strip()
    if not chapter_text:
        logging.warning(f"Chapter {novel_number} is empty, cannot finalize.")
        return

    global_summary_file = os.path.join(filepath, "global_summary.txt")
    old_global_summary = read_file(global_summary_file)
    character_state_file = os.path.join(filepath, "character_state.txt")
    old_character_state = read_file(character_state_file)

    # 识别本章涉及角色
    directory_file = os.path.join(filepath, "Novel_directory.txt")
    blueprint_text = read_file(directory_file)
    chapter_info = get_chapter_info_from_blueprint(blueprint_text, novel_number)
    characters_involved = chapter_info.get("characters_involved", "")
    if not characters_involved:
        # 兜底：自动检测
        auto_chars = auto_detect_characters(
            old_character_state,
            chapter_info.get("chapter_purpose", ""),
            chapter_info.get("chapter_summary", ""),
            chapter_text[:2000],
        )
        if auto_chars:
            characters_involved = "，".join(auto_chars)
    logging.info(f"[Finalize] 第{novel_number}章涉及角色: {characters_involved or '(未识别，将更新全部)'}")

    llm_adapter = create_llm_adapter(
        interface_format=interface_format,
        base_url=base_url,
        model_name=model_name,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout
    )

    prompt_summary = prompt_definitions.summary_prompt.format(
        chapter_text=chapter_text,
        global_summary=old_global_summary
    )
    new_global_summary = invoke_with_cleaning(llm_adapter, prompt_summary)
    if not new_global_summary.strip():
        new_global_summary = old_global_summary

    new_char_state = _update_character_states_by_role(
        chapter_text=chapter_text,
        old_character_state=old_character_state,
        llm_adapter=llm_adapter,
        characters_involved=characters_involved,
    )

    clear_file_content(global_summary_file)
    save_string_to_txt(new_global_summary, global_summary_file)
    clear_file_content(character_state_file)
    save_string_to_txt(new_char_state, character_state_file)

    update_vector_store(
        embedding_adapter=create_embedding_adapter(
            embedding_interface_format,
            embedding_api_key,
            embedding_url,
            embedding_model_name
        ),
        new_chapter=chapter_text,
        filepath=filepath
    )

    # 即兴模式：更新伏笔池
    if workflow_mode == "improv":
        try:
            from novel_generator.improv import update_open_threads
            update_open_threads(
                interface_format=interface_format,
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                filepath=filepath,
                chapter_number=novel_number,
                chapter_text=chapter_text,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        except Exception as e:
            logging.error(f"[Improv] open_threads update failed: {e}")

    # ── 自动提炼生成下一章的幕间因果交接（Semantic Handoff） ──
    try:
        from novel_generator.continuity import build_semantic_handoff_from_chapter
        build_semantic_handoff_from_chapter(
            filepath=filepath,
            chapter_num=novel_number,
            chapter_text=chapter_text,
            llm_adapter=llm_adapter
        )
        logging.info(f"[Finalize] 已自动提炼并存储第 {novel_number + 1} 章的 Semantic Handoff")
    except Exception as e:
        logging.warning(f"[Finalize] 自动提炼下章 Handoff 失败: {e}")

    logging.info(f"Chapter {novel_number} has been finalized.")

def expand_scenes(
    chapter_text: str,
    sensuality_level: str,
    api_key: str,
    base_url: str,
    model_name: str,
    temperature: float,
    interface_format: str,
    max_tokens: int,
    timeout: int = 600,
    writing_style: str = "",
    narrative_instruction: str = "",
    polish_guidance: str = "",
    polish_mode: str = "enhance",
    extra_context: str = "",
    progress=None,
    custom_prompt_override: str = "",
) -> str:
    """
    对章节文本进行润色。支持多种模式：
    - enhance: 通用润色扩写（默认，使用预设prompt）
    - sensual: 专注亲密场景润色
    - modify: 修改指定段落的剧情
    - add: 在指定位置增加新内容
    """
    llm_adapter = create_llm_adapter(
        interface_format=interface_format,
        base_url=base_url,
        model_name=model_name,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout
    )

    _MODE_PROMPTS = {
        "editorial_review": """你是一位拥有二十年畅销网文出版与爆款运营经验的资深中文总编辑。请对以下章节草稿执行【强力去AI味 + 节奏审校】。

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
""",
        "editorial_review_light": """你是一位专业中文小说审稿编辑。请对以下章节草稿执行【轻度流畅润色 + 逻辑校对】。

【润色准则】：
1. 最大程度保留原草稿的文风、句式和叙事习惯，不做大刀阔斧的改写。
2. 仅修正以下问题：错别字与语病、明显重复啰嗦的句子、零星突兀的 AI 套话（如“空气仿佛凝固”“眼底闪过一抹”）、以及对照参考资料修正人物称谓或设定矛盾。
3. 确保章末最后几句过渡自然且保有悬念，不平淡流水账收尾。

【输出格式要求】：
先输出润色后的完整正式章节正文；
然后另起一行输出分隔符 `---`，紧随其后输出 `【修改清单】`，简要说明修正的语句与校对点。

===== 章节原文 =====
{chapter_text}
""",
        "rule_polish": """你是一位资深网络小说编辑与审稿人。请对以下章节进行严格润色。
【润色任务】只改表达，不改剧情、不改设定、不增删情节。

【小说流水线底层规则 · 中文润色九大铁律】（必须逐条对照替换，输出附各项剩余次数）：
1.【脚本】跨章禁用词，每词全章≤2次：pale, iron, dust, ground, dared, northern, ancient/archaic/ancestral, dormant, heavy, surged, blood welled/trickled, cold sweat, bit down, dug fingertips（苍白/铁箍/灰尘/地面/竟敢/北境/古老/蛰伏/沉重/翻涌/冷汗/咬牙/掐指）。
2.【脚本】否定排比（No X. No Y. / neither…nor / 不是A也不是B / 没有...也没有... / 既不...也不...）全章合计≤2，按功能识别，不只匹配字面。
3. 同一比喻域（账本、法务、金属、冰）全章≤3处，且只归属固定角色。
4. 每场景精确数字≤2个；禁用医学术语（capillary, patella, respiratory, 毛细血管, 髌骨, 呼吸道等）。
5. 同类描写（声音平静/冷/平稳）全章只留一处。
6.【脚本】连续3句同结构、分词短语收尾每段≤1次、remained 全章≤3。
7. 修仙词外溢全部替换：vitality, life force, spirit, pressure point, radiance, mortal, energy, meridians, dantian, qi, cultivation, realm（严禁经脉、丹田、灵力、真气、境界、修炼；血脉异常统一写成"血脉堵塞/兽魂受损"）。
8. 对照正史页和固定写法表核对物件位置、伤势、颜色、称谓、知情范围（严禁让角色得知不在场的信息）。
9.【脚本】连续200字以上相似内容视为重复，删除后一处。

【输出格式要求】：
先输出润色后的完整章节正文；
然后另起一行分隔线，输出【修改清单】（逐项统计每类替换处数与剩余配额）。

===== 章节原文 =====
{chapter_text}
""",
        "modify": """\
你是一位专业的小说编辑，擅长根据作者意图修改剧情。

===== 章节原文 =====
{chapter_text}

===== 任务 =====
请根据作者的修改建议，对章节中的指定内容进行改写。

修改原则：
1. 只改动作者指定的部分，未提及的内容保持原样
2. 改写后的内容要与前后文自然衔接，不出现逻辑断裂
3. 保持角色性格和行为的一致性
4. 保持原文的文风和叙事视角

输出完整的修改后章节文本，不要解释。""",

        "add": """\
你是一位专业的小说编辑，擅长在已有章节中补充新内容。

===== 章节原文 =====
{chapter_text}

===== 任务 =====
请根据作者的指示，在章节中的指定位置补充新内容。

补充原则：
1. 新增内容要与原文风格一致，自然融入
2. 不要删减或大幅改动原有内容
3. 新增部分的篇幅和细节程度参考原文水准
4. 确保新增内容与前后文逻辑连贯

输出完整的补充后章节文本，不要解释。""",
    }

    if custom_prompt_override and custom_prompt_override.strip():
        tmpl = custom_prompt_override.strip()
        if "{chapter_text}" in tmpl:
            prompt = tmpl.replace("{chapter_text}", chapter_text)
        else:
            prompt = f"{tmpl}\n\n===== 章节原文 =====\n{chapter_text}"
    elif polish_mode in _MODE_PROMPTS:
        prompt = _MODE_PROMPTS[polish_mode].format(chapter_text=chapter_text)
    else:
        # enhance 模式：使用预设的 scene_expansion_prompt
        prompt = prompt_definitions.scene_expansion_prompt.format(
            chapter_text=chapter_text,
            sensuality_level=sensuality_level or "未指定"
        )

    if extra_context:
        prompt = f"===== 参考资料（仅供参考，不要在输出中包含这些资料本身） =====\n{extra_context}\n===== 参考资料结束 =====\n\n{prompt}"
    if polish_guidance:
        prompt = f"【润色建议】\n{polish_guidance}\n\n{prompt}"
    if writing_style:
        prompt = f"【文风要求】\n{writing_style}\n\n{prompt}"
    if narrative_instruction:
        prompt = f"\n【叙事风格指导-章节层】\n{narrative_instruction}\n\n" + prompt
    # 若为规则润色模式，在 prompt 前注入确定性脚本预检报告
    if polish_mode == "rule_polish":
        try:
            from novel_generator.pipeline_rules import DeterministicRuleChecker
            pre_report = DeterministicRuleChecker.run_full_script_audit(text_zh=chapter_text)
            pre_text = DeterministicRuleChecker.format_script_report_as_text(pre_report)
            prompt = f"【润色前确定性脚本初检报告（供重点整改参考）】:\n{pre_text}\n\n" + prompt
        except Exception:
            pass

    expanded_text = invoke_with_cleaning(llm_adapter, prompt, progress=progress)
    final_output = expanded_text if expanded_text else chapter_text

    # 若为规则润色模式，后验脚本检测并自动追加配额剩余统计到修改清单
    if polish_mode == "rule_polish" and final_output:
        try:
            from novel_generator.pipeline_rules import DeterministicRuleChecker
            post_report = DeterministicRuleChecker.run_full_script_audit(text_zh=final_output)
            post_text = DeterministicRuleChecker.format_script_report_as_text(post_report)
            if "【修改清单】" in final_output:
                final_output = final_output + f"\n\n{post_text}"
            elif "修改清单" in final_output:
                final_output = final_output + f"\n\n{post_text}"
            else:
                final_output = final_output + f"\n\n【修改清单】\n{post_text}"
        except Exception:
            pass

    return final_output

def enrich_chapter_text(
    chapter_text: str,
    word_number: int,
    api_key: str,
    base_url: str,
    model_name: str,
    temperature: float,
    interface_format: str,
    max_tokens: int,
    timeout: int=600,
    progress=None
) -> str:
    """
    对章节文本进行扩写，使其更接近 word_number 字数，保持剧情连贯。
    """
    llm_adapter = create_llm_adapter(
        interface_format=interface_format,
        base_url=base_url,
        model_name=model_name,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout
    )
    prompt = f"""以下章节文本较短，请在保持剧情连贯的前提下进行扩写，使其更充实，接近 {word_number} 字左右，仅给出最终文本，不要解释任何内容。：
原内容：
{chapter_text}
"""
    enriched_text = invoke_with_cleaning(llm_adapter, prompt, progress=progress)
    return enriched_text if enriched_text else chapter_text
