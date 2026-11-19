# llm_adapters.py
# -*- coding: utf-8 -*-
import logging
from typing import Optional
from langchain_openai import ChatOpenAI, AzureChatOpenAI
# from google import genai
import google.generativeai as genai
# from google.genai import types
from google.generativeai import types
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.inference.models import SystemMessage, UserMessage
from openai import OpenAI
import requests


def check_base_url(url: str) -> str:
    """
    处理base_url的规则：
    1. 如果url以#结尾，则移除#并直接使用用户提供的url
    2. 否则检查是否需要添加/v1后缀
    """
    import re
    url = url.strip()
    if not url:
        return url
        
    if url.endswith('#'):
        return url.rstrip('#')
        
    if not re.search(r'/v\d+$', url):
        if '/v1' not in url:
            url = url.rstrip('/') + '/v1'
    return url

class BaseLLMAdapter:
    """
    统一的 LLM 接口基类，为不同后端（OpenAI、Ollama、ML Studio、Gemini等）提供一致的方法签名。
    """
    last_reasoning: str = ""  # 最近一次调用的思考过程（仅思考模型会填充）

    def invoke(self, prompt: str, system_message: str = "") -> str:
        raise NotImplementedError("Subclasses must implement .invoke(prompt) method.")

    def invoke_stream(self, prompt: str, system_message: str = ""):
        """流式调用 LLM，yield 文本片段。默认回退到非流式。"""
        result = self.invoke(prompt, system_message=system_message)
        if result:
            yield result

    def invoke_chat_stream(self, messages: list):
        """流式多轮对话。messages = [{"role": ..., "content": ...}, ...]
        默认回退：提取 system 和最后一条 user 消息，调用 invoke_stream。"""
        system_msg = ""
        user_msg = ""
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            if m["role"] == "user":
                user_msg = m["content"]
        yield from self.invoke_stream(user_msg, system_message=system_msg)

def _openai_chat_stream_helper(client, model_name, messages, max_tokens, temperature, timeout):
    """OpenAI 兼容接口的通用多轮对话流式调用辅助函数。"""
    stream = client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def _openai_stream_helper(client, model_name, prompt, system_message, max_tokens, temperature, timeout):
    """OpenAI 兼容接口的通用流式调用辅助函数。
    client: openai.OpenAI 实例
    返回: generator，逐片段 yield 文本
    """
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})
    stream = client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


class DeepSeekAdapter(BaseLLMAdapter):
    """
    适配官方/OpenAI兼容接口（使用 langchain.ChatOpenAI）
    """
    def __init__(self, api_key: str, base_url: str, model_name: str, max_tokens: int, temperature: float = 0.7, timeout: Optional[int] = 600):
        self.base_url = check_base_url(base_url)
        self.api_key = api_key
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

        self._client = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            timeout=self.timeout,
            max_retries=0
        )
        self._raw_client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=0
        )

    def invoke(self, prompt: str, system_message: str = "") -> str:
        from langchain_core.messages import SystemMessage as LCSystemMessage, HumanMessage
        if system_message:
            messages = [LCSystemMessage(content=system_message), HumanMessage(content=prompt)]
            response = self._client.invoke(messages)
        else:
            response = self._client.invoke(prompt)
        if not response:
            logging.warning("No response from DeepSeekAdapter.")
            return ""
        return response.content

    def invoke_stream(self, prompt: str, system_message: str = ""):
        yield from _openai_stream_helper(
            self._raw_client, self.model_name, prompt, system_message,
            self.max_tokens, self.temperature, self.timeout
        )

    def invoke_chat_stream(self, messages: list):
        yield from _openai_chat_stream_helper(
            self._raw_client, self.model_name, messages,
            self.max_tokens, self.temperature, self.timeout
        )

