from typing import Any, Callable, Dict, Optional
from pydantic import BaseModel, Field
from app.llm.router import ModelRouter


class InpaintRequest(BaseModel):
    client_id: str = "default"
    node_id: str = "node_preview"
    full_text: str
    start_index: int = Field(..., ge=0)
    end_index: int = Field(..., gt=0)
    instruction: str
    model_role: str = "prose_writer"
    context_window: int = 500


def slice_inpaint_context(full_text: str, start: int, end: int, window: int = 500) -> Dict[str, str]:
    """精准切出前文锚点、待重写段落、后文锚点"""
    prefix_start = max(0, start - window)
    suffix_end = min(len(full_text), end + window)
    return {
        "prefix": full_text[prefix_start:start],
        "target": full_text[start:end],
        "suffix": full_text[end:suffix_end],
    }


async def run_inpainting(
    req: InpaintRequest,
    router: ModelRouter,
    emit_chunk: Optional[Callable[[str], Any]] = None,
) -> Dict[str, str]:
    """
    文字版 Inpainting 局部重写执行器：
    利用 FIM (Fill-in-the-Middle) 保持前文与后文平滑衔接
    """
    slices = slice_inpaint_context(req.full_text, req.start_index, req.end_index, req.context_window)

    system_prompt = (
        "你是专业的小说精修编辑。你正在执行【局部重写（Inpainting）】任务。\n"
        "严格遵守以下规则：\n"
        "1. 只输出重写后的【新段落正文】，严禁包含前文锚点、后文锚点或任何解释性废话。\n"
        "2. 新段落的开头必须自然承接【前文】，结尾必须平滑过渡到【后文】。"
    )

    user_prompt = (
        f"【前文（严禁重复输出）】\n{slices['prefix']}\n\n"
        f"【待重写的原段落】\n{slices['target']}\n\n"
        f"【后文（严禁重复输出）】\n{slices['suffix']}\n\n"
        f"【修改指令】\n{req.instruction}\n\n"
        f"请直接输出替换后的新段落："
    )

    new_segment = ""
    async for chunk in router.stream_chat(
        role_or_profile=req.model_role,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    ):
        new_segment += chunk
        if emit_chunk:
            res = emit_chunk(chunk)
            if hasattr(res, "__await__"):
                await res

    merged_text = req.full_text[: req.start_index] + new_segment + req.full_text[req.end_index :]
    return {
        "replaced_segment": new_segment,
        "merged_text": merged_text,
    }
