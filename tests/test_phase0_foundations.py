import os
import shutil
import tempfile
import unittest
from app.schemas.payload import EnvelopePayload, PortType
from app.schemas.diff import PatchItem, StateDiffOutput
from app.schemas.project import ProjectConfig
from app.storage.project_bundle import ProjectBundle
from app.llm.structured import extract_json_str


class TestPhase0Foundations(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_schema_envelope(self):
        env = EnvelopePayload(
            port_type=PortType.ASSET_BUNDLE,
            meta={"chapter_index": 512, "active_scope": ["vol_04", "map_zhongzhou"]},
            payload={"entities": [{"id": "char_linfeng", "realm": "元婴初期"}]}
        )
        self.assertEqual(env.port_type, "ASSET_BUNDLE")
        self.assertEqual(env.meta["chapter_index"], 512)
        self.assertEqual(len(env.payload["entities"]), 1)

    def test_rfc6902_patch_validation(self):
        # Valid patch with leading slash and evidence
        patch = PatchItem(
            target_type="entity",
            target_id="char_linfeng",
            op="replace",
            path="/custom_fields/injury",
            old_value="左臂受损",
            new_value="左臂经脉撕裂",
            evidence_quote="林风左臂如遭雷击，经脉彻底撕裂。",
            approved=True
        )
        self.assertEqual(patch.path, "/custom_fields/injury")

        # Invalid path missing leading slash
        with self.assertRaises(ValueError):
            PatchItem(
                target_type="entity",
                target_id="char_linfeng",
                op="replace",
                path="custom_fields/injury",
                evidence_quote="原句内容足够长",
            )

        # Invalid evidence quote too short
        with self.assertRaises(ValueError):
            PatchItem(
                target_type="entity",
                target_id="char_linfeng",
                op="replace",
                path="/test",
                evidence_quote="短",
            )

    def test_extract_json_str(self):
        raw = "这里是一些废话：\n```json\n{\"title\": \"太虚剑尊\", \"chapters\": 100}\n```\n希望你满意。"
        clean = extract_json_str(raw)
        self.assertEqual(clean, '{"title": "太虚剑尊", "chapters": 100}')

        raw2 = "回复如下： {\"key\": \"value\"} 谢谢"
        clean2 = extract_json_str(raw2)
        self.assertEqual(clean2, '{"key": "value"}')

    def test_project_bundle_sqlite_and_files(self):
        bundle = ProjectBundle(self.test_dir)
        cfg = ProjectConfig(
            project_id="test_001",
            title="太虚剑尊",
            genre="修仙",
            iron_rules=["无热武器", "主角不可上帝视角"]
        )
        bundle.init_project(cfg)

        # Check loaded config
        loaded_cfg = bundle.load_config()
        self.assertEqual(loaded_cfg.title, "太虚剑尊")
        self.assertEqual(len(loaded_cfg.iron_rules), 2)

        # Check cache ops
        bundle.set_cache("sha_test_123", "rag_retriever", {"hits": 5})
        cache_data = bundle.get_cache("sha_test_123")
        self.assertIsNotNone(cache_data)
        self.assertEqual(cache_data["hits"], 5)

        # Check workflow run save and load
        run_dict = {
            "run_id": "run_test_01",
            "status": "PAUSED",
            "graph": {"nodes": [], "edges": []},
            "context": {"node_1": {"port_type": "CHAPTER_TEXT", "payload": {"text": "hello"}}},
            "paused_node_id": "node_router",
            "paused_inputs": {"node_1": {"port_type": "CHAPTER_TEXT", "payload": {"text": "hello"}}}
        }
        bundle.save_run(run_dict)
        loaded_run = bundle.load_run("run_test_01")
        self.assertIsNotNone(loaded_run)
        self.assertEqual(loaded_run["status"], "PAUSED")
        self.assertEqual(loaded_run["paused_node_id"], "node_router")

        # Check chapter save & full export
        bundle.save_chapter(volume=1, chapter_index=1, title="破晓之剑", content="晨光微曦...")
        bundle.save_chapter(volume=1, chapter_index=2, title="云海争锋", content="剑气纵横...")
        export_file = bundle.root / "export.txt"
        bundle.export_full_txt(str(export_file))
        self.assertTrue(export_file.exists())
        text = export_file.read_text(encoding="utf-8")
        self.assertIn("破晓之剑", text)
        self.assertIn("云海争锋", text)


if __name__ == "__main__":
    unittest.main()
