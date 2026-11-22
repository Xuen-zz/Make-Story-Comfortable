import json
import re
from typing import Any, Dict, List, Optional, Type, TypeVar
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def extract_json_str(raw_text: str) -> str:
    """容错提取：剥离 ```json 围栏或前后闲聊文字"""
    text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


async def call_llm_structured(
    client: AsyncOpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_model: Type[T],
    max_retries: int = 3,
    temperature: float = 0.1,
    use_json_mode: bool = True,
) -> T:
    """
    通用结构化提取调用器：
    自动注入 Pydantic Schema，校验失败时将精准错误信息追加回上下文让模型原地自愈修正。
    注意：不拦截 asyncio.CancelledError，保证 Cancel 动作无阻碍穿透。
    """
    schema_json = json.dumps(response_model.model_json_schema(), ensure_ascii=False, indent=2)
    full_system_prompt = (
        f"{system_prompt}\n\n"
        f"【严格输出要求】\n"
        f"你必须只输出一个合法的 JSON 对象，严格符合以下 JSON Schema，严禁输出任何解释性文字：\n"
        f"{schema_json}"
    )

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": full_system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = await client.chat.completions.create(**kwargs)
        raw_content = resp.choices[0].message.content or ""

        try:
            clean_json = extract_json_str(raw_content)
            parsed_dict = json.loads(clean_json)
            validated_obj = response_model.model_validate(parsed_dict)
            return validated_obj

        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            error_msg = str(e)
            print(f"[JSON 校验失败 - 第 {attempt}/{max_retries} 次尝试] 错误: {error_msg[:180]}...")

            if attempt < max_retries:
                messages.append({"role": "assistant", "content": raw_content})
                messages.append({
                    "role": "user",
                    "content": (
                        f"你刚才输出的 JSON 未通过格式校验，报错如下：\n{error_msg}\n\n"
                        f"请修复上述错误，重新输出完整且严格合法的 JSON 对象。"
                    ),
                })

    raise RuntimeError(f"结构化提取在重试 {max_retries} 次后依然失败，最后一次报错: {last_error}")
