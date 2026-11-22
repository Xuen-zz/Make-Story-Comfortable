import json
import time
from typing import Any, Dict, List, Optional
import jsonpatch
from app.storage.project_bundle import ProjectBundle
from app.storage.vector_adapter import VectorStoreAdapter


class NovelStateManager:
    """
    超长篇小说双库同步版本控制与状态回滚管理器：
    1. 结构化状态库：基准快照 + JSON Patch 增量重放 + 软归档 (ARCHIVED)
    2. 向量库：按章节生命周期 Metadata 过滤与时空回退
    """
    def __init__(self, bundle: ProjectBundle, vector_adapter: Optional[VectorStoreAdapter] = None):
        self.bundle = bundle
        self.vector_adapter = vector_adapter or VectorStoreAdapter(bundle.vector_dir)

    def commit_chapter(
        self,
        chapter_index: int,
        diff_patches: List[Dict[str, Any]],
        full_state: Optional[Dict[str, Any]] = None,
        is_full_snapshot: bool = False,
    ) -> int:
        """提交某一章节的状态 Commit（全量快照或 JSON Patch 补丁列表）"""
        with self.bundle._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO chapter_commits
                    (chapter_index, is_full_snapshot, full_state_json, diff_patches_json, status, created_at)
                VALUES (?, ?, ?, ?, 'ACTIVE', ?)
                """,
                (
                    chapter_index,
                    1 if is_full_snapshot else 0,
                    json.dumps(full_state, ensure_ascii=False) if full_state else None,
                    json.dumps(diff_patches, ensure_ascii=False),
                    int(time.time()),
                ),
            )
            return cursor.lastrowid

    def get_latest_chapter_index(self) -> int:
        with self.bundle._get_conn() as conn:
            row = conn.execute(
                "SELECT MAX(chapter_index) as max_ch FROM chapter_commits WHERE status = 'ACTIVE'"
            ).fetchone()
            return row["max_ch"] if row and row["max_ch"] is not None else 0

    def restore_state_at_chapter(self, target_chapter: int) -> Dict[str, Any]:
        """
        按目标章节序号重构出当前世界精确的全局状态：
        1. 找到 <= target_chapter 最近的全量快照
        2. 依次按正序重放后续章节的 JSON Patch
        """
        with self.bundle._get_conn() as conn:
            # 找到最近基准快照
            base_row = conn.execute(
                """
                SELECT chapter_index, full_state_json FROM chapter_commits
                WHERE is_full_snapshot = 1 AND chapter_index <= ? AND status = 'ACTIVE'
                ORDER BY chapter_index DESC LIMIT 1
                """,
                (target_chapter,)
            ).fetchone()

            if base_row and base_row["full_state_json"]:
                base_ch = base_row["chapter_index"]
                current_state = json.loads(base_row["full_state_json"])
            else:
                base_ch = 0
                current_state = {}

            # 获取 base_ch 到 target_chapter 的增量补丁
            patch_rows = conn.execute(
                """
                SELECT chapter_index, diff_patches_json FROM chapter_commits
                WHERE chapter_index > ? AND chapter_index <= ? AND status = 'ACTIVE'
                ORDER BY chapter_index ASC
                """,
                (base_ch, target_chapter)
            ).fetchall()

            for row in patch_rows:
                patches_raw = json.loads(row["diff_patches_json"])
                # 过滤出 approved 的 RFC 6902 补丁
                clean_patches = []
                for p in patches_raw:
                    if p.get("approved", True):
                        patch_dict = {
                            "op": p["op"],
                            "path": p["path"],
                        }
                        if "value" in p:
                            patch_dict["value"] = p["value"]
                        elif "new_value" in p:
                            patch_dict["value"] = p["new_value"]
                        clean_patches.append(patch_dict)

                if clean_patches:
                    patch_obj = jsonpatch.JsonPatch(clean_patches)
                    current_state = patch_obj.apply(current_state)

            return current_state

    def rollback_to_chapter(self, target_chapter: int) -> Dict[str, Any]:
        """
        执行双库同步彻底回滚：
        1. 恢复 target_chapter 时的完整世界状态
        2. 将 > target_chapter 的 Commit 标记为 ARCHIVED
        3. 向量库删除未来切片并复活历史设定
        """
        # 1. 还原结构化状态
        restored_state = self.restore_state_at_chapter(target_chapter)

        # 2. 标记未来 Commit 为 ARCHIVED
        with self.bundle._get_conn() as conn:
            conn.execute(
                "UPDATE chapter_commits SET status = 'ARCHIVED' WHERE chapter_index > ?",
                (target_chapter,)
            )

        # 3. 向量库同步回滚
        vector_stats = self.vector_adapter.rollback_to_chapter(target_chapter)

        return {
            "target_chapter": target_chapter,
            "restored_state": restored_state,
            "vector_rollback_stats": vector_stats,
        }