class OpenAIAdapter(BaseLLMAdapter):
    """
    适配官方/OpenAI兼容接口（使用 langchain.ChatOpenAI）
    当 enable_thinking=True 时，改用原生 openai.OpenAI 客户端以支持
    thinking_budget 扩展参数，并记录思考过程到日志。
    """
    def __init__(self, api_key: str, base_url: str, model_name: str, max_tokens: int, temperature: float = 0.7, timeout: Optional[int] = 600, enable_thinking: bool = False, thinking_budget: int = 0):
        self.base_url = check_base_url(base_url)
        self.api_key = api_key
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.enable_thinking = enable_thinking
        self.thinking_budget = thinking_budget

        if self.enable_thinking:
            self._raw_client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=0
            )
            self._client = None
            logging.info(f"OpenAIAdapter: 启用思考模式, thinking_budget={self.thinking_budget}, model={self.model_name}")
        else:
            self._raw_client = None
            self._client = ChatOpenAI(
                model=self.model_name,
                api_key=self.api_key,
                base_url=self.base_url,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=self.timeout,
                max_retries=0
            )

    def invoke(self, prompt: str, system_message: str = "") -> str:
        if self._raw_client:
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})
            api_params = {
                "model": self.model_name,
                "messages": messages,
                "max_tokens": self.max_tokens,
            }
            if self.thinking_budget > 0:
                api_params["extra_body"] = {"thinking_budget": self.thinking_budget}
            response = self._raw_client.chat.completions.create(**api_params)
            if not response or not response.choices:
                logging.warning("No response from OpenAIAdapter (thinking mode).")
                return ""
            msg = response.choices[0].message
            # 从多种位置尝试获取 reasoning_content（不同 SDK 版本存放位置不同）
            reasoning = (
                getattr(msg, 'reasoning_content', None)
                or (msg.model_extra or {}).get('reasoning_content')
                or ""
            )
            self.last_reasoning = reasoning
            if reasoning:
                logging.info(f"[Thinking] 思考过程 ({len(reasoning)}字):\n{reasoning[:500]}{'...(截断)' if len(reasoning) > 500 else ''}")
            else:
                logging.info(f"[Thinking] 未获取到 reasoning_content, msg字段: {list(vars(msg).keys()) if hasattr(msg, '__dict__') else dir(msg)}")
            content = msg.content or ""
            if not content and reasoning:
                logging.warning("[Thinking] content 为空但有 reasoning_content, 可能模型仅返回了思考过程")
            return content
        else:
            self.last_reasoning = ""
            from langchain_core.messages import SystemMessage as LCSystemMessage, HumanMessage
            if system_message:
                messages = [LCSystemMessage(content=system_message), HumanMessage(content=prompt)]
                response = self._client.invoke(messages)
            else:
                response = self._client.invoke(prompt)
            if not response:
                logging.warning("No response from OpenAIAdapter.")
                return ""
            return response.content

    def invoke_stream(self, prompt: str, system_message: str = ""):
        if self._raw_client:
            # thinking 模式也支持流式
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})
            api_params = {
                "model": self.model_name,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "stream": True,
            }
            if self.thinking_budget > 0:
                api_params["extra_body"] = {"thinking_budget": self.thinking_budget}
            stream = self._raw_client.chat.completions.create(**api_params)
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        else:
            yield from _openai_stream_helper(
                OpenAI(base_url=self.base_url, api_key=self.api_key,
                       timeout=self.timeout, max_retries=0),
                self.model_name, prompt, system_message,
                self.max_tokens, self.temperature, self.timeout
            )

    def invoke_chat_stream(self, messages: list):
        if self._raw_client:
            yield from _openai_chat_stream_helper(
                self._raw_client, self.model_name, messages,
                self.max_tokens, self.temperature, self.timeout
            )
        else:
            raw = OpenAI(base_url=self.base_url, api_key=self.api_key,
                         timeout=self.timeout, max_retries=0)
            yield from _openai_chat_stream_helper(
                raw, self.model_name, messages,
                self.max_tokens, self.temperature, self.timeout
            )

class GeminiAdapter(BaseLLMAdapter):
    """
    适配 Google Gemini (Google Generative AI) 接口
    """

    # PenBo 修复新版本google-generativeai 不支持 Client 类问题；而是使用 GenerativeModel 类来访问API
    def __init__(self, api_key: str, base_url: str, model_name: str, max_tokens: int, temperature: float = 0.7, timeout: Optional[int] = 600):
        self.api_key = api_key
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

        # 配置API密钥
        genai.configure(api_key=self.api_key)
        
        # 创建生成模型实例
        self._model = genai.GenerativeModel(model_name=self.model_name)

    def invoke(self, prompt: str, system_message: str = "") -> str:
        try:
            # 设置生成配置
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            # Gemini 通过 system_instruction 注入 system message
            effective_prompt = prompt
            if system_message:
                effective_prompt = f"{system_message}\n\n{prompt}"

            # 生成内容
            response = self._model.generate_content(
                effective_prompt,
                generation_config=generation_config
            )

            if response and response.text:
                return response.text
            else:
                logging.warning("No text response from Gemini API.")
                return ""
        except Exception as e:
            logging.error(f"Gemini API 调用失败: {e}")
            return ""

