# api/routers/config.py
# -*- coding: utf-8 -*-
"""LLM / Embedding 配置路由"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from api.schemas import LLMConfigCreate, EmbeddingConfigCreate, TestLLMConfigRequest, TestEmbeddingConfigRequest
from api.app_state import get_web_app
from api.sse_utils import run_with_sse
from embedding_adapters import create_embedding_adapter, clear_embedding_cache
from llm_adapters import create_llm_adapter

router = APIRouter(tags=["config"])


# ── LLM ───────────────────────────────────────────────────────────────────────

@router.get("/config/llm")
def list_llm_configs():
    app = get_web_app()
    configs = app.config.get("llm_configs", {})
    return {
        "configs": configs,
        "choices": list(configs.keys()),
        "choose": app.config.get("choose_configs", {})
    }


@router.post("/config/llm")
def save_llm_config(body: LLMConfigCreate):
    app = get_web_app()
    _, msg = app.save_llm_config(
        body.config_name, body.api_key, body.base_url,
        body.interface_format, body.model_name,
        body.temperature, body.max_tokens, body.timeout,
        body.enable_thinking, body.thinking_budget,
        body.enable_streaming,
    )
    if msg.startswith("❌"):
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


@router.delete("/config/llm/{name}")
def delete_llm_config(name: str):
    app = get_web_app()
    _, msg = app.delete_llm_config(name)
    if msg.startswith("❌"):
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


# ── Embedding ─────────────────────────────────────────────────────────────────

@router.get("/config/embedding")
def list_embedding_configs():
    app = get_web_app()
    configs = app.config.get("embedding_configs", {})
    return {
        "configs": configs,
        "choices": list(configs.keys())
    }


@router.post("/config/embedding")
def save_embedding_config(body: EmbeddingConfigCreate):
    app = get_web_app()
    _, msg = app.save_embedding_config(
        body.config_name, body.interface_format, body.api_key,
        body.base_url, body.model_name, body.retrieval_k
    )
    if msg.startswith("❌"):
        raise HTTPException(status_code=400, detail=msg)
    clear_embedding_cache()
    return {"message": msg}


@router.delete("/config/embedding/{name}")
def delete_embedding_config(name: str):
    app = get_web_app()
    _, msg = app.delete_embedding_config(name)
    if msg.startswith("❌"):
        raise HTTPException(status_code=400, detail=msg)
    clear_embedding_cache()
    return {"message": msg}


# ── 连通性测试 ────────────────────────────────────────────────────────────────

def _test_llm_sync(interface_format, api_key, base_url, model_name,
                    temperature, max_tokens, timeout, progress):
    progress(0.1, desc="正在创建 LLM 适配器...")
    llm_adapter = create_llm_adapter(
        interface_format=interface_format,
        base_url=base_url,
        model_name=model_name,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    progress(0.3, desc="正在发送测试请求...")
    response = llm_adapter.invoke("Please reply 'OK'")
    if response:
        progress(0.9, desc="测试成功")
        return f"✅ LLM 连通性测试成功！回复: {response[:200]}"
    return "❌ LLM 测试失败：未获取到响应"


def _test_emb_sync(interface_format, api_key, base_url, model_name, progress):
    progress(0.1, desc="正在创建 Embedding 适配器...")
    adapter = create_embedding_adapter(
        interface_format=interface_format,
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
    )
    progress(0.3, desc="正在发送测试请求...")
    embeddings = adapter.embed_query("测试文本")
    if embeddings and len(embeddings) > 0:
        progress(0.9, desc="测试成功")
        return f"✅ Embedding 连通性测试成功！向量维度: {len(embeddings)}"
    return "❌ Embedding 测试失败：未获取到向量"


@router.post("/config/llm/test")
async def test_llm_config(body: TestLLMConfigRequest):
    return StreamingResponse(
        run_with_sse(
            _test_llm_sync,
            body.interface_format, body.api_key, body.base_url,
            body.model_name, body.temperature, body.max_tokens, body.timeout,
        ),
        media_type="text/event-stream",
    )


@router.post("/config/embedding/test")
async def test_embedding_config(body: TestEmbeddingConfigRequest):
    return StreamingResponse(
        run_with_sse(
            _test_emb_sync,
            body.interface_format, body.api_key, body.base_url, body.model_name,
        ),
        media_type="text/event-stream",
    )


# ── 代理设置 ─────────────────────────────────────────────────────────────────

@router.get("/config/proxy")
def get_proxy():
    app = get_web_app()
    proxy = app.config.get("proxy_setting", {"proxy_url": "", "proxy_port": "", "enabled": False})
    return proxy


@router.put("/config/proxy")
def save_proxy(body: dict):
    app = get_web_app()
    app.config["proxy_setting"] = {
        "proxy_url": body.get("proxy_url", "").strip(),
        "proxy_port": str(body.get("proxy_port", "")).strip(),
        "enabled": bool(body.get("enabled", False)),
    }
    from config_manager import save_config
    save_config(app.config, app.config_file)
    # 立即生效
    from llm_adapters import _apply_proxy_settings
    _apply_proxy_settings()
    return {"message": "✅ 代理设置已保存"}


# ── 用户画像 ─────────────────────────────────────────────────────────────────

import json
import os
from datetime import datetime

from app_paths import get_data_file
_PROFILE_PATH = get_data_file("user_profile.json")


def _read_profile():
    if os.path.exists(_PROFILE_PATH):
        with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"profile": "", "updated_at": ""}


def _write_profile(data):
    with open(_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.get("/config/user_profile")
def get_user_profile():
    return _read_profile()


@router.post("/config/user_profile/extract")
def extract_user_preferences(body: dict):
    """从用户文本中提取偏好信号，返回提取结果（不自动写入）"""
    text = body.get("text", "").strip()
    llm_config_name = body.get("llm_config_name", "")
    if not text or not llm_config_name:
        return {"preferences": ""}

    app = get_web_app()
    if llm_config_name not in app.config.get("llm_configs", {}):
        return {"preferences": ""}

    llm_conf = app.config["llm_configs"][llm_config_name]
    existing_profile = _read_profile().get("profile", "")

    from llm_adapters import create_llm_adapter
    from novel_generator.common import invoke_with_cleaning

    llm_adapter = create_llm_adapter(
        interface_format=llm_conf["interface_format"],
        base_url=llm_conf["base_url"],
        model_name=llm_conf["model_name"],
        api_key=llm_conf["api_key"],
        temperature=0.3,
        max_tokens=512,
        timeout=30,
    )

    prompt = f"""分析以下用户在小说创作过程中写的文本，判断其中是否隐含了用户的内容偏好/审美倾向。

