import asyncio
import os
import shutil
import tempfile
import unittest
import app.nodes  # 触发节点自动注册
from app.core.dag_engine import execute_dag, compute_cache_key
from app.schemas.graph import GraphDef, NodeDef, EdgeDef, RunState
from app.schemas.payload import EnvelopePayload, PortType
from app.schemas.project import ProjectConfig
from app.storage.project_bundle import ProjectBundle


class TestPhase1DagEngine(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bundle = ProjectBundle(self.test_dir)
        self.bundle.init_project(ProjectConfig(
            project_id="test_dag",
            title="太虚剑尊测试",
            genre="修仙"
        ))
        self.events = []

    async def asyncTearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def mock_ws_emitter(self, client_id: str, event: str, data: dict):
        self.events.append((event, data))

    async def test_full_dag_execution(self):
        """测试 4 节点完整流水线并发执行"""
        graph = GraphDef(
            nodes=[
                NodeDef(id="node_rag", type="rag_retriever", params={"query": "拍卖行"}),
                NodeDef(id="node_char", type="char_state_loader", params={"name": "林风"}),
                NodeDef(id="node_router", type="context_router"),
                NodeDef(id="node_llm", type="llm_sampler", params={"mock_text": "林风走入拍卖行..."}),
            ],
            edges=[
                EdgeDef(source="node_rag", target="node_router"),
                EdgeDef(source="node_char", target="node_router"),
                EdgeDef(source="node_router", target="node_llm"),
            ]
        )

        run_state = RunState(run_id="run_test_full", graph=graph)
        await execute_dag(run_state, client_id="c1", bundle=self.bundle, ws_emitter=self.mock_ws_emitter)

        self.assertEqual(run_state.status, "COMPLETED")
        self.assertIn("node_llm", run_state.context)
        llm_out = run_state.context["node_llm"]
        self.assertEqual(llm_out.port_type, PortType.CHAPTER_TEXT)
        self.assertIn("林风走入拍卖行", llm_out.payload["text"])

        # 验证 SQLite 中已持久化运行记录与节点缓存
        loaded_run = self.bundle.load_run("run_test_full")
        self.assertEqual(loaded_run["status"], "COMPLETED")

    async def test_sha256_dirty_check_cache(self):
        """测试脏检查缓存：二次运行时上游资产毫秒级命中 CACHED"""
        graph = GraphDef(
            nodes=[
                NodeDef(id="node_rag", type="rag_retriever", params={"query": "拍卖行"}),
            ],
            edges=[]
        )

        # 第一次执行：冷启动运行
        run_1 = RunState(run_id="run_c1", graph=graph)
        await execute_dag(run_1, client_id="c1", bundle=self.bundle, ws_emitter=self.mock_ws_emitter)
        self.assertEqual(run_1.status, "COMPLETED")

        # 清空事件记录
        self.events.clear()

        # 第二次执行：参数与输入完全相同，应命中 CACHED
        run_2 = RunState(run_id="run_c2", graph=graph)
        await execute_dag(run_2, client_id="c1", bundle=self.bundle, ws_emitter=self.mock_ws_emitter)
        self.assertEqual(run_2.status, "COMPLETED")

        # 检查是否推了 CACHED 事件
        cached_events = [e for e in self.events if e[0] == "NODE_STATUS" and e[1].get("status") == "CACHED"]
        self.assertTrue(len(cached_events) > 0)

    async def test_breakpoint_pause_and_resume(self):
        """测试人工断点挂起与无状态恢复"""
        graph = GraphDef(
            nodes=[
                NodeDef(id="node_rag", type="rag_retriever", params={"query": "拍卖行"}),
                NodeDef(id="node_router", type="context_router", is_breakpoint=True),
                NodeDef(id="node_llm", type="llm_sampler", params={"mock_text": "【断点后正文】剑气破空！"}),
            ],
            edges=[
                EdgeDef(source="node_rag", target="node_router"),
                EdgeDef(source="node_router", target="node_llm"),
            ]
        )

        # 1. 触发执行：在 node_router 处遇到断点，应暂停
        run_state = RunState(run_id="run_bp_01", graph=graph)
        await execute_dag(run_state, client_id="c1", bundle=self.bundle, ws_emitter=self.mock_ws_emitter)

        self.assertEqual(run_state.status, "PAUSED")
        self.assertEqual(run_state.paused_node_id, "node_router")
        self.assertIsNotNone(run_state.paused_inputs)
        self.assertNotIn("node_llm", run_state.context)

        # 2. 模拟前端人工微调/审批后调用 resume：
        # 将微调后的 modified_output 填入断点节点的 context 槽位
        modified_output = EnvelopePayload(
            port_type=PortType.PROMPT_CONTEXT,
            payload={"assembled_prompt": "【人工微调后的提示词】"}
        )
        run_state.context["node_router"] = modified_output
        run_state.paused_node_id = None
        run_state.paused_inputs = None

        # 3. 原地续跑 execute_dag：直接跳过已完成节点，执行 node_llm
        await execute_dag(run_state, client_id="c1", bundle=self.bundle, ws_emitter=self.mock_ws_emitter)

        self.assertEqual(run_state.status, "COMPLETED")
        self.assertIn("node_llm", run_state.context)
        self.assertIn("剑气破空", run_state.context["node_llm"].payload["text"])


if __name__ == "__main__":
    unittest.main()