class AzureOpenAIAdapter(BaseLLMAdapter):
    """
    适配 Azure OpenAI 接口（使用 langchain.ChatOpenAI）
    """
    def __init__(self, api_key: str, base_url: str, model_name: str, max_tokens: int, temperature: float = 0.7, timeout: Optional[int] = 600):
        import re
        match = re.match(r'https://(.+?)/openai/deployments/(.+?)/chat/completions\?api-version=(.+)', base_url)
        if match:
            self.azure_endpoint = f"https://{match.group(1)}"
            self.azure_deployment = match.group(2)
            self.api_version = match.group(3)
        else:
            raise ValueError("Invalid Azure OpenAI base_url format")
        
        self.api_key = api_key
        self.model_name = self.azure_deployment
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

        self._client = AzureChatOpenAI(
            azure_endpoint=self.azure_endpoint,
            azure_deployment=self.azure_deployment,
            api_version=self.api_version,
            api_key=self.api_key,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            timeout=self.timeout,
            max_retries=0
        )

    def invoke(self, prompt: str, system_message: str = "") -> str:
        from langchain_core.messages import SystemMessage as LCSystemMessage, HumanMessage
        if system_message:
            messages = [LCSystemMessage(content=system_message), HumanMessage(content=prompt)]
            response = self._client.invoke(messages)
        else:
            response = self._client.invoke(prompt)
        if not response:
            logging.warning("No response from AzureOpenAIAdapter.")
            return ""
        return response.content

class OllamaAdapter(BaseLLMAdapter):
    """
    Ollama 同样有一个 OpenAI-like /v1/chat 接口，可直接使用 ChatOpenAI。
    """
    def __init__(self, api_key: str, base_url: str, model_name: str, max_tokens: int, temperature: float = 0.7, timeout: Optional[int] = 600):
        self.base_url = check_base_url(base_url)
        self.api_key = api_key
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

        if self.api_key == '':
            self.api_key= 'ollama'

        self._client = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            timeout=self.timeout,
            max_retries=0
        )

    def invoke(self, prompt: str, system_message: str = "") -> str:
        from langchain_core.messages import SystemMessage as LCSystemMessage, HumanMessage
        if system_message:
            messages = [LCSystemMessage(content=system_message), HumanMessage(content=prompt)]
            response = self._client.invoke(messages)
        else:
            response = self._client.invoke(prompt)
        if not response:
            logging.warning("No response from OllamaAdapter.")
            return ""
        return response.content

    def invoke_stream(self, prompt: str, system_message: str = ""):
        raw = OpenAI(base_url=self.base_url, api_key=self.api_key,
                     timeout=self.timeout, max_retries=0)
        yield from _openai_stream_helper(
            raw, self.model_name, prompt, system_message,
            self.max_tokens, self.temperature, self.timeout
        )

    def invoke_chat_stream(self, messages: list):
        raw = OpenAI(base_url=self.base_url, api_key=self.api_key,
                     timeout=self.timeout, max_retries=0)
        yield from _openai_chat_stream_helper(
            raw, self.model_name, messages,
            self.max_tokens, self.temperature, self.timeout
        )

class MLStudioAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, base_url: str, model_name: str, max_tokens: int, temperature: float = 0.7, timeout: Optional[int] = 600):
        self.base_url = check_base_url(base_url)
        self.api_key = api_key
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

        self._client = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            timeout=self.timeout,
            max_retries=0
        )

    def invoke(self, prompt: str, system_message: str = "") -> str:
        try:
            from langchain_core.messages import SystemMessage as LCSystemMessage, HumanMessage
            if system_message:
                messages = [LCSystemMessage(content=system_message), HumanMessage(content=prompt)]
                response = self._client.invoke(messages)
            else:
                response = self._client.invoke(prompt)
            if not response:
                logging.warning("No response from MLStudioAdapter.")
                return ""
            return response.content
        except Exception as e:
            logging.error(f"ML Studio API 调用超时或失败: {e}")
            return ""

