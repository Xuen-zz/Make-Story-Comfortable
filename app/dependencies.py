from pathlib import Path
from typing import Optional
from app.llm.router import ModelRouter, ModelProfile
from app.storage.project_bundle import ProjectBundle

# 全局默认工程目录与管理器单例
DEFAULT_PROJECT_DIR = Path("./projects/default_novel").resolve()
_active_bundle: Optional[ProjectBundle] = None
_model_router: Optional[ModelRouter] = None


def get_project_bundle() -> ProjectBundle:
    global _active_bundle
    if _active_bundle is None:
        _active_bundle = ProjectBundle(str(DEFAULT_PROJECT_DIR))
        if not _active_bundle.config_path.exists():
            from app.schemas.project import ProjectConfig
            _active_bundle.init_project(ProjectConfig(
                project_id="novel_default",
                title="默认修仙史诗",
                genre="修仙",
                iron_rules=["本世界无热武器", "主角不可提前知晓未来秘密"]
            ))
    return _active_bundle


def set_active_project(bundle: ProjectBundle):
    global _active_bundle
    _active_bundle = bundle


def get_model_router() -> ModelRouter:
    global _model_router
    if _model_router is None:
        _model_router = ModelRouter()
        # 默认注册 deepseek_chat 作为基础提取/便宜模型
        _model_router.register_profile(ModelProfile(
            profile_id="deepseek_chat",
            provider="deepseek",
            base_url="https://api.deepseek.com",
            api_key="sk-placeholder",
            model_name="deepseek-chat",
            default_temp=0.3,
        ))
        _model_router.bind_role("prose_writer", ["deepseek_chat"])
        _model_router.bind_role("fast_extractor", ["deepseek_chat"])
    return _model_router
