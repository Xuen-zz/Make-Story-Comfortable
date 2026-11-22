# api_server.py
# -*- coding: utf-8 -*-
"""
NovelFlow Studio FastAPI 后端引擎入口
支持本地开发直跑与 Electron 桌面端 PyInstaller Sidecar 模式：
    python api_server.py [--host 127.0.0.1] [--port 7860] [--data-dir <path>]
"""

import argparse
import os
import sys
import shutil
import logging

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["ANONYMIZED_TELEMETRY"] = "False"


def _parse_cli_early():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("NOVELFLOW_PORT", "7860")))
    parser.add_argument("--data-dir", default="")
    args, _ = parser.parse_known_args()
    if args.data_dir:
        os.environ["NOVELFLOW_DATA_DIR"] = os.path.abspath(args.data_dir)
    return args


_CLI_ARGS = _parse_cli_early()

from app_paths import get_bundle_root, get_data_dir, get_data_file, get_books_root, set_books_root

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(get_data_file("app.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

APP_VERSION = "2.1.1"

app = FastAPI(
    title="NovelFlow Studio API",
    description="AI 小说工作流引擎（ComfyUI 风格桌面端后端）",
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 挂载路由 ─────────────────────────────────────────────────────────────────

from api.routers import (
    assets,
    projects, config, presets, generate,
    styles, knowledge, files, logs, consistency, xp_presets,
    brainstorm, workflow,
)

app.include_router(projects.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(presets.router, prefix="/api")
app.include_router(generate.router, prefix="/api")
app.include_router(styles.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(consistency.router, prefix="/api")
app.include_router(xp_presets.router, prefix="/api")
app.include_router(brainstorm.router, prefix="/api")
app.include_router(workflow.router, prefix="/api")
app.include_router(assets.router, prefix="/api")

# ── ComfyNovel DAG 引擎与超长篇协同路由 ─────────────────────────────
import app.nodes as _comfy_nodes
from app.api.ws import ws_router
from app.api.runs import runs_router
from app.api.workflow import workflow_router as dag_mock_workflow_router
from app.api.projects import projects_router as dag_projects_router
from app.api.tools import tools_router
from app.api.workflows import workflows_router

app.include_router(ws_router)
app.include_router(runs_router)
app.include_router(dag_mock_workflow_router)
app.include_router(dag_projects_router)
app.include_router(tools_router)
app.include_router(workflows_router)



# ── 健康检查与桌面系统信息 ────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "version": APP_VERSION}


@app.get("/api/system/info")
def system_info():
    from api.app_state import get_web_app
    web_app = get_web_app()
    llm_cfgs = web_app.config.get("llm_configs", {})
    has_configured_model = any(
        (v.get("api_key") or "").strip() not in ("", "your-api-key")
        or v.get("interface_format") in ("Ollama", "ML Studio")
        for v in llm_cfgs.values()
    )
    return {
        "version": APP_VERSION,
        "data_dir": get_data_dir(),
        "books_root": get_books_root(),
        "has_agy_cli": bool(shutil.which("agy")),
        "has_configured_model": has_configured_model,
        "model_count": len(llm_cfgs),
    }


class _BooksRootReq(BaseModel):
    books_root: str


@app.post("/api/system/books_root")
def update_books_root(body: _BooksRootReq):
    saved = set_books_root(body.books_root)
    return {"success": True, "books_root": saved}


# ── 生产模式：serve Vue 构建产物 ───────────────────────────────────────────────

_frontend_dist = os.path.join(get_bundle_root(), "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="static")
    logging.getLogger(__name__).info(f"Serving frontend from {_frontend_dist}")
else:
    logging.getLogger(__name__).info(
        "Frontend dist not found. Run 'cd frontend && npm run build' to build the UI."
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=_CLI_ARGS.host, port=_CLI_ARGS.port, reload=False)
