import asyncio
import shutil
import tempfile
import unittest
from app.core.dag_engine import execute_dag
from app.core.subgraph import SubgraphTemplate, flatten_subgraphs
from app.schemas.graph import GraphDef, NodeDef, EdgeDef, RunState
from app.schemas.project import ProjectConfig
from app.services.inpainting import slice_inpaint_context
from app.services.linter import NovelLinter
from app.storage.project_bundle import ProjectBundle


class TestPhase4AuthoringTools(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bundle = ProjectBundle(self.test_dir)
        self.bundle.init_project(ProjectConfig(
            project_id="test_p4",
            title="高阶效能测试",
            genre="修仙"
        ))

    async def asyncTearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_subgraph_flattening_and_execution(self):
        # 1. 定义子图模板：内部包含 rag_retriever 和 context_router
        sub_template = SubgraphTemplate(
            template_id="sub_context_pack",
            name="资产装配子图",
            input_node_id="inner_rag",
            output_node_id="inner_router",
            graph=GraphDef(
                nodes=[
                    NodeDef(id="inner_rag", type="rag_retriever", params={"query": "太虚剑冢"}),
                    NodeDef(id="inner_router", type="context_router")
                ],
                edges=[
                    EdgeDef(source="inner_rag", target="inner_router")
                ]
            )
        )

        # 2. 外部主画布：只有一个子图节点和一个正文生成节点
        outer_graph = GraphDef(
            nodes=[
                NodeDef(
                    id="my_subgraph_01",
                    type="subgraph",
                    params={
                        "template_id": "sub_context_pack",
                        "overrides": {
                            "inner_rag": {"query": "覆写后的剑冢query"}
                        }
                    }
                ),
                NodeDef(id="node_llm", type="llm_sampler", params={"mock_text": "万剑齐鸣！"})
            ],
            edges=[
                EdgeDef(source="my_subgraph_01", target="node_llm")
            ]
        )

        # 3. 执行扁平化展开
        flattened = flatten_subgraphs(outer_graph, {"sub_context_pack": sub_template})

        # 检查节点：应展开为 3 个真实节点
        node_ids = [n.id for n in flattened.nodes]
        self.assertIn("my_subgraph_01__inner_rag", node_ids)
        self.assertIn("my_subgraph_01__inner_router", node_ids)
        self.assertIn("node_llm", node_ids)

        # 检查参数覆写
        rag_node = next(n for n in flattened.nodes if n.id == "my_subgraph_01__inner_rag")
        self.assertEqual(rag_node.params["query"], "覆写后的剑冢query")

        # 检查连线重定向：连出子图的线应从 inner_router 连向 node_llm
        edge_pairs = [(e.source, e.target) for e in flattened.edges]
        self.assertIn(("my_subgraph_01__inner_rag", "my_subgraph_01__inner_router"), edge_pairs)
        self.assertIn(("my_subgraph_01__inner_router", "node_llm"), edge_pairs)

    def test_inpaint_context_slicing(self):
        full_text = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        # 划选 10 到 20 的字符（即 'ABCDEFGHIJ'）
        slices = slice_inpaint_context(full_text, start=10, end=20, window=5)
        self.assertEqual(slices["prefix"], "56789")
        self.assertEqual(slices["target"], "ABCDEFGHIJ")
        self.assertEqual(slices["suffix"], "KLMNO")

    def test_linter_scan_overdue_hooks(self):
        linter = NovelLinter(overdue_threshold=50)
        hooks = [
            {
                "hook_id": "h1",
                "summary": "破庙生锈铜片",
                "status": "unresolved",
                "planted_chapter": 10
            },
            {
                "hook_id": "h2",
                "summary": "大长老的诡异眼神",
                "status": "resolved",  # 已解决
                "planted_chapter": 5
            },
            {
                "hook_id": "h3",
                "summary": "刚得到的灵药",
                "status": "unresolved",
                "planted_chapter": 90  # 距离 100 只有 10 章，未超期
            }
        ]

        # 在第 100 章体检：h1 超期 90 章 (>= 50)，应被抓出；h2已解决，h3未超期
        issues = linter.scan_overdue_foreshadowing(current_chapter=100, foreshadowing_list=hooks)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].category, "OVERDUE_HOOK")
        self.assertIn("破庙生锈铜片", issues[0].description)
        self.assertEqual(issues[0].chapter_ref, 10)


if __name__ == "__main__":
    unittest.main()
