import asyncio
from typing import AsyncGenerator, Dict, List, Optional
from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError
from pydantic import BaseModel, Field


class ModelProfile(BaseModel):
    profile_id: str          # 例如 "deepseek_v3", "claude_sonnet", "local_ollama"
    provider: str = "openai" # "deepseek" | "openrouter" | "ollama" | "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = "sk-placeholder"
    model_name: str
    default_temp: float = 0.7
    timeout: float = 60.0


class ModelRouter:
    """
    多模型分流路由器：
    1. 按任务角色（Role，如 prose_writer / fast_extractor）调度
    2. 故障自动降级（Fallback Chain）
    3. 吐字中途不切模型防文风撕裂
    4. CancelledError 零延迟穿透
    """
    def __init__(self):
        self.profiles: Dict[str, ModelProfile] = {}
        self.clients: Dict[str, AsyncOpenAI] = {}
        self.role_chains: Dict[str, List[str]] = {}

    def register_profile(self, profile: ModelProfile):
        self.profiles[profile.profile_id] = profile
        self.clients[profile.profile_id] = AsyncOpenAI(
            api_key=profile.api_key,
            base_url=profile.base_url,
            timeout=profile.timeout,
        )

    def bind_role(self, role: str, profile_chain: List[str]):
        """例如: bind_role("prose_writer", ["flagship_writer", "deepseek_chat"])"""
        self.role_chains[role] = profile_chain

    def _resolve_chain(self, role_or_profile: str) -> List[ModelProfile]:
        """支持传角色名或具体 profile_id"""
        if role_or_profile in self.role_chains:
            ids = self.role_chains[role_or_profile]
        elif role_or_profile in self.profiles:
            ids = [role_or_profile]
        else:
            raise ValueError(f"未找到模型角色或配置: {role_or_profile}")
        return [self.profiles[pid] for pid in ids]

    async def stream_chat(
        self,
        role_or_profile: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """带自动降级的流式生成器"""
        chain = self._resolve_chain(role_or_profile)
        last_err: Optional[Exception] = None

        for idx, profile in enumerate(chain):
            client = self.clients[profile.profile_id]
            stream = None
            has_yielded = False

            try:
                stream = await client.chat.completions.create(
                    model=profile.model_name,
                    messages=messages,
                    temperature=temperature if temperature is not None else profile.default_temp,
                    stream=True,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        has_yielded = True
                        yield delta
                return  # 成功吐完，直接返回

            except asyncio.CancelledError:
                # 外部取消时立刻穿透，不触发降级
                raise
            except (APIError, RateLimitError, APITimeoutError, Exception) as e:
                last_err = e
                # 若已吐出部分字符，不可再静默切换模型，防止前后文风撕裂
                if has_yielded or idx == len(chain) - 1:
                    raise
                print(f"[ROUTER FALLBACK] {profile.profile_id} 异常 ({e})，降级至 {chain[idx+1].profile_id}")
            finally:
                if stream is not None:
                    await stream.close()

        raise RuntimeError(f"角色 {role_or_profile} 所有备用模型均调用失败: {last_err}")