class AzureAIAdapter(BaseLLMAdapter):
    """
    适配 Azure AI Inference 接口，用于访问Azure AI服务部署的模型
    使用 azure-ai-inference 库进行API调用
    """
    def __init__(self, api_key: str, base_url: str, model_name: str, max_tokens: int, temperature: float = 0.7, timeout: Optional[int] = 600):
        import re
        # 匹配形如 https://xxx.services.ai.azure.com/models/chat/completions?api-version=xxx 的URL
        match = re.match(r'https://(.+?)\.services\.ai\.azure\.com(?:/models)?(?:/chat/completions)?(?:\?api-version=(.+))?', base_url)
        if match:
            # endpoint需要是形如 https://xxx.services.ai.azure.com/models 的格式
            self.endpoint = f"https://{match.group(1)}.services.ai.azure.com/models"
            # 如果URL中包含api-version参数，使用它；否则使用默认值
            self.api_version = match.group(2) if match.group(2) else "2024-05-01-preview"
        else:
            raise ValueError("Invalid Azure AI base_url format. Expected format: https://<endpoint>.services.ai.azure.com/models/chat/completions?api-version=xxx")
        
        self.base_url = self.endpoint  # 存储处理后的endpoint URL
        self.api_key = api_key
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

        self._client = ChatCompletionsClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.api_key),
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout
        )

    def invoke(self, prompt: str, system_message: str = "") -> str:
        try:
            sys_msg = system_message if system_message else "You are a helpful assistant."
            response = self._client.complete(
                messages=[
                    SystemMessage(sys_msg),
                    UserMessage(prompt)
                ]
            )
            if response and response.choices:
                return response.choices[0].message.content
            else:
                logging.warning("No response from AzureAIAdapter.")
                return ""
        except Exception as e:
            logging.error(f"Azure AI Inference API 调用失败: {e}")
            return ""

# 火山引擎实现
class VolcanoEngineAIAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, base_url: str, model_name: str, max_tokens: int, temperature: float = 0.7, timeout: Optional[int] = 600):
        self.base_url = check_base_url(base_url)
        self.api_key = api_key
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=0
        )
    def invoke(self, prompt: str, system_message: str = "") -> str:
        try:
            sys_msg = system_message if system_message else "你是DeepSeek，是一个 AI 人工智能助手"
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": prompt},
                ],
                timeout=self.timeout
            )
            if not response:
                logging.warning("No response from VolcanoEngineAIAdapter.")
                return ""
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"火山引擎API调用超时或失败: {e}")
            return ""

    def invoke_stream(self, prompt: str, system_message: str = ""):
        yield from _openai_stream_helper(
            self._client, self.model_name, prompt,
            system_message or "你是DeepSeek，是一个 AI 人工智能助手",
            self.max_tokens, self.temperature, self.timeout
        )

class SiliconFlowAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, base_url: str, model_name: str, max_tokens: int, temperature: float = 0.7, timeout: Optional[int] = 600, enable_thinking: bool = False, thinking_budget: int = 0):
        self.base_url = check_base_url(base_url)
        self.api_key = api_key
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.enable_thinking = enable_thinking
        self.thinking_budget = thinking_budget

        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=0
        )
    def invoke(self, prompt: str, system_message: str = "") -> str:
        try:
            sys_msg = system_message if system_message else "你是DeepSeek，是一个 AI 人工智能助手"
            api_params = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": prompt},
                ],
                "timeout": self.timeout
            }

            if self.enable_thinking and self.thinking_budget > 0:
                api_params["extra_body"] = {"thinking_budget": self.thinking_budget}
                logging.info(f"启用思考模式，thinking_budget={self.thinking_budget}")

            response = self._client.chat.completions.create(**api_params)

            if not response:
                logging.warning("No response from SiliconFlowAdapter.")
                return ""
            msg = response.choices[0].message
            reasoning = (
                getattr(msg, 'reasoning_content', None)
                or (msg.model_extra or {}).get('reasoning_content')
                or ""
            )
            self.last_reasoning = reasoning
            if reasoning:
                logging.info(f"[Thinking] 思考过程 ({len(reasoning)}字):\n{reasoning[:500]}{'...(截断)' if len(reasoning) > 500 else ''}")
            content = msg.content or ""
            if not content and reasoning:
                logging.warning("[Thinking] content 为空但有 reasoning_content, 可能模型仅返回了思考过程")
            return content
        except Exception as e:
            logging.error(f"硅基流动API调用超时或失败: {e}")
            return ""

    def invoke_stream(self, prompt: str, system_message: str = ""):
        yield from _openai_stream_helper(
            self._client, self.model_name, prompt,
            system_message or "你是DeepSeek，是一个 AI 人工智能助手",
            self.max_tokens, self.temperature, self.timeout
        )

    def invoke_chat_stream(self, messages: list):
        yield from _openai_chat_stream_helper(
            self._client, self.model_name, messages,
            self.max_tokens, self.temperature, self.timeout
        )

