from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.dependencies import get_project_bundle
from app.storage.project_bundle import ProjectBundle

workflows_router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class SaveWorkflowRequest(BaseModel):
    name: str
    graph: Dict[str, Any]


@workflows_router.get("", response_model=List[str])
async def list_workflows(bundle: ProjectBundle = Depends(get_project_bundle)):
    """获取所有已保存的工作流模板名称列表"""
    files = bundle.workflows_dir.glob("*.json")
    return [f.stem for f in files]


@workflows_router.get("/{name}", response_model=Dict[str, Any])
async def get_workflow(name: str, bundle: ProjectBundle = Depends(get_project_bundle)):
    """获取指定工作流模板"""
    try:
        return bundle.load_workflow(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"未找到模板: {name}")


@workflows_router.post("", response_model=Dict[str, str])
async def save_workflow(
    req: SaveWorkflowRequest,
    bundle: ProjectBundle = Depends(get_project_bundle),
):
    """保存或更新工作流模板"""
    bundle.save_workflow(req.name, req.graph)
    return {"status": "SAVED", "name": req.name}
