import shutil
import tempfile
import unittest
from app.schemas.project import ProjectConfig
from app.storage.project_bundle import ProjectBundle
from app.storage.vector_adapter import VectorStoreAdapter
from app.storage.rollback_manager import NovelStateManager


class TestPhase3RollbackAndVectors(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.bundle = ProjectBundle(self.test_dir)
        self.bundle.init_project(ProjectConfig(
            project_id="test_rollback",
            title="太虚剑尊回滚测试",
            genre="修仙"
        ))
        self.vector_adapter = VectorStoreAdapter(self.bundle.vector_dir)
        self.state_mgr = NovelStateManager(self.bundle, self.vector_adapter)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_json_patch_replay_and_dual_store_rollback(self):
        # 1. 提交第 10 章全量快照
        init_state = {
            "characters": {
                "linfeng": {"realm": "金丹后期", "injury": "无", "weapons": ["青灵剑"]}
            },
            "world": {"current_map": "东洲"}
        }
        self.state_mgr.commit_chapter(
            chapter_index=10,
            diff_patches=[],
            full_state=init_state,
            is_full_snapshot=True
        )

        # 2. 第 11 章：主角突破至元婴初期 (replace)
        self.state_mgr.commit_chapter(
            chapter_index=11,
            diff_patches=[{
                "op": "replace",
                "path": "/characters/linfeng/realm",
                "new_value": "元婴初期",
                "evidence_quote": "金丹碎裂，一尊三寸元婴赫然跃出...",
                "approved": True
            }]
        )

        # 3. 第 12 章：主角左臂受创 (replace) 并捡到生锈铜片 (add)
        self.state_mgr.commit_chapter(
            chapter_index=12,
            diff_patches=[
                {
                    "op": "replace",
                    "path": "/characters/linfeng/injury",
                    "new_value": "左臂经脉撕裂",
                    "evidence_quote": "咔嚓一声，林风左臂经脉崩裂",
                    "approved": True
                },
                {
                    "op": "add",
                    "path": "/characters/linfeng/weapons/-",
                    "new_value": "神秘生锈铜片",
                    "evidence_quote": "他在青石下拾起一枚暗青色铜片",
                    "approved": True
                }
            ]
        )

        # 4. 第 13 章（未来写偏的章节）：主角前往中州拍卖行并把铜片卖了 (remove)
        self.state_mgr.commit_chapter(
            chapter_index=13,
            diff_patches=[
                {
                    "op": "replace",
                    "path": "/world/current_map",
                    "new_value": "中州",
                    "evidence_quote": "跨过传送阵，已是繁华中州",
                    "approved": True
                }
            ]
        )

        # 同时向向量库写入记忆
        # 切片 A：第 10 章写入的古籍（一直有效）
        self.vector_adapter.add_chunk(
            chunk_id="chunk_lore_ancient",
            content="东洲青云山下封印着上古剑冢",
            created_at_chapter=10
        )
        # 切片 B：第 11 章有效，第 13 章被废弃（比如误以为某秘密是假的）
        self.vector_adapter.add_chunk(
            chunk_id="chunk_secret_elder",
            content="大长老是内奸",
            created_at_chapter=11,
            deprecated_at_chapter=13
        )
        # 切片 C：第 13 章写入的未来记忆（中州拍卖行老板身份）
        self.vector_adapter.add_chunk(
            chunk_id="chunk_future_zhongzhou",
            content="中州拍卖行行长是赵无极",
            created_at_chapter=13
        )

        # 校验在第 13 章时：
        state_13 = self.state_mgr.restore_state_at_chapter(13)
        self.assertEqual(state_13["characters"]["linfeng"]["realm"], "元婴初期")
        self.assertEqual(state_13["characters"]["linfeng"]["injury"], "左臂经脉撕裂")
        self.assertIn("神秘生锈铜片", state_13["characters"]["linfeng"]["weapons"])
        self.assertEqual(state_13["world"]["current_map"], "中州")

        # 校验向量库在第 13 章可见性：
        # 切片 B 在第 13 章被废弃，不可见；切片 C 在第 13 章可见
        chunks_at_13 = self.vector_adapter.query_active_chunks(current_chapter=13)
        chunk_ids_13 = [c["chunk_id"] for c in chunks_at_13]
        self.assertIn("chunk_lore_ancient", chunk_ids_13)
        self.assertNotIn("chunk_secret_elder", chunk_ids_13)
        self.assertIn("chunk_future_zhongzhou", chunk_ids_13)

        # ==============================================================
        # 核心回滚测试：发现第 13 章写崩，一键回滚到第 12 章！
        # ==============================================================
        rollback_res = self.state_mgr.rollback_to_chapter(target_chapter=12)

        # 1. 结构化库验证：地图应还原回东洲，但第 12 章的元婴和伤势保留
        restored_state = rollback_res["restored_state"]
        self.assertEqual(restored_state["world"]["current_map"], "东洲")
        self.assertEqual(restored_state["characters"]["linfeng"]["realm"], "元婴初期")
        self.assertEqual(restored_state["characters"]["linfeng"]["injury"], "左臂经脉撕裂")
        self.assertIn("神秘生锈铜片", restored_state["characters"]["linfeng"]["weapons"])

        # 2. 向量库验证：
        # - 切片 C（第 13 章写入）已被物理抹杀
        # - 切片 B（原在第 13 章废弃）已被复活，deprecated_at_chapter 恢复为 None
        chunks_at_12 = self.vector_adapter.query_active_chunks(current_chapter=12)
        chunk_ids_12 = [c["chunk_id"] for c in chunks_at_12]
        self.assertIn("chunk_lore_ancient", chunk_ids_12)
        self.assertIn("chunk_secret_elder", chunk_ids_12, "第 13 章被推翻的秘密在回滚后应成功复活")
        self.assertNotIn("chunk_future_zhongzhou", chunk_ids_12, "第 13 章未来记忆应被彻底清除")


if __name__ == "__main__":
    unittest.main()