# grok實現
class GrokAdapter(BaseLLMAdapter):
    """
    适配 xAI Grok API
    """
    def __init__(self, api_key: str, base_url: str, model_name: str, max_tokens: int, temperature: float = 0.7, timeout: Optional[int] = 600):
        self.base_url = check_base_url(base_url)
        self.api_key = api_key
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=0
        )

    def invoke(self, prompt: str, system_message: str = "") -> str:
        try:
            sys_msg = system_message if system_message else "You are Grok, created by xAI."
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=self.timeout
            )
            if response and response.choices:
                return response.choices[0].message.content
            else:
                logging.warning("No response from GrokAdapter.")
                return ""
        except Exception as e:
            logging.error(f"Grok API 调用失败: {e}")
            return ""

    def invoke_stream(self, prompt: str, system_message: str = ""):
        yield from _openai_stream_helper(
            self._client, self.model_name, prompt,
            system_message or "You are Grok, created by xAI.",
            self.max_tokens, self.temperature, self.timeout
        )

    def invoke_chat_stream(self, messages: list):
        yield from _openai_chat_stream_helper(
            self._client, self.model_name, messages,
            self.max_tokens, self.temperature, self.timeout
        )


class MuseAdapter(BaseLLMAdapter):
    """
    基于 muse-cli 的 Meta Muse 个人 AI Agent 适配器。
    专门用于长篇小说高质量文学渲染与正文撰写。
    """
    def __init__(self, session_id: Optional[str] = None, timeout: int = 180):
        self.session_id = session_id
        self.timeout = timeout or 180
        self.model_name = "Meta-Muse"
        self.last_reasoning = ""

    def invoke(self, prompt: str, system_message: str = "") -> str:
        import time
        import os
        import logging
        from muse_cli.cli import connect, load_config

        if "MUSE_PROXY" not in os.environ and "ALL_PROXY" not in os.environ:
            os.environ["MUSE_PROXY"] = "socks5h://127.0.0.1:7897"

        combined = f"System Instructions:\n{system_message}\n\nUser Request:\n{prompt}" if system_message else prompt
        cfg = load_config()
        gw = connect(cfg)

        params = {
            "items": [{"type": "text", "text": combined}],
            "node_id": cfg["node_id"],
            "capabilities": {},
        }
        if self.session_id:
            params["session_id"] = self.session_id

        scope = {"session_id": self.session_id} if self.session_id else {}
        baseline = 0
        try:
            h = gw.call_json("chat.history", body={"limit": 5, **scope})
            evs = h.get("chat_events", [])
            if evs:
                baseline = max(e.get("seq", 0) for e in evs)
        except Exception:
            pass

        gw._open("chat.stream", body=params)

        deadline = time.time() + self.timeout
        while time.time() < deadline:
            time.sleep(2)
            try:
                h = gw.call_json("chat.history", body={"limit": 10, **scope})
                evs = sorted(h.get("chat_events", []), key=lambda e: e.get("seq", 0))
                for ev in evs:
                    if ev.get("seq", 0) > baseline:
                        payload = ev.get("payload", {})
                        if payload.get("role") == "assistant" or ev.get("role") == "assistant" or ev.get("event_name") == "message.assistant":
                            text = payload.get("display_text") or payload.get("content") or ev.get("display_text")
                            if text:
                                return text
            except Exception as e:
                logging.warning(f"[MuseAdapter] Polling error: {e}")
                continue

        raise TimeoutError(f"Muse did not respond within {self.timeout} seconds")

    def invoke_stream(self, prompt: str, system_message: str = ""):
        result = self.invoke(prompt, system_message=system_message)
        if result:
            yield result

