# api/routers/generate.py
# -*- coding: utf-8 -*-
"""生成路由（全部使用 SSE 流式输出）"""

import os
import glob
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, PlainTextResponse

from api.schemas import (
    GenerateArchRequest, GenerateArchStepRequest, AssembleArchRequest,
    ContinueArchRequest, ContinueArchStepRequest, AssembleContinuationRequest,
    CompressContextRequest,
    GenerateBlueprintRequest, GenerateChapterRequest,
    FinalizeChapterRequest, ExpandScenesRequest, SaveChapterRequest,
    SaveContentRequest, GenerateCharStateRequest, BatchGenerateRequest,
    SupplementCharactersRequest, HumanizerRequest, BatchHumanizerRequest,
    ReviseStepRequest, GenerateDetailedOutlineRequest,
    GenerateBlueprintSingleRequest, GenerateOutlineSingleRequest,
    GenerateChapterImprovRequest, SaveSingleContentRequest,
    ReviseBlueprintSingleRequest, ReviseOutlineSingleRequest,
)
from pydantic import BaseModel as _BaseModel
from api.app_state import get_web_app
from api.sse_utils import run_with_sse, cancel_operation
from utils import read_file, save_string_to_txt
from novel_generator.architecture import (
    read_core_seed, read_character_dynamics, read_world_building,
    read_plot_architecture, read_character_state,
    save_core_seed, save_character_dynamics, save_world_building,
    save_plot_architecture, regenerate_assembled_view,
)

router = APIRouter(tags=["generate"])


class _CancelRequest(_BaseModel):
    operation_id: str


@router.post("/generate/cancel")
def cancel_generation(body: _CancelRequest):
    found = cancel_operation(body.operation_id)
    return {"cancelled": found}


