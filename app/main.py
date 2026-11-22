import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 顶级直接导入以触发 @register_node 自动注册
import app.nodes
from app.api.projects import projects_router
from app.api.runs import runs_router
from app.api.tools import tools_router
from app.api.workflows import workflows_router
from app.api.workflow import workflow_router
from app.api.ws import ws_router
from app.core.registry import NODE_REGISTRY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ComfyNovel")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("已加载并注册插件节点: %s", list(NODE_REGISTRY.keys()))
    yield


app = FastAPI(
    title="ComfyNovel DAG Studio Backend",
    version="2.2.0",
    description="千万字超长篇小说 ComfyUI 风格 DAG 引擎与人机协同创作系统",
    lifespan=lifespan,
)

# 允许跨域（支持前端 Vite 开发服务器与 Electron 桌面端）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载所有路由
app.include_router(ws_router)
app.include_router(runs_router)
app.include_router(workflow_router)
app.include_router(projects_router)
app.include_router(tools_router)
app.include_router(workflows_router)


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "registered_nodes": list(NODE_REGISTRY.keys()),
    }
