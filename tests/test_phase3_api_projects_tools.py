import os
import shutil
import tempfile
import unittest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.dependencies import set_active_project
from app.schemas.project import ProjectConfig
from app.storage.project_bundle import ProjectBundle


class TestPhase3ApiProjectsTools(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bundle = ProjectBundle(self.test_dir)
        self.bundle.init_project(ProjectConfig(
            project_id="test_api_tools",
            title="太虚剑尊测试",
            genre="修仙",
            iron_rules=["无热武器"]
        ))
        set_active_project(self.bundle)
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_project_config_api(self):
        resp = await self.client.get("/api/projects/config")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["title"], "太虚剑尊测试")

        # 更新配置
        data["iron_rules"].append("主角不可开上帝视角")
        update_resp = await self.client.post("/api/projects/config", json=data)
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(len(update_resp.json()["iron_rules"]), 2)

    async def test_chapter_commit_and_rollback_api(self):
        # 1. Commit 第 1 章状态
        commit_payload = {
            "chapter_index": 1,
            "diff_patches": [],
            "full_state": {"characters": {"linfeng": {"realm": "练气"}}},
            "is_full_snapshot": True
        }
        c1_resp = await self.client.post("/api/projects/commit", json=commit_payload)
        self.assertEqual(c1_resp.status_code, 200)

        # 2. Commit 第 2 章状态（突破）
        c2_payload = {
            "chapter_index": 2,
            "diff_patches": [{
                "op": "replace",
                "path": "/characters/linfeng/realm",
                "new_value": "筑基",
                "evidence_quote": "突破筑基期",
                "approved": True
            }],
            "is_full_snapshot": False
        }
        c2_resp = await self.client.post("/api/projects/commit", json=c2_payload)
        self.assertEqual(c2_resp.status_code, 200)

        # 3. 回滚至第 1 章
        rb_resp = await self.client.post("/api/projects/rollback", json={"target_chapter": 1})
        self.assertEqual(rb_resp.status_code, 200)
        restored = rb_resp.json()["restored_state"]
        self.assertEqual(restored["characters"]["linfeng"]["realm"], "练气")

    async def test_workflows_template_api(self):
        # 保存工作流模板
        save_resp = await self.client.post("/api/workflows", json={
            "name": "standard_write_flow",
            "graph": {"nodes": [], "edges": []}
        })
        self.assertEqual(save_resp.status_code, 200)

        # 获取模板列表
        list_resp = await self.client.get("/api/workflows")
        self.assertEqual(list_resp.status_code, 200)
        self.assertIn("standard_write_flow", list_resp.json())

        # 读取模板
        get_resp = await self.client.get("/api/workflows/standard_write_flow")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json(), {"nodes": [], "edges": []})

    async def test_lint_api_rule_scanner(self):
        lint_payload = {
            "current_chapter": 200,
            "foreshadowing_list": [
                {
                    "hook_id": "hook_old",
                    "summary": "神秘残图",
                    "status": "unresolved",
                    "planted_chapter": 10
                }
            ],
            "overdue_threshold": 50
        }
        lint_resp = await self.client.post("/api/tools/lint", json=lint_payload)
        self.assertEqual(lint_resp.status_code, 200)
        issues = lint_resp.json()["issues"]
        self.assertEqual(len(issues), 1)
        self.assertIn("神秘残图", issues[0]["description"])


if __name__ == "__main__":
    unittest.main()