def _sse_response(gen):
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _get_workflow_mode(filepath: str) -> str:
    """读取项目工作流模式。无配置文件则返回 outlined。"""
    import json
    cfg_path = os.path.join(filepath, "project_config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f).get("workflow_mode", "outlined")
        except Exception:
            return "outlined"
    return "outlined"


def _require_outlined_mode(filepath: str, action: str) -> None:
    """全书规划类操作的兜底：即兴模式拒绝"""
    if _get_workflow_mode(filepath) == "improv":
        raise HTTPException(
            status_code=409,
            detail=f"当前项目处于即兴模式（improv），不允许执行「{action}」。请切换到大纲模式（outlined）后重试。",
        )


def _require_improv_mode(filepath: str, action: str) -> None:
    """即兴模式专用操作的兜底：大纲模式拒绝"""
    if _get_workflow_mode(filepath) != "improv":
        raise HTTPException(
            status_code=409,
            detail=f"当前项目处于大纲模式（outlined），不允许执行「{action}」。请切换到即兴模式（improv）后重试。",
        )


# ── 完整架构生成 ──────────────────────────────────────────────────────────────

@router.post("/generate/architecture")
def generate_architecture(body: GenerateArchRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.generate_architecture,
            body.llm_config_name, body.topic, body.genre,
            body.num_chapters, body.word_number, body.filepath,
            body.user_guidance, body.arch_style_name, body.xp_type,
            body.num_characters,
        ):
            yield chunk

    return _sse_response(_gen())


# ── 分步架构生成 ──────────────────────────────────────────────────────────────

@router.post("/generate/architecture/step/core_seed")
def generate_step_core_seed(body: GenerateArchStepRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.generate_step_core_seed,
            body.llm_config_name, body.topic, body.genre,
            body.num_chapters, body.word_number,
            body.step_guidance, body.global_guidance, body.xp_type,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/generate/architecture/step/characters")
def generate_step_characters(body: GenerateArchStepRequest):
    """仅生成角色动力学"""
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.generate_step_char_dynamics,
            body.llm_config_name, body.seed_text,
            body.step_guidance, body.global_guidance, body.xp_type,
            body.num_characters,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/generate/architecture/supplement_characters")
def supplement_characters_endpoint(body: SupplementCharactersRequest):
    """基于已有角色补充生成新角色"""
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.supplement_characters_gen,
            body.llm_config_name, body.existing_characters,
            body.supplement_guidance, body.num_characters,
            body.core_seed, body.world_building, body.filepath,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/generate/architecture/step/char_state")
def generate_step_char_state(body: GenerateCharStateRequest):
    """根据角色动力学生成角色状态"""
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.generate_step_char_state,
            body.llm_config_name, body.char_dynamics_text,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/generate/architecture/step/world")
def generate_step_world(body: GenerateArchStepRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.generate_step_world,
            body.llm_config_name, body.seed_text,
            body.step_guidance, body.global_guidance, body.xp_type,
            body.char_text,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/generate/architecture/step/plot")
def generate_step_plot(body: GenerateArchStepRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.generate_step_plot,
            body.llm_config_name, body.seed_text, body.char_text, body.world_text,
            body.step_guidance, body.global_guidance, body.num_chapters,
            body.arch_style_name, body.xp_type,
        ):
            yield chunk

    return _sse_response(_gen())


# ── 修订步骤内容 ──────────────────────────────────────────────────────────────

@router.post("/generate/architecture/step/revise")
def revise_step_content(body: ReviseStepRequest):
    """基于已有内容 + 修改建议，让 LLM 修订内容"""
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.revise_step_content,
            body.llm_config_name, body.original_content,
            body.revision_guidance, body.step_type,
            body.filepath,
            body.include_core_seed, body.include_characters,
            body.include_world_building, body.include_plot,
        ):
            yield chunk

    return _sse_response(_gen())


# ── 组装架构 ──────────────────────────────────────────────────────────────────

@router.post("/generate/architecture/assemble")
def assemble_architecture(body: AssembleArchRequest):
    app = get_web_app()
    status, content = app.assemble_and_save_architecture(
        body.filepath, body.topic, body.genre, body.num_chapters,
        body.word_number, body.seed_text, body.char_text,
        body.char_state_text, body.world_text, body.plot_text
    )
    if status.startswith("❌"):
        raise HTTPException(status_code=400, detail=status)
    return {"message": status, "content": content}


# ── 加载分步缓存 ──────────────────────────────────────────────────────────────

@router.get("/generate/architecture/partial")
def load_partial_steps(filepath: str):
    app = get_web_app()
    status, seed, char, world, plot = app.load_partial_steps(filepath)
    return {
        "message": status,
        "seed_text": seed,
        "char_text": char,
        "world_text": world,
        "plot_text": plot,
    }


# ── 续写章节弧 ────────────────────────────────────────────────────────────────

@router.post("/generate/architecture/continue")
def continue_architecture(body: ContinueArchRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.continue_architecture,
            body.llm_config_name, body.filepath,
            body.new_chapters, body.user_guidance,
            body.arch_style_name, body.xp_type,
            body.num_characters,
        ):
            yield chunk

    return _sse_response(_gen())


# ── 续写分步 ──────────────────────────────────────────────────────────────────

@router.post("/generate/architecture/continue/step/seed")
def continue_step_seed(body: ContinueArchStepRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.continue_step_seed,
            body.llm_config_name, body.filepath,
            body.new_chapters, body.user_guidance,
            body.arch_style_name, body.xp_type,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/generate/architecture/continue/step/world")
def continue_step_world(body: ContinueArchStepRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.continue_step_world,
            body.llm_config_name, body.filepath,
            body.continuation_seed, body.new_chapters,
            body.user_guidance, body.arch_style_name, body.xp_type,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/generate/architecture/continue/step/characters")
def continue_step_characters(body: ContinueArchStepRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.continue_step_characters,
            body.llm_config_name, body.filepath,
            body.new_chapters, body.user_guidance, body.step_guidance,
            body.arch_style_name, body.xp_type,
            body.continuation_seed, body.world_expansion,
            body.num_characters,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/generate/architecture/continue/step/arcs")
def continue_step_arcs(body: ContinueArchStepRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.continue_step_arcs,
            body.llm_config_name, body.filepath,
            body.new_characters_text, body.new_chapters,
            body.user_guidance, body.step_guidance,
            body.arch_style_name, body.xp_type,
            body.continuation_seed, body.world_expansion,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/generate/architecture/continue/step/char_state")
def continue_step_char_state(body: ContinueArchStepRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.continue_step_char_state,
            body.llm_config_name, body.filepath,
            body.new_characters_text,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/generate/architecture/continue/assemble")
def assemble_continuation(body: AssembleContinuationRequest):
    app = get_web_app()
    status, content = app.assemble_and_save_continuation(
        body.filepath, body.new_chapters, body.new_characters_text,
        body.new_arcs_text, body.new_char_state_text,
        body.continuation_seed, body.world_expansion,
    )
    if status.startswith("❌"):
        raise HTTPException(status_code=400, detail=status)
    # 从已更新的项目数据中读取新总章节数
    new_total = None
    active = app.get_active_project_name()
    if active and active in app.projects_data.get("projects", {}):
        new_total = app.projects_data["projects"][active].get("num_chapters")
    resp = {"message": status, "content": content}
    if new_total:
        resp["new_total_chapters"] = new_total
    return resp


# ── 压缩摘要/角色状态 ─────────────────────────────────────────────────────────

@router.post("/generate/compress-context")
def compress_context(body: CompressContextRequest):
    app = get_web_app()
    result = app.compress_context(body.llm_config_name, body.filepath, body.include_world_building)
    if result.startswith("❌"):
        raise HTTPException(status_code=400, detail=result)
    return {"message": result}


# ── 蓝图生成 ──────────────────────────────────────────────────────────────────

@router.post("/generate/blueprint")
def generate_blueprint(body: GenerateBlueprintRequest):
    _require_outlined_mode(body.filepath, "生成全书章节蓝图")
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.generate_blueprint,
            body.llm_config_name, body.filepath, body.num_chapters,
            body.user_guidance, body.bp_style_name, body.xp_type,
        ):
            yield chunk

    return _sse_response(_gen())


# ── 详细细纲 ──────────────────────────────────────────────────────────────────

@router.post("/generate/detailed_outline")
def generate_detailed_outline(body: GenerateDetailedOutlineRequest):
    _require_outlined_mode(body.filepath, "生成全书章节细纲")
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.generate_detailed_outline,
            body.llm_config_name, body.filepath,
            body.start_chapter, body.end_chapter, body.num_chapters,
            body.user_guidance, body.xp_type, body.outline_mode,
        ):
            yield chunk

    return _sse_response(_gen())


@router.get("/generate/detailed_outline")
def get_detailed_outline(filepath: str = "./output"):
    outline_file = os.path.join(filepath, "Novel_detailed_outline.txt")
    if os.path.exists(outline_file):
        content = read_file(outline_file)
        return {"content": content}
    return {"content": ""}


@router.put("/generate/detailed_outline")
def save_detailed_outline(body: SaveContentRequest):
    outline_file = os.path.join(body.filepath, "Novel_detailed_outline.txt")
    os.makedirs(os.path.dirname(outline_file) if os.path.dirname(outline_file) else ".", exist_ok=True)
    save_string_to_txt(body.content, outline_file)
    return {"message": "✅ 章节细纲已保存"}


# ── 章节生成 ──────────────────────────────────────────────────────────────────

@router.post("/generate/chapter")
def generate_chapter(body: GenerateChapterRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.generate_chapter,
            body.llm_config_name, body.emb_config_name, body.filepath,
            body.chapter_num, body.word_number, body.user_guidance,
            body.characters_involved, body.key_items,
            body.scene_location, body.time_constraint,
            body.style_name, body.narrative_style_name, body.xp_type,
            body.inject_world_building, body.scene_by_scene,
        ):
            yield chunk

    return _sse_response(_gen())


@router.put("/generate/chapter/{num}")
def save_chapter(num: int, body: SaveChapterRequest, filepath: str = "./output"):
    chapter_file = os.path.join(filepath, "chapters", f"chapter_{num}.txt")
    os.makedirs(os.path.dirname(chapter_file), exist_ok=True)
    save_string_to_txt(body.content, chapter_file)
    return {"message": f"✅ 第 {num} 章已保存"}


@router.put("/generate/architecture")
def save_architecture(body: SaveContentRequest):
    """已废弃：架构文件现在是只读组装副本，请编辑各独立组件。"""
    raise HTTPException(status_code=405, detail="架构文件现在是只读的，请编辑各独立组件（PUT /generate/architecture/component/{name}）。")


@router.put("/generate/architecture/component/{component_name}")
def save_architecture_component(component_name: str, body: SaveContentRequest):
    """保存单个架构组件到独立文件，然后重新组装 Novel_architecture.txt。"""
    filepath = body.filepath
    os.makedirs(filepath, exist_ok=True)

    save_funcs = {
        "core_seed": lambda: save_core_seed(filepath, body.content),
        "character_dynamics": lambda: save_character_dynamics(filepath, body.content),
        "world_building": lambda: save_world_building(filepath, body.content),
        "plot_architecture": lambda: save_plot_architecture(filepath, body.content),
        "character_state": lambda: save_string_to_txt(
            body.content,
            os.path.join(filepath, "character_state.txt"),
        ),
    }

    if component_name not in save_funcs:
        raise HTTPException(
            status_code=400,
            detail=f"未知组件: {component_name}。可用: {', '.join(save_funcs.keys())}",
        )

    save_funcs[component_name]()
    assembled = regenerate_assembled_view(filepath)
    return {"message": f"✅ {component_name} 已保存", "assembled_content": assembled}


@router.put("/generate/blueprint")
def save_blueprint(body: SaveContentRequest):
    bp_file = os.path.join(body.filepath, "Novel_directory.txt")
    os.makedirs(os.path.dirname(bp_file), exist_ok=True)
    save_string_to_txt(body.content, bp_file)
    return {"message": "✅ 蓝图已保存"}


@router.get("/generate/chapter/{num}")
def get_chapter(num: int, filepath: str = "./output"):
    chapter_file = os.path.join(filepath, "chapters", f"chapter_{num}.txt")
    if not os.path.exists(chapter_file):
        raise HTTPException(status_code=404, detail=f"未找到第 {num} 章文件")
    return {"content": read_file(chapter_file), "chapter_num": num}


# ── 章节列表 ──────────────────────────────────────────────────────────────────

@router.get("/generate/chapters")
def list_chapters(filepath: str = "./output"):
    chapters_dir = os.path.join(filepath, "chapters")
    if not os.path.exists(chapters_dir):
        return {"chapters": []}

    all_files = glob.glob(os.path.join(chapters_dir, "chapter_*.txt"))
    chapter_nums = set()
    for f in all_files:
        match = re.search(r'chapter_(\d+)', os.path.basename(f))
        if match:
            chapter_nums.add(int(match.group(1)))

    result = []
    for num in sorted(chapter_nums):
        draft_file = os.path.join(chapters_dir, f"chapter_{num}_draft.txt")
        final_file = os.path.join(chapters_dir, f"chapter_{num}.txt")
        result.append({
            "num": num,
            "has_draft": os.path.exists(draft_file),
            "has_final": os.path.exists(final_file),
        })
    return {"chapters": result}


@router.get("/generate/dashboard")
def get_project_dashboard(filepath: str = "./output"):
    arch_file = os.path.join(filepath, "Novel_architecture.txt")
    bp_file = os.path.join(filepath, "Novel_directory.txt")
    outline_file = os.path.join(filepath, "Novel_detailed_outline.txt")
    summary_file = os.path.join(filepath, "global_summary.txt")
    char_state_file = os.path.join(filepath, "character_state.txt")
    chapters_dir = os.path.join(filepath, "chapters")
    en_dir = os.path.join(filepath, "chapters_en")

    # 1. 蓝图标题
    bp_titles = {}
    if os.path.exists(bp_file):
        try:
            bp_content = read_file(bp_file)
            for m in re.finditer(r'第\s*(\d+)\s*章[：:\s\-—]+([^\r\n]+)', bp_content):
                bp_titles[int(m.group(1))] = m.group(2).strip()
        except Exception:
            pass

    # 2. 细纲章节
    outline_chapters = set()
    if os.path.exists(outline_file):
        try:
            ot_content = read_file(outline_file)
            for m in re.finditer(r'【第\s*(\d+)\s*章细纲】([^\r\n]+)', ot_content):
                num = int(m.group(1))
                outline_chapters.add(num)
                if num not in bp_titles:
                    bp_titles[num] = m.group(2).strip()
        except Exception:
            pass

    # 英文目录检测
    en_titles = {}
    en_json_file = os.path.join(filepath, "Novel_directory_en.json")
    en_txt_file = os.path.join(filepath, "Novel_directory_en.txt")
    if os.path.exists(en_json_file):
        try:
            import json as _json
            with open(en_json_file, 'r', encoding='utf-8') as _f:
                _en_data = _json.load(_f)
                for _item in _en_data:
                    en_titles[_item.get("num")] = _item.get("title_en", "")
        except Exception:
            pass
    elif os.path.exists(en_txt_file):
        try:
            _txt_c = read_file(en_txt_file)
            for _m in re.finditer(r'Chapter\s*(\d+)[：:\s\-—]+([^|\r\n]+)', _txt_c):
                en_titles[int(_m.group(1))] = f"Chapter {_m.group(1)}: {_m.group(2).strip()}"
        except Exception:
            pass

    # 资产状态
    assets = {
        "architecture": {
            "exists": os.path.exists(arch_file),
            "chars": len(read_file(arch_file)) if os.path.exists(arch_file) else 0,
            "label": "小说完整架构",
            "file": "Novel_architecture.txt",
        },
        "blueprint": {
            "exists": os.path.exists(bp_file),
            "total_chapters": len(bp_titles),
            "chars": len(read_file(bp_file)) if os.path.exists(bp_file) else 0,
            "label": "全书蓝图目录",
            "file": "Novel_directory.txt",
        },
        "directory_en": {
            "exists": os.path.exists(en_json_file) or os.path.exists(en_txt_file),
            "total_chapters": len(en_titles),
            "chars": len(read_file(en_txt_file)) if os.path.exists(en_txt_file) else 0,
            "label": "全书英文目录",
            "file": "Novel_directory_en.txt",
        },
        "detailed_outline": {
            "exists": os.path.exists(outline_file),
            "planned_chapters": len(outline_chapters),
            "chars": len(read_file(outline_file)) if os.path.exists(outline_file) else 0,
            "label": "章节精细细纲",
            "file": "Novel_detailed_outline.txt",
        },
        "global_summary": {
            "exists": bool(read_file(summary_file).strip()) if os.path.exists(summary_file) else False,
            "chars": len(read_file(summary_file).strip()) if os.path.exists(summary_file) else 0,
            "label": "全局前文记忆",
            "file": "global_summary.txt",
        },
        "character_state": {
            "exists": bool(read_file(char_state_file).strip()) if os.path.exists(char_state_file) else False,
            "chars": len(read_file(char_state_file).strip()) if os.path.exists(char_state_file) else 0,
            "label": "角色能力状态库",
            "file": "character_state.txt",
        },
    }

    # 3. 收集所有章节
    all_nums = set()
    if os.path.exists(chapters_dir):
        for f in glob.glob(os.path.join(chapters_dir, "chapter_*.txt")):
            m = re.search(r'chapter_(\d+)', os.path.basename(f))
            if m:
                all_nums.add(int(m.group(1)))
    all_nums.update(bp_titles.keys())
    all_nums.update(outline_chapters)
    if not all_nums:
        all_nums.add(1)

    chapters_list = []
    for num in sorted(all_nums):
        draft_file = os.path.join(chapters_dir, f"chapter_{num}_draft.txt")
        final_file = os.path.join(chapters_dir, f"chapter_{num}.txt")
        en_file = os.path.join(en_dir, f"chapter_{num}_en.txt")

        has_final = os.path.exists(final_file)
        has_draft = os.path.exists(draft_file)
        ch_file_to_read = final_file if has_final else (draft_file if has_draft else None)
        ch_content = read_file(ch_file_to_read) if ch_file_to_read else ""
        ch_chars = len(ch_content.strip()) if ch_content else 0

        has_en = os.path.exists(en_file)
        en_content = read_file(en_file).strip() if has_en else ""
        en_words = len(en_content.split()) if en_content else 0

        title = bp_titles.get(num, f"第 {num} 章")
        title_en = en_titles.get(num, "")

        chapters_list.append({
            "num": num,
            "title": title,
            "title_en": title_en,
            "has_draft": bool(ch_chars > 0),
            "chars": ch_chars,
            "has_final": has_final,
            "has_en": has_en,
            "en_words": en_words,
            "has_outline": (num in outline_chapters),
        })

    return {
        "project_name": os.path.basename(os.path.normpath(filepath)),
        "filepath": filepath,
        "assets": assets,
        "chapters": chapters_list,
    }


# ── 精炼章节 ──────────────────────────────────────────────────────────────────

@router.post("/generate/finalize")
def finalize_chapter(body: FinalizeChapterRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.finalize_chapter_web,
            body.llm_config_name, body.emb_config_name, body.filepath,
            body.chapter_num, body.word_number,
        ):
            yield chunk

    return _sse_response(_gen())


# ── 场景扩写 ──────────────────────────────────────────────────────────────────

@router.post("/generate/expand")
def expand_scenes(body: ExpandScenesRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.expand_scenes_web,
            body.llm_config_name, body.filepath, body.chapter_num,
            body.style_name, body.narrative_style_name, body.xp_type,
            body.polish_guidance, body.polish_mode,
            body.include_outline, body.include_character_state,
            body.include_summary, body.include_world_building,
        ):
            yield chunk

    return _sse_response(_gen())


# ── 去 AI 痕迹 ──────────────────────────────────────────────────────────────

@router.post("/generate/humanize")
def humanize_chapter(body: HumanizerRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.humanize_chapter_web,
            body.llm_config_name, body.filepath, body.chapter_num,
            body.enable_r8, body.user_focus, body.depth,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/generate/humanize/batch")
def batch_humanize(body: BatchHumanizerRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.batch_humanize_web,
            body.llm_config_name, body.filepath,
            body.start_chapter, body.end_chapter,
            body.enable_r8, body.user_focus, body.depth,
        ):
            yield chunk

    return _sse_response(_gen())


class TranslateChapterRequest(_BaseModel):
    llm_config_name: str
    filepath: str = "./output"
    chapter_num: int
    target_style: str = "Alpha Romance (GoodNovel / Dreame 爆款标准)"
    custom_guidance: str = ""


@router.post("/generate/translate")
def translate_chapter(body: TranslateChapterRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.translate_chapter_web,
            body.llm_config_name, body.filepath, body.chapter_num,
            body.target_style, body.custom_guidance,
        ):
            yield chunk

    return _sse_response(_gen())


@router.get("/generate/chapter_en/{num}")
def get_chapter_en(num: int, filepath: str = "./output"):
    en_file = os.path.join(filepath, "chapters_en", f"chapter_{num}_en.txt")
    if not os.path.exists(en_file):
        raise HTTPException(status_code=404, detail=f"未找到第 {num} 章英文文件")
    return {"content": read_file(en_file), "chapter_num": num}


@router.put("/generate/chapter_en/{num}")
def save_chapter_en(num: int, body: SaveChapterRequest, filepath: str = "./output"):
    en_dir = os.path.join(filepath, "chapters_en")
    os.makedirs(en_dir, exist_ok=True)
    en_file = os.path.join(en_dir, f"chapter_{num}_en.txt")
    save_string_to_txt(body.content, en_file)
    return {"message": f"✅ 第 {num} 章英文译文已保存至 {en_file}"}

@router.get("/generate/chapter_artifacts/{num}")
def get_chapter_artifacts(num: int, filepath: str = "./output"):
    """获取指定章节的全套流水线产物快照（草稿、润色、修改清单、英文译稿、全书摘要与角色状态等）"""
    chapters_dir = os.path.join(filepath, "chapters")
    en_dir = os.path.join(filepath, "chapters_en")

    raw_draft_path = os.path.join(chapters_dir, f"chapter_{num}_raw_draft.txt")
    polished_path = os.path.join(chapters_dir, f"chapter_{num}.txt")
    checklist_path = os.path.join(chapters_dir, f"chapter_{num}_polish_checklist.txt")
    en_path = os.path.join(en_dir, f"chapter_{num}_en.txt")
    summary_path = os.path.join(filepath, "global_summary.txt")
    char_state_path = os.path.join(filepath, "character_state.txt")

    raw_draft = read_file(raw_draft_path) if os.path.exists(raw_draft_path) else ""
    polished = read_file(polished_path) if os.path.exists(polished_path) else ""
    checklist = read_file(checklist_path) if os.path.exists(checklist_path) else ""
    en_text = read_file(en_path) if os.path.exists(en_path) else ""
    summary = read_file(summary_path) if os.path.exists(summary_path) else ""
    char_state = read_file(char_state_path) if os.path.exists(char_state_path) else ""

    return {
        "chapter_num": num,
        "draft": raw_draft or polished,
        "polished": polished,
        "checklist": checklist,
        "translation": en_text,
        "summary": summary,
        "character_state": char_state,
        "has_en": bool(en_text),
        "has_polished": bool(polished),
    }


class SaveDirectoryEnRequest(_BaseModel):
    filepath: str = "./output"
    chapters: list = []
    raw_text: str = ""


class TranslateDirectoryRequest(_BaseModel):
    llm_config_name: str
    filepath: str = "./output"
    target_style: str = "Alpha Romance (GoodNovel / Dreame 爆款标准)"
    custom_guidance: str = ""


@router.get("/generate/directory_en")
def get_directory_en(filepath: str = "./output"):
    import json
    json_path = os.path.join(filepath, "Novel_directory_en.json")
    txt_path = os.path.join(filepath, "Novel_directory_en.txt")
    zh_path = os.path.join(filepath, "Novel_directory.txt")

    chapters = []
    raw_text = ""
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                chapters = json.load(f)
        except Exception:
            pass

    if os.path.exists(txt_path):
        try:
            raw_text = read_file(txt_path)
        except Exception:
            pass

    # 若尚未生成英文目录，从中文蓝图目录自动解析出章节骨架
    if not chapters and os.path.exists(zh_path):
        try:
            zh_content = read_file(zh_path)
            for m in re.finditer(r'第\s*(\d+)\s*章[：:\s\-—]+([^\r\n]+)', zh_content):
                cnum = int(m.group(1))
                ctitle = m.group(2).strip()
                chapters.append({
                    "num": cnum,
                    "title_zh": ctitle,
                    "title_en": f"Chapter {cnum}: {ctitle}",
                    "title_en_clean": ctitle,
                    "summary": ""
                })
        except Exception:
            pass

    return {
        "chapters": chapters,
        "raw_text": raw_text
    }


@router.put("/generate/directory_en")
def save_directory_en(body: SaveDirectoryEnRequest):
    import json
    filepath = body.filepath
    os.makedirs(filepath, exist_ok=True)
    json_path = os.path.join(filepath, "Novel_directory_en.json")
    txt_path = os.path.join(filepath, "Novel_directory_en.txt")

    if body.chapters:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(body.chapters, f, ensure_ascii=False, indent=2)

        lines = []
        for ch in body.chapters:
            num = ch.get("num", 0)
            en = ch.get("title_en", f"Chapter {num}")
            zh = ch.get("title_zh", "")
            lines.append(f"{en} | {zh}")
        raw_text = "\n".join(lines) + "\n"
        save_string_to_txt(raw_text, txt_path)
    elif body.raw_text:
        save_string_to_txt(body.raw_text, txt_path)

    return {"message": "✅ 全书英文章名目录已成功保存！"}


@router.post("/generate/translate_directory")
def translate_directory(body: TranslateDirectoryRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.translate_directory_web,
            body.llm_config_name, body.filepath,
            body.target_style, body.custom_guidance,
        ):
            yield chunk

    return _sse_response(_gen())


class AuditTranslationRequest(_BaseModel):
    llm_config_name: str
    filepath: str = "./output"
    chapter_num: int


@router.post("/generate/audit_translation")
def audit_translation(body: AuditTranslationRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.audit_translation_web,
            body.llm_config_name, body.filepath, body.chapter_num
        ):
            yield chunk

    return _sse_response(_gen())


class PipelineChapterRequest(_BaseModel):
    llm_config_name: str
    emb_config_name: str = ""
    filepath: str = "./output"
    chapter_num: int
    word_number: int = 3000
    user_guidance: str = ""
    characters_involved: str = ""
    key_items: str = ""
    scene_location: str = ""
    time_constraint: str = ""
    style_name: str = ""
    narrative_style_name: str = ""
    xp_type: str = ""
    target_style: str = "Alpha Romance (GoodNovel / Dreame 爆款标准)"
    auto_retry_translation: bool = True
    scene_by_scene: bool = True
    pipeline_mode: str = "fast_zh"
    review_strength: str = "strong"
    inject_world_building: bool = True
    inject_summary: bool = True
    inject_char_state: bool = True
    inject_canon: bool = True


@router.get("/generate/chapter_context_preview")
def get_chapter_context_preview(chapter_num: int, filepath: str = "./output"):
    """预览某章流水线执行前将注入的所有上下游上下文依赖（透明化输入展示）。"""
    import json as _json
    bp_file = os.path.join(filepath, "Novel_directory.txt")
    outline_file = os.path.join(filepath, "Novel_detailed_outline.txt")
    summary_file = os.path.join(filepath, "global_summary.txt")
    canon_file = os.path.join(filepath, "Novel_canon_history.txt")

    bp_info = {}
    bp_raw_text = ""
    if os.path.exists(bp_file):
        try:
            from novel_generator.blueprint import get_chapter_info_from_blueprint
            bp_info = get_chapter_info_from_blueprint(read_file(bp_file), chapter_num) or {}
            if bp_info:
                parts = []
                if bp_info.get("chapter_title"):
                    parts.append(f"标题：{bp_info.get('chapter_title')}")
                if bp_info.get("chapter_role"):
                    parts.append(f"定位：{bp_info.get('chapter_role')}")
                if bp_info.get("chapter_purpose"):
                    parts.append(f"作用：{bp_info.get('chapter_purpose')}")
                if bp_info.get("characters_involved"):
                    parts.append(f"出场人物：{bp_info.get('characters_involved')}")
                if bp_info.get("chapter_summary"):
                    parts.append(f"章节梗概：{bp_info.get('chapter_summary')}")
                bp_raw_text = "\n".join(parts)
        except Exception:
            pass

    outline_text = ""
    if os.path.exists(outline_file):
        try:
            from novel_generator.detailed_outline import get_chapter_outline
            outline_text = (get_chapter_outline(read_file(outline_file), chapter_num) or "").strip()
        except Exception:
            pass

    summary_text = read_file(summary_file).strip() if os.path.exists(summary_file) else ""
    char_state_text = (read_character_state(filepath) or "").strip()
    world_text = (read_world_building(filepath) or "").strip()
    canon_text = read_file(canon_file).strip() if os.path.exists(canon_file) else ""

    handoff_text = ""
    handoff_dict = None
    if chapter_num > 1:
        try:
            from novel_generator.continuity import get_semantic_handoff
            h_obj = get_semantic_handoff(filepath, chapter_num - 1)
            if h_obj:
                handoff_dict = h_obj.to_dict()
                handoff_text = _json.dumps(handoff_dict, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _pack(label: str, content: str):
        c = content or ""
        return {
            "label": label,
            "exists": bool(c.strip()),
            "chars": len(c),
            "content": c,
        }

    return {
        "chapter_num": chapter_num,
        "blueprint_info": bp_info,
        "items": {
            "blueprint": _pack("目录简纲", bp_raw_text),
            "outline": _pack("本章细纲", outline_text),
            "handoff": {**_pack("上章因果交接 (Handoff)", handoff_text), "data": handoff_dict},
            "global_summary": _pack("前文全局摘要", summary_text),
            "character_state": _pack("角色能力与状态表", char_state_text),
            "world_building": _pack("世界观与设定", world_text),
            "canon_history": _pack("已发生正史约束", canon_text),
        },
    }


@router.post("/generate/pipeline_chapter")
def pipeline_chapter(body: PipelineChapterRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.pipeline_chapter_web,
            body.llm_config_name,
            body.emb_config_name,
            body.filepath,
            body.chapter_num,
            body.word_number,
            body.user_guidance,
            body.characters_involved,
            body.key_items,
            body.scene_location,
            body.time_constraint,
            body.style_name if body.style_name and body.style_name != "不使用文风" else None,
            body.narrative_style_name if body.narrative_style_name and body.narrative_style_name != "不使用文风" else None,
            body.xp_type,
            body.target_style,
            body.auto_retry_translation,
            body.scene_by_scene,
            body.pipeline_mode,
            body.review_strength,
            body.inject_world_building,
            body.inject_summary,
            body.inject_char_state,
            body.inject_canon,
        ):
            yield chunk

    return _sse_response(_gen())


# ── 一键生成全部章节 ──────────────────────────────────────────────────────────

@router.post("/generate/batch")
def batch_generate(body: BatchGenerateRequest):
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.batch_generate_all,
            body.llm_config_name, body.emb_config_name, body.filepath,
            body.word_number, body.user_guidance,
            body.style_name, body.narrative_style_name, body.xp_type,
            body.inject_world_building,
        ):
            yield chunk

    return _sse_response(_gen())


# ── 生成状态 ──────────────────────────────────────────────────────────────────

@router.get("/generate/status")
def get_generate_status(filepath: str = "./output"):
    arch_exists = os.path.exists(os.path.join(filepath, "Novel_architecture.txt"))
    bp_exists = os.path.exists(os.path.join(filepath, "Novel_directory.txt"))
    cd_exists = os.path.exists(os.path.join(filepath, "character_dynamics.txt"))

    arch_content = ""
    bp_content = ""
    cd_content = ""
    if arch_exists:
        arch_content = read_file(os.path.join(filepath, "Novel_architecture.txt"))
    if bp_exists:
        bp_content = read_file(os.path.join(filepath, "Novel_directory.txt"))
    if cd_exists:
        cd_content = read_file(os.path.join(filepath, "character_dynamics.txt"))

    # 读取各独立文件内容
    core_seed_content = read_core_seed(filepath)
    world_building_content = read_world_building(filepath)
    plot_architecture_content = read_plot_architecture(filepath)
    character_state_content = read_character_state(filepath)

    return {
        "architecture_exists": arch_exists or bool(core_seed_content),
        "blueprint_exists": bp_exists,
        "architecture_content": arch_content,
        "blueprint_content": bp_content,
        "character_dynamics_exists": cd_exists,
        "character_dynamics_content": cd_content,
        "core_seed_content": core_seed_content,
        "world_building_content": world_building_content,
        "plot_architecture_content": plot_architecture_content,
        "character_state_content": character_state_content,
    }


@router.put("/generate/character_dynamics")
def save_character_dynamics_endpoint(body: SaveContentRequest):
    cd_file = os.path.join(body.filepath, "character_dynamics.txt")
    os.makedirs(os.path.dirname(cd_file), exist_ok=True)
    save_string_to_txt(body.content, cd_file)
    return {"message": "✅ 角色动力学已保存"}


# ── 即兴写作模式（improv） ────────────────────────────────────────────────────

@router.get("/generate/workflow_mode")
def get_workflow_mode(filepath: str = "./output"):
    """读取当前项目的工作流模式（outlined / improv）"""
    return {"workflow_mode": _get_workflow_mode(filepath)}


@router.post("/generate/blueprint_single")
def generate_blueprint_single(body: GenerateBlueprintSingleRequest):
    """即兴模式·按章生成单章蓝图（不直接保存，前端确认后调 PUT 保存）"""
    _require_improv_mode(body.filepath, "生成单章蓝图")
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.generate_chapter_blueprint_single_web,
            body.llm_config_name, body.filepath,
            body.chapter_num, body.chapter_intent, body.word_number,
        ):
            yield chunk

    return _sse_response(_gen())


@router.get("/generate/blueprint_single/{num}")
def get_blueprint_single(num: int, filepath: str = "./output"):
    from novel_generator.improv import get_single_blueprint_path
    p = get_single_blueprint_path(filepath, num)
    if not os.path.exists(p):
        return {"content": "", "exists": False}
    return {"content": read_file(p), "exists": True}


@router.put("/generate/blueprint_single/{num}")
def save_blueprint_single(num: int, body: SaveSingleContentRequest):
    from novel_generator.improv import save_single_blueprint
    save_single_blueprint(body.filepath, num, body.content)
    return {"message": f"✅ 第 {num} 章蓝图已保存"}


@router.post("/generate/outline_single")
def generate_outline_single(body: GenerateOutlineSingleRequest):
    """即兴模式·按章生成单章细纲（基于已保存的单章蓝图）"""
    _require_improv_mode(body.filepath, "生成单章细纲")
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.generate_chapter_outline_single_web,
            body.llm_config_name, body.filepath,
            body.chapter_num, body.word_number,
        ):
            yield chunk

    return _sse_response(_gen())


@router.get("/generate/outline_single/{num}")
def get_outline_single(num: int, filepath: str = "./output"):
    from novel_generator.improv import get_single_outline_path
    p = get_single_outline_path(filepath, num)
    if not os.path.exists(p):
        return {"content": "", "exists": False}
    return {"content": read_file(p), "exists": True}


@router.put("/generate/outline_single/{num}")
def save_outline_single(num: int, body: SaveSingleContentRequest):
    from novel_generator.improv import save_single_outline
    save_single_outline(body.filepath, num, body.content)
    return {"message": f"✅ 第 {num} 章细纲已保存"}


@router.post("/generate/blueprint_single/revise")
def revise_blueprint_single(body: ReviseBlueprintSingleRequest):
    """即兴模式·按修订建议重写单章蓝图"""
    _require_improv_mode(body.filepath, "修订单章蓝图")
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.revise_chapter_blueprint_single_web,
            body.llm_config_name, body.filepath, body.chapter_num,
            body.current_blueprint, body.revision_guidance,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/generate/outline_single/revise")
def revise_outline_single(body: ReviseOutlineSingleRequest):
    """即兴模式·按修订建议重写单章细纲"""
    _require_improv_mode(body.filepath, "修订单章细纲")
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.revise_chapter_outline_single_web,
            body.llm_config_name, body.filepath, body.chapter_num,
            body.current_outline, body.revision_guidance,
        ):
            yield chunk

    return _sse_response(_gen())


@router.post("/generate/chapter_improv")
def generate_chapter_improv(body: GenerateChapterImprovRequest):
    """即兴模式·章节正文生成（依赖单章蓝图）"""
    _require_improv_mode(body.filepath, "即兴模式生成章节正文")
    app = get_web_app()

    async def _gen():
        async for chunk in run_with_sse(
            app.generate_chapter_improv_web,
            body.llm_config_name, body.filepath, body.chapter_num,
            body.word_number, body.user_guidance,
            body.style_name, body.narrative_style_name,
        ):
            yield chunk

    return _sse_response(_gen())


@router.get("/generate/open_threads")
def get_open_threads(filepath: str = "./output"):
    from novel_generator.improv import read_open_threads
    return {"content": read_open_threads(filepath)}


@router.put("/generate/open_threads")
def save_open_threads_endpoint(body: SaveContentRequest):
    from novel_generator.improv import save_open_threads
    save_open_threads(body.filepath, body.content)
    return {"message": "✅ 伏笔池已保存"}


# ── 合并导出小说 ────────────────────────────────────────────────────────────

@router.get("/generate/export")
def export_novel(filepath: str = "./output"):
    """将所有章节合并为一个完整文本，供下载。"""
    from chapter_directory_parser import parse_chapter_blueprint

    chapters_dir = os.path.join(filepath, "chapters")
    if not os.path.exists(chapters_dir):
        raise HTTPException(status_code=404, detail="未找到章节目录")

    # 收集所有章节文件
    all_files = glob.glob(os.path.join(chapters_dir, "chapter_*.txt"))
    chapter_nums = set()
    for f in all_files:
        match = re.search(r'chapter_(\d+)\.txt$', os.path.basename(f))
        if match:
            chapter_nums.add(int(match.group(1)))

    if not chapter_nums:
        raise HTTPException(status_code=404, detail="未找到任何已保存的章节")

    # 尝试从蓝图获取章节标题
    bp_file = os.path.join(filepath, "Novel_directory.txt")
    chapter_titles = {}
    if os.path.exists(bp_file):
        bp_text = read_file(bp_file)
        try:
            parsed = parse_chapter_blueprint(bp_text)
            for ch in parsed:
                chapter_titles[ch["chapter_number"]] = ch.get("chapter_title", "")
        except Exception:
            pass

    # 合并：优先使用章节内容自带的标题，没有时才补上
    parts = []
    for num in sorted(chapter_nums):
        chapter_file = os.path.join(chapters_dir, f"chapter_{num}.txt")
        if not os.path.exists(chapter_file):
            continue
        content = read_file(chapter_file).strip()
        # 检查内容前几行是否已包含章节标题（如"第N章"、"第N章 标题"等）
        first_line = content.split('\n', 1)[0].strip() if content else ""
        has_title = bool(re.match(r'^第\s*\d+\s*章', first_line))
        if has_title:
            parts.append(content)
        else:
            title = chapter_titles.get(num, "")
            header = f"第{num}章" + (f" - {title}" if title else "")
            parts.append(f"{header}\n\n{content}")

    if not parts:
        raise HTTPException(status_code=404, detail="未找到任何已保存的章节")

    merged = "\n\n\n".join(parts)
    return PlainTextResponse(
        content=merged,
        headers={
            "Content-Disposition": "attachment; filename=novel_export.txt",
        },
    )


class UpdateCanonHistoryRequest(_BaseModel):
    llm_config_name: str
    filepath: str
    chapter_num: int


@router.get("/generate/canon_history")
def get_canon_history(filepath: str):
    """读取当前项目的正史设定页、正史规则与更新记录"""
    canon_file = os.path.join(filepath, "Novel_canon_history.txt")
    rules_file = os.path.join(filepath, "Novel_canon_rules.txt")
    changelog_file = os.path.join(filepath, "Novel_canon_changelog.txt")
    canon = read_file(canon_file) if os.path.exists(canon_file) else ""
    rules = read_file(rules_file) if os.path.exists(rules_file) else ""
    changelog = read_file(changelog_file) if os.path.exists(changelog_file) else ""
    return {"canon": canon, "rules": rules, "changelog": changelog}


@router.post("/generate/update_canon_history")
def update_canon_history_api(body: UpdateCanonHistoryRequest):
    """依据本章定稿与正史规则手动触发正史设定页演进更新"""
    app = get_web_app()
    result = app.update_canon_history_web(
        llm_config_name=body.llm_config_name,
        filepath=body.filepath,
        chapter_num=body.chapter_num
    )
    return {"result": result}


# ── 因果连续性与幕间交接（Semantic Handoff & Continuity Engine）路由 ──

class ColdStartBackfillRequest(_BaseModel):
    llm_config_name: str
    filepath: str
    max_chapters: int = None


class PreWriteGateRequest(_BaseModel):
    llm_config_name: str
    filepath: str
    chapter_num: int


class SpanRepairRequest(_BaseModel):
    llm_config_name: str
    filepath: str
    chapter_num: int
    target_span: str
    repair_instruction: str


@router.get("/generate/handoff")
def get_handoff_api(filepath: str, chapter_num: int):
    """获取第 chapter_num 章的幕间因果交接数据（Handoff）"""
    from novel_generator.continuity import get_semantic_handoff
    handoff = get_semantic_handoff(filepath, int(chapter_num))
    return {"handoff": handoff}


@router.post("/generate/cold_start_backfill")
def cold_start_backfill_api(body: ColdStartBackfillRequest):
    """一键从前文历史章节冷启动萃取正史底册与因果交接（解决中途接入割裂感）"""
    app = get_web_app()
    res = app.cold_start_backfill_web(
        llm_config_name=body.llm_config_name,
        filepath=body.filepath,
        max_chapters=body.max_chapters
    )
    return res


@router.post("/generate/pre_write_gate")
def pre_write_gate_api(body: PreWriteGateRequest):
    """大纲级前置因果门禁体检（动笔前低成本拦截冲突）"""
    app = get_web_app()
    res = app.pre_write_gate_web(
        llm_config_name=body.llm_config_name,
        filepath=body.filepath,
        chapter_num=body.chapter_num
    )
    return res


@router.post("/generate/span_repair")
def span_repair_api(body: SpanRepairRequest):
    """局部句子级精准修补（无需推翻整章，单点替换）"""
    app = get_web_app()
    res = app.repair_span_web(
        llm_config_name=body.llm_config_name,
        filepath=body.filepath,
        chapter_num=body.chapter_num,
        target_span=body.target_span,
        repair_instruction=body.repair_instruction
    )
    return res


# ── 小说流水线底层规则与固定写法表路由 ──

class SaveFixedTermsRequest(_BaseModel):
    filepath: str
    content: str


class ScriptAuditRequest(_BaseModel):
    text_zh: str = ""
    text_en: str = ""


@router.get("/generate/fixed_terms")
def get_fixed_terms_api(filepath: str):
    """获取项目的固定写法表内容"""
    from novel_generator.pipeline_rules import ensure_fixed_terms_file
    content = ensure_fixed_terms_file(filepath)
    return {"content": content}


@router.post("/generate/fixed_terms")
def save_fixed_terms_api(body: SaveFixedTermsRequest):
    """保存项目的固定写法表内容"""
    from novel_generator.pipeline_rules import get_fixed_terms_file_path
    p = get_fixed_terms_file_path(body.filepath)
    save_string_to_txt(body.content, p)
    return {"success": True, "message": "固定写法表已保存"}


@router.get("/generate/pipeline_rules")
def get_pipeline_rules_api():
    """获取小说流水线底层规则全文"""
    from novel_generator.pipeline_rules import PIPELINE_RULES_RAW
    return {"rules": PIPELINE_RULES_RAW}


@router.post("/generate/script_audit")
def run_script_audit_api(body: ScriptAuditRequest):
    """直接运行确定性脚本规则检测器（统计禁用词、否定排比、修仙外溢、标签等）"""
    from novel_generator.pipeline_rules import DeterministicRuleChecker
    report = DeterministicRuleChecker.run_full_script_audit(text_zh=body.text_zh, text_en=body.text_en)
    text_summary = DeterministicRuleChecker.format_script_report_as_text(report)
    return {"report": report, "summary": text_summary}

# ── 章节留底档案与全书规则迭代白皮书 ──────────────────────────────────────────

class _AuditBackfillReq(_BaseModel):
    filepath: str


@router.get("/generate/audit_trail")
def get_chapter_audit(filepath: str, chapter_num: int):
    """获取单章全链路生成与质量留底档案"""
    import json as _json
    audit_file = os.path.join(filepath, "audit_trails", f"chapter_{chapter_num}_audit.json")
    md_file = os.path.join(filepath, "audit_trails", f"chapter_{chapter_num}_audit.md")
    if not os.path.exists(audit_file):
        return {"exists": False, "chapter_num": chapter_num, "message": "暂无该章留底档案"}
    try:
        with open(audit_file, "r", encoding="utf-8") as f:
            data = _json.load(f)
        md_text = ""
        if os.path.exists(md_file):
            with open(md_file, "r", encoding="utf-8") as mf:
                md_text = mf.read()
        zhuque_file = os.path.join(filepath, "audit_trails", f"chapter_{chapter_num}_zhuque_report.md")
        zhuque_md = ""
        if os.path.exists(zhuque_file):
            with open(zhuque_file, "r", encoding="utf-8") as zf:
                zhuque_md = zf.read()
        return {"exists": True, "data": data, "markdown": md_text, "zhuque_report": zhuque_md}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generate/book_audit_whitepaper")
def get_book_audit_whitepaper(filepath: str):
    """获取全书生成留底总账本与规则迭代白皮书"""
    import json as _json
    from novel_generator.audit_tracker import generate_book_iteration_report
    index_file = os.path.join(filepath, "audit_trails", "book_audit_index.json")
    index_data = {}
    if os.path.exists(index_file):
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                index_data = _json.load(f)
        except Exception:
            pass
    report_text = generate_book_iteration_report(filepath)
    return {"whitepaper": report_text, "index": index_data}


@router.post("/generate/backfill_audits")
def backfill_audits(body: _AuditBackfillReq):
    """对全书所有已有章节回溯构建留底档案"""
    from novel_generator.audit_tracker import backfill_historical_audits
    results = backfill_historical_audits(body.filepath)
    return {"success": True, "count": len(results), "chapters": results}
