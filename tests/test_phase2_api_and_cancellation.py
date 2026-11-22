import asyncio
import os
import shutil
import tempfile
import unittest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.dependencies import set_active_project
from app.schemas.project import ProjectConfig
from app.storage.project_bundle import ProjectBundle


class TestPhase2ApiAndCancellation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bundle = ProjectBundle(self.test_dir)
        self.bundle.init_project(ProjectConfig(
            project_id="test_p2",
            title="API与取消测试",
            genre="科幻"
        ))
        set_active_project(self.bundle)
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_health_check(self):
        resp = await self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("rag_retriever", data["registered_nodes"])
        self.assertIn("llm_sampler", data["registered_nodes"])

    async def test_api_run_and_status(self):
        graph_payload = {
            "client_id": "client_test_01",
            "graph": {
                "nodes": [
                    {"id": "node_rag", "type": "rag_retriever", "params": {"query": "星舰"}},
                    {"id": "node_llm", "type": "llm_sampler", "params": {"mock_text": "曲率引擎已启动..."}}
                ],
                "edges": [
                    {"source": "node_rag", "target": "node_llm"}
                ]
            }
        }
        start_resp = await self.client.post("/api/runs", json=graph_payload)
        self.assertEqual(start_resp.status_code, 200)
        run_id = start_resp.json()["run_id"]

        # 异步等待后台任务在当前事件循环中完成
        completed = False
        for _ in range(50):
            await asyncio.sleep(0.05)
            status_resp = await self.client.get(f"/api/runs/{run_id}")
            if status_resp.status_code == 200 and status_resp.json().get("status") == "COMPLETED":
                completed = True
                break

        self.assertTrue(completed, "工作流应在短时间内执行完成")

    async def test_api_breakpoint_and_resume(self):
        graph_payload = {
            "client_id": "client_test_02",
            "graph": {
                "nodes": [
                    {"id": "node_rag", "type": "rag_retriever", "params": {"query": "星舰"}},
                    {"id": "node_router", "type": "context_router", "is_breakpoint": True},
                    {"id": "node_llm", "type": "llm_sampler", "params": {"mock_text": "【审批后】主炮充能完毕！"}}
                ],
                "edges": [
                    {"source": "node_rag", "target": "node_router"},
                    {"source": "node_router", "target": "node_llm"}
                ]
            }
        }
        start_resp = await self.client.post("/api/runs", json=graph_payload)
        run_id = start_resp.json()["run_id"]

        # 等待其挂起在 PAUSED
        paused = False
        for _ in range(50):
            await asyncio.sleep(0.05)
            status_resp = await self.client.get(f"/api/runs/{run_id}")
            if status_resp.status_code == 200 and status_resp.json().get("status") == "PAUSED":
                paused = True
                break

        self.assertTrue(paused, "工作流应在断点处成功挂起")

        # 调用 resume
        resume_payload = {
            "client_id": "client_test_02",
            "modified_output": {
                "protocol_version": "1.0",
                "port_type": "PROMPT_CONTEXT",
                "payload": {"assembled_prompt": "人工确认的星舰指令"}
            }
        }
        resume_resp = await self.client.post(f"/api/runs/{run_id}/resume", json=resume_payload)
        self.assertEqual(resume_resp.status_code, 200)

        # 验证下游继续执行直到 COMPLETED
        resumed_completed = False
        for _ in range(50):
            await asyncio.sleep(0.05)
            status_resp = await self.client.get(f"/api/runs/{run_id}")
            if status_resp.status_code == 200 and status_resp.json().get("status") == "COMPLETED":
                resumed_completed = True
                break

        self.assertTrue(resumed_completed, "恢复后下游节点应继续执行至完成")

    async def test_api_cancel_paused_run(self):
        graph_payload = {
            "client_id": "client_test_03",
            "graph": {
                "nodes": [
                    {"id": "node_rag", "type": "rag_retriever"},
                    {"id": "node_router", "type": "context_router", "is_breakpoint": True}
                ],
                "edges": [
                    {"source": "node_rag", "target": "node_router"}
                ]
            }
        }
        start_resp = await self.client.post("/api/runs", json=graph_payload)
        run_id = start_resp.json()["run_id"]

        # 等待 PAUSED
        for _ in range(50):
            await asyncio.sleep(0.05)
            status_resp = await self.client.get(f"/api/runs/{run_id}")
            if status_resp.status_code == 200 and status_resp.json().get("status") == "PAUSED":
                break

        # 发送 cancel 请求
        cancel_resp = await self.client.post(f"/api/runs/{run_id}/cancel?client_id=client_test_03")
        self.assertEqual(cancel_resp.status_code, 200)
        self.assertEqual(cancel_resp.json()["status"], "CANCELLED")

        # 再次获取状态确认是 CANCELLED
        final_status = (await self.client.get(f"/api/runs/{run_id}")).json()
        self.assertEqual(final_status["status"], "CANCELLED")


if __name__ == "__main__":
    unittest.main()