class AgyCodexAdapter(BaseLLMAdapter):
    """
    基于本地 Antigravity / Codex 官方 CLI 引擎的大模型适配器。
    完全免密、无需第三方 API Key 与网络代理，直接使用本地环境模型。
    """
    def __init__(self, model_name: str = "gemini-3.8-flash-low", timeout: int = 180):
        self.model_name = model_name or "gemini-3.8-flash-low"
        self.timeout = timeout or 180
        self.last_reasoning = ""
        self.agy_path = self._find_agy()

    def _find_agy(self) -> str:
        import shutil, os
        p = shutil.which("agy")
        if p and os.path.exists(p):
            return p
        local_app = os.path.expandvars(r"%LOCALAPPDATA%\agy\bin\agy.exe")
        if os.path.exists(local_app):
            return local_app
        return "agy"

    def invoke_stream(self, prompt: str, system_message: str = ""):
        import subprocess, json, os, tempfile

        # 核心约束：强制作为文学创作与对话模型，禁止 agy CLI 尝试调用命令行/写文件等工具
        no_tools_instruction = "【系统核心约束：你是专业文学创作与双语本地化翻译助手。严禁尝试调用任何工具、执行命令或访问文件系统，必须直接输出纯文本回答。】\n\n"
        combined = f"{no_tools_instruction}{system_message}\n\n{prompt}" if system_message else f"{no_tools_instruction}{prompt}"

        cmd = [
            self.agy_path,
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--disable-slash-commands",
            "--dangerously-skip-permissions"
        ]
        clean_model = (self.model_name or "").strip()
        if clean_model and clean_model.lower() not in ("default", "auto", "codex", "内置模型", "codex 内置模型", "codex/antigravity"):
            cmd.extend(["--model", clean_model])

        try:
            # 在临时目录运行，隔离工作区，防止 agy 尝试解析代码仓库或运行命令
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                cwd=tempfile.gettempdir()
            )
        except Exception as e:
            raise RuntimeError(f"启动本地 Codex/Antigravity 引擎失败 ({self.agy_path}): {e}")

        payload = json.dumps({"event": "user", "message": {"content": combined}}, ensure_ascii=False)
        try:
            proc.stdin.write(payload + "\n")
            proc.stdin.flush()
            proc.stdin.close()
        except Exception as e:
            try:
                proc.kill()
            except Exception:
                pass
            raise RuntimeError(f"向本地 Codex/Antigravity 引擎下发提示词失败: {e}")

        full_chunks = []
        last_error = ""
        try:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue

                event = data.get("event")
                if event == "step_update":
                    update = data.get("step_update", {})
                    step_type = update.get("step_type")
                    if step_type == "agent_response":
                        delta = update.get("text_delta") or update.get("content")
                        if delta:
                            full_chunks.append(delta)
                            yield delta
                    elif step_type == "error":
                        last_error = update.get("error") or update.get("message") or str(update)
                        logging.warning(f"[AgyCodexAdapter] step_type error: {last_error}")
                elif event == "error":
                    last_error = data.get("error", {}).get("message") or str(data.get("error"))
                    logging.warning(f"[AgyCodexAdapter] event error: {last_error}")
                elif event == "result":
                    res = data.get("result", {})
                    if not full_chunks:
                        resp = res.get("response") or res.get("content") or ""
                        if resp:
                            full_chunks.append(resp)
                            yield resp
                        elif res.get("status") and res.get("status") != "SUCCESS":
                            last_error = res.get("error") or f"status={res.get('status')}"
                    break

            if not full_chunks:
                try:
                    stderr_txt = proc.stderr.read().strip()
                except Exception:
                    stderr_txt = ""
                err_detail = last_error or stderr_txt or f"退出码={proc.poll()}"
                logging.error(f"[AgyCodexAdapter] 未收到有效模型回复，详情: {err_detail}")
        finally:
            try:
                proc.terminate()
            except Exception:
                pass

    def invoke(self, prompt: str, system_message: str = "") -> str:
        return "".join(list(self.invoke_stream(prompt, system_message=system_message)))

    def invoke_chat_stream(self, messages: list):
        """流式多轮对话支持：完整保留并格式化对话上下文历史与角色指令"""
        system_parts = []
        dialogue_history = []
        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if not content:
                continue
            if role == "system":
                system_parts.append(content)
            elif role == "user":
                dialogue_history.append(f"【用户】：\n{content}")
            elif role == "assistant":
                dialogue_history.append(f"【AI顾问】：\n{content}")

        system_text = "\n\n".join(system_parts)
        history_text = "\n\n".join(dialogue_history)
        combined = f"{system_text}\n\n=== 对话历史与当前提问 ===\n\n{history_text}\n\n请针对用户的最新提问，直接给出你的建议和回复："
        yield from self.invoke_stream(combined, system_message="")