用户文本：
{text}

已有画像（避免重复提取）：
{existing_profile if existing_profile else '（空）'}

提取规则：
- 只提取关于内容偏好的信息（角色类型偏好、关系模式偏好、剧情节奏偏好等）
- 不提取写作风格偏好（那是文风管的）
- 不提取针对具体项目的设定（那是项目自己管的）
- 不提取已经在"已有画像"中存在的偏好
- 如果文本中没有可提取的偏好信息，返回空

如果提取到了偏好，用简短的条目格式输出（每条一行，以"- "开头）。
如果没有可提取的，只输出一个字：无"""

    result = invoke_with_cleaning(llm_adapter, prompt, enable_streaming=False)
    result = result.strip()
    if result == "无" or not result or len(result) < 3:
        return {"preferences": ""}
    return {"preferences": result}


@router.post("/config/user_profile/append")
def append_user_profile(body: dict):
    """将新偏好追加到现有画像"""
    new_preferences = body.get("preferences", "").strip()
    if not new_preferences:
        return {"message": "无新偏好"}
    data = _read_profile()
    existing = data.get("profile", "").strip()
    if existing:
        data["profile"] = existing + "\n" + new_preferences
    else:
        data["profile"] = new_preferences
    data["updated_at"] = datetime.now().isoformat()
    _write_profile(data)
    return {"message": "✅ 画像已更新"}


@router.put("/config/user_profile")
def save_user_profile(body: dict):
    profile_text = body.get("profile", "")
    enabled = body.get("enabled", True)
    data = {
        "profile": profile_text,
        "enabled": enabled,
        "updated_at": datetime.now().isoformat(),
    }
    _write_profile(data)
    return {"message": "✅ 用户画像已保存"}


# ── 审校模型配置 ──────────────────────────────────────────────────────────────

@router.get("/config/quality_guard")
def get_quality_guard_config():
    app = get_web_app()
    default_cfg = {
        "enabled": False,
        "reviewer_engine": "gemini-4-hydrogen-medium",
        "reviewer_llm_config": "Gemini 4 Hydrogen (Medium)",
        "codex_model": "",
        "zhuque_enabled": False,
        "zhuque_api_key": "",
        "zhuque_threshold": 20.0,
    }
    cfg = app.config.get("quality_guard_setting", default_cfg)
    return cfg


@router.post("/config/quality_guard")
def save_quality_guard_config(body: dict):
    app = get_web_app()
    current = app.config.get("quality_guard_setting", {})
    reviewer_llm = str(body.get("reviewer_llm_config", current.get("reviewer_llm_config", "Gemini 4 Hydrogen (Medium)"))).strip()
    current.update({
        "enabled": bool(body.get("enabled", False)),
        "reviewer_engine": str(body.get("reviewer_engine", "gemini-4-hydrogen-medium")).strip(),
        "reviewer_llm_config": reviewer_llm,
        "codex_model": str(body.get("codex_model", "")).strip(),
        "zhuque_enabled": bool(body.get("zhuque_enabled", False)),
        "zhuque_api_key": str(body.get("zhuque_api_key", "")).strip(),
        "zhuque_threshold": float(body.get("zhuque_threshold", 20.0)),
    })
    app.config["quality_guard_setting"] = current
    if reviewer_llm and reviewer_llm in app.config.get("llm_configs", {}):
        choose = app.config.setdefault("choose_configs", {})
        choose["final_chapter_llm"] = reviewer_llm
        choose["consistency_review_llm"] = reviewer_llm
    from config_manager import save_config
    save_config(app.config, app.config_file)
    return {"success": True, "message": "✅ 审校模型配置已保存", "data": current}


@router.post("/config/zhuque/test")
def test_zhuque_api(body: dict):
    """测试腾讯云朱雀自检 API Key 连通性"""
    key = body.get("zhuque_api_key", "").strip()
    if not key:
        return {"success": False, "message": "请先输入腾讯云 EdgeOne 朱雀 API Key"}

    from novel_generator.zhuque_client import ZhuqueAuditClient
    client = ZhuqueAuditClient(api_key=key, timeout=10)
    test_text = "这是一段用于测试腾讯云朱雀 AIGC 文本自检 API 连通性的文本内容。"
    res = client.check_chunk(test_text)
    if res.get("ok"):
        return {
            "success": True,
            "message": f"✅ 朱雀自检 API 联调成功！置信度: {res.get('confidence', 0)}",
            "data": res
        }
    else:
        err = res.get("error", "未知错误")
        return {
            "success": False,
            "message": f"❌ 朱雀 API 请求失败: {err}"
        }


@router.post("/config/codex/test")
def test_codex_adapter(body: dict):
    """测试本地 Codex CLI 连通性与模型可用性"""
    model = body.get("codex_model", "").strip()
    from novel_generator.codex_adapter import CodexCLIAdapter
    adapter = CodexCLIAdapter(model_name=model, timeout=30)
    if not adapter.is_available():
        return {
            "success": False,
            "message": f"❌ 未在系统中检测到 codex 可执行文件，请确认本地已安装 Codex CLI"
        }
    try:
        reply = adapter.invoke(
            prompt="请只输出这行字：【Codex 引擎联调成功】",
            system_message="你正在接受连通性测试，请简短回答。",
            model=model
        )
        return {
            "success": True,
            "message": "✅ 本地 Codex CLI (GPT) 连通测试成功！",
            "reply": reply[:100]
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Codex 调用测试异常: {str(e)}"
        }


# ── 独立模型与 Provider 提供商管理中心（脱离 Antigravity 独立发行底座） ──────────────

_BUILTIN_PROVIDER_TEMPLATES = [
    {
        "id": "deepseek",
        "name": "DeepSeek 官方",
        "interface_format": "OpenAI",
        "base_url": "https://api.deepseek.com/v1",
        "default_models": ["deepseek-chat", "deepseek-reasoner"],
        "requires_key": True,
        "badge": "高性价比长文主力",
    },
    {
        "id": "gemini_openai",
        "name": "Google Gemini (OpenAI 兼容)",
        "interface_format": "OpenAI",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_models": ["gemini-2.5-flash", "gemini-2.5-pro"],
        "requires_key": True,
        "badge": "长上下文 / 去AI审校",
    },
    {
        "id": "openai",
        "name": "OpenAI 官方 / 中转站",
        "interface_format": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_models": ["gpt-4o", "gpt-4.1", "o3-mini"],
        "requires_key": True,
        "badge": "标准协议",
    },
    {
        "id": "siliconflow",
        "name": "硅基流动 (SiliconFlow)",
        "interface_format": "OpenAI",
        "base_url": "https://api.siliconflow.cn/v1",
        "default_models": ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-72B-Instruct"],
        "requires_key": True,
        "badge": "国内直连",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter 聚合",
        "interface_format": "OpenAI",
        "base_url": "https://openrouter.ai/api/v1",
        "default_models": ["anthropic/claude-3.7-sonnet", "google/gemini-2.5-pro"],
        "requires_key": True,
        "badge": "Claude / 多模型聚合",
    },
    {
        "id": "ollama",
        "name": "Ollama 本地模型（免 Key）",
        "interface_format": "Ollama",
        "base_url": "http://127.0.0.1:11434",
        "default_models": [],
        "requires_key": False,
        "badge": "本地离线隐私",
    },
    {
        "id": "lmstudio",
        "name": "LM Studio 本地服务",
        "interface_format": "ML Studio",
        "base_url": "http://127.0.0.1:1234/v1",
        "default_models": [],
        "requires_key": False,
        "badge": "本地 GGUF",
    },
    {
        "id": "custom",
        "name": "自定义 OpenAI 兼容站",
        "interface_format": "OpenAI",
        "base_url": "",
        "default_models": [],
        "requires_key": True,
        "badge": "OneAPI / NewAPI",
    },
    {
        "id": "antigravity_local",
        "name": "Antigravity (agy) 本机高级桥接",
        "interface_format": "Codex",
        "base_url": "",
        "default_models": ["gemini-3.8-flash-low", "gemini-4-hydrogen-medium"],
        "requires_key": False,
        "advanced": True,
        "badge": "仅限本机已装 agy 环境",
    },
]


@router.get("/config/providers")
def list_providers():
    import shutil
    app = get_web_app()
    saved = app.config.get("providers", [])
    has_agy = bool(shutil.which("agy"))
    templates = []
    for tpl in _BUILTIN_PROVIDER_TEMPLATES:
        item = dict(tpl)
        if item["id"] == "antigravity_local":
            item["available"] = has_agy
        else:
            item["available"] = True
        templates.append(item)
    return {"templates": templates, "saved": saved, "has_agy_cli": has_agy}


@router.post("/config/providers/save")
def save_provider(body: dict):
    """保存提供商配置并将勾选的模型一键同步到系统 llm_configs 供工作流节点选用。"""
    from config_manager import save_config
    app = get_web_app()
    pid = (body.get("id") or "").strip() or f"custom_{int(__import__('time').time())}"
    pname = (body.get("name") or pid).strip()
    iface = (body.get("interface_format") or "OpenAI").strip()
    base_url = (body.get("base_url") or "").strip()
    api_key = (body.get("api_key") or "").strip()
    selected_models = [str(m).strip() for m in (body.get("selected_models") or []) if str(m).strip()]

    providers = [p for p in app.config.get("providers", []) if p.get("id") != pid]
    record = {
        "id": pid,
        "name": pname,
        "interface_format": iface,
        "base_url": base_url,
        "api_key": api_key,
        "selected_models": selected_models,
        "enabled": bool(body.get("enabled", True)),
    }
    providers.append(record)
    app.config["providers"] = providers

    llm_configs = app.config.setdefault("llm_configs", {})
    for model_id in selected_models:
        cfg_label = f"{pname} · {model_id}" if not model_id.startswith(pname) else model_id
        llm_configs[cfg_label] = {
            "api_key": api_key or ("ollama" if iface in ("Ollama", "ML Studio", "Codex") else ""),
            "base_url": base_url,
            "model_name": model_id,
            "temperature": float(body.get("temperature", 0.7)),
            "max_tokens": int(body.get("max_tokens", 8192)),
            "timeout": int(body.get("timeout", 600)),
            "interface_format": iface,
            "provider_id": pid,
        }

    save_config(app.config, app.config_file)
    return {
        "success": True,
        "message": f"✅ 已保存「{pname}」并同步 {len(selected_models)} 个模型到节点可选列表",
        "provider": record,
        "llm_choices": list(llm_configs.keys()),
    }


@router.post("/config/providers/fetch_models")
def fetch_provider_models(body: dict):
    """自动拉取指定厂商或本地 Ollama/LM Studio 的可用模型列表。"""
    import requests
    import subprocess
    import re
    iface = (body.get("interface_format") or "OpenAI").strip()
    base_url = (body.get("base_url") or "").strip().rstrip("/")
    api_key = (body.get("api_key") or "").strip()

    try:
        if iface == "Ollama":
            url = (base_url or "http://127.0.0.1:11434") + "/api/tags"
            resp = requests.get(url, timeout=8)
            resp.raise_for_status()
            models = [m.get("name") for m in resp.json().get("models", []) if m.get("name")]
            return {"success": True, "models": sorted(models), "source": "ollama"}

        if iface == "Codex":
            proc = subprocess.run(["agy", "models"], capture_output=True, text=True, timeout=12)
            found = []
            for line in (proc.stdout or "").splitlines():
                m = re.match(r"^\s*([a-zA-Z0-9_.-]+)\s+", line)
                if m and m.group(1).lower() not in ("model", "id", "name", "---"):
                    found.append(m.group(1))
            return {"success": True, "models": found or ["gemini-3.8-flash-low", "gemini-4-hydrogen-medium"], "source": "agy"}

        if iface == "Google":
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            models = [
                m.name.replace("models/", "")
                for m in genai.list_models()
                if "generateContent" in getattr(m, "supported_generation_methods", [])
            ]
            return {"success": True, "models": sorted(models), "source": "google"}

        # OpenAI / DeepSeek / SiliconFlow / OpenRouter / LM Studio 兼容 /models
        if not base_url:
            return {"success": False, "models": [], "error": "请先填写 Base URL"}
        from llm_adapters import check_base_url
        eff_url = check_base_url(base_url).rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        resp = requests.get(f"{eff_url}/models", headers=headers, timeout=12)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        models = sorted({str(item.get("id")) for item in data if item.get("id")})
        return {"success": True, "models": models, "source": "openai_compat"}
    except Exception as e:
        return {"success": False, "models": [], "error": f"拉取失败: {str(e)}"}


@router.post("/config/providers/test_connection")
def test_provider_connection(body: dict):
    """快速单次测速并验证提供商连通性。"""
    import time
    iface = (body.get("interface_format") or "OpenAI").strip()
    base_url = (body.get("base_url") or "").strip()
    api_key = (body.get("api_key") or "").strip()
    model_name = (body.get("model_name") or "").strip()
    if not model_name:
        return {"ok": False, "latency_ms": 0, "error": "请先选择或填写一个测试模型名"}
    t0 = time.time()
    try:
        adapter = create_llm_adapter(
            interface_format=iface,
            base_url=base_url,
            model_name=model_name,
            api_key=api_key or "ollama",
            temperature=0.2,
            max_tokens=32,
            timeout=25,
        )
        reply = adapter.invoke("Reply OK")
        ms = int((time.time() - t0) * 1000)
        if reply and str(reply).strip():
            return {"ok": True, "latency_ms": ms, "reply": str(reply).strip()[:120]}
        return {"ok": False, "latency_ms": ms, "error": "模型返回为空"}
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        return {"ok": False, "latency_ms": ms, "error": str(e)}
