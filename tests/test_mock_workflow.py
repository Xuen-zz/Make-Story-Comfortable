import asyncio
import unittest
from httpx import ASGITransport, AsyncClient
from app.main import app


class TestMockWorkflow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_mock_workflow_run_resume_flow(self):
        # 1. 启动 Mock 工作流
        run_resp = await self.client.post("/api/workflow/run", json={
            "client_id": "test_client_mock",
            "nodes": [],
            "edges": []
        })
        self.assertEqual(run_resp.status_code, 200)
        task_id = run_resp.json()["task_id"]
        self.assertTrue(task_id.startswith("task_"))

        # 等待其走到断点挂起（约 1.4s）
        await asyncio.sleep(1.6)

        # 2. 模拟前端人工微调后恢复执行
        resume_resp = await self.client.post("/api/workflow/resume", json={
            "client_id": "test_client_mock",
            "task_id": task_id,
            "node_id": "node_prompt",
            "override_payload": {
                "instruction": "增强肃杀与拔剑音效的细节描写"
            }
        })
        self.assertEqual(resume_resp.status_code, 200)
        self.assertEqual(resume_resp.json()["status"], "resumed")

        # 3. 等待正文模拟推流完毕
        await asyncio.sleep(1.0)

    async def test_mock_workflow_cancel_flow(self):
        run_resp = await self.client.post("/api/workflow/run", json={
            "client_id": "test_client_cancel",
            "nodes": [],
            "edges": []
        })
        task_id = run_resp.json()["task_id"]

        # 模拟运行中点击一键中止
        await asyncio.sleep(0.2)
        cancel_resp = await self.client.post("/api/workflow/cancel", json={
            "client_id": "test_client_cancel",
            "task_id": task_id
        })
        self.assertEqual(cancel_resp.status_code, 200)
        self.assertEqual(cancel_resp.json()["status"], "cancelling")


if __name__ == "__main__":
    unittest.main()