def _apply_proxy_settings():
    """读取 config.json 中的代理设置，注入到环境变量中供 httpx/requests/openai 使用。"""
    import os, json
    from app_paths import get_data_file
    config_path = get_data_file("config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        proxy_cfg = config.get("proxy_setting", {})
        if proxy_cfg.get("enabled") and proxy_cfg.get("proxy_url"):
            proxy_url = proxy_cfg["proxy_url"].strip()
            proxy_port = str(proxy_cfg.get("proxy_port", "")).strip()
            if not any(proxy_url.startswith(p) for p in ("http://", "https://", "socks5://", "socks5h://")):
                proxy_url = "http://" + proxy_url
            if proxy_port:
                proxy_url = proxy_url.rstrip("/") + ":" + proxy_port
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
            os.environ["http_proxy"] = proxy_url
            os.environ["https_proxy"] = proxy_url
            logging.info(f"[Proxy] 代理已启用: {proxy_url}")
        else:
            for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
                os.environ.pop(key, None)
    except Exception as e:
        logging.warning(f"[Proxy] 读取代理配置失败: {e}")


def create_llm_adapter(
    interface_format: str,
    base_url: str,
    model_name: str,
    api_key: str,
    temperature: float,
    max_tokens: int,
    timeout: int,
    enable_thinking: bool = False,
    thinking_budget: int = 0
) -> BaseLLMAdapter:
    """
    工厂函数：根据 interface_format 返回不同的适配器实例。
    """
    _apply_proxy_settings()
    fmt = interface_format.strip().lower()
    if fmt == "deepseek":
        return DeepSeekAdapter(api_key, base_url, model_name, max_tokens, temperature, timeout)
    elif fmt == "openai":
        return OpenAIAdapter(api_key, base_url, model_name, max_tokens, temperature, timeout, enable_thinking, thinking_budget)
    elif fmt == "azure openai":
        return AzureOpenAIAdapter(api_key, base_url, model_name, max_tokens, temperature, timeout)
    elif fmt == "azure ai":
        return AzureAIAdapter(api_key, base_url, model_name, max_tokens, temperature, timeout)
    elif fmt == "ollama":
        return OllamaAdapter(api_key, base_url, model_name, max_tokens, temperature, timeout)
    elif fmt == "ml studio":
        return MLStudioAdapter(api_key, base_url, model_name, max_tokens, temperature, timeout)
    elif fmt == "gemini":
        return GeminiAdapter(api_key, base_url, model_name, max_tokens, temperature, timeout)
    elif fmt == "阿里云百炼":
        return OpenAIAdapter(api_key, base_url, model_name, max_tokens, temperature, timeout, enable_thinking, thinking_budget)
    elif fmt == "火山引擎":
        return VolcanoEngineAIAdapter(api_key, base_url, model_name, max_tokens, temperature, timeout)
    elif fmt == "硅基流动":
        return SiliconFlowAdapter(api_key, base_url, model_name, max_tokens, temperature, timeout, enable_thinking, thinking_budget)
    elif fmt == "grok":
        return GrokAdapter(api_key, base_url, model_name, max_tokens, temperature, timeout)
    elif fmt in ("codex", "agy", "antigravity", "local", "内置模型", "codex/antigravity", "codex 内置模型"):
        clean_model = model_name if (model_name and model_name not in ("auto", "default")) else "gemini-3.8-flash-low"
        return AgyCodexAdapter(model_name=clean_model, timeout=timeout or 180)
    elif fmt in ("muse", "meta muse", "muse.ai"):
        session_id = None
        if model_name and len(model_name) >= 30 and "-" in model_name:
            session_id = model_name
        return MuseAdapter(session_id=session_id, timeout=timeout or 180)
    else:
        raise ValueError(f"Unknown interface_format: {interface_format}")
