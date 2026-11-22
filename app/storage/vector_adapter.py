import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


class VectorStoreAdapter:
    """
    轻量本地嵌入式向量存储适配器：
    带有严格的生命周期元数据 (created_at_chapter, deprecated_at_chapter)，
    支持与结构化状态库双库同步时空倒流回滚。
    """
    def __init__(self, vector_dir: Path):
        self.vector_dir = vector_dir
        self.db_path = self.vector_dir / "vector_chunks.db"
        self._init_db()

    def _init_db(self):
        self.vector_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vector_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    title TEXT,
                    content TEXT NOT NULL,
                    created_at_chapter INTEGER NOT NULL,
                    deprecated_at_chapter INTEGER,
                    scope TEXT DEFAULT 'global',
                    metadata_json TEXT
                )
            """)
            conn.commit()

    def add_chunk(
        self,
        chunk_id: str,
        content: str,
        created_at_chapter: int,
        title: str = "",
        deprecated_at_chapter: Optional[int] = None,
        scope: str = "global",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO vector_chunks
                (chunk_id, title, content, created_at_chapter, deprecated_at_chapter, scope, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk_id,
                title,
                content,
                created_at_chapter,
                deprecated_at_chapter,
                scope,
                json.dumps(metadata or {}, ensure_ascii=False)
            ))
            conn.commit()

    def query_active_chunks(self, current_chapter: int, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        检索当前章节合法的记忆切片：
        1. created_at_chapter <= current_chapter（防未来剧透）
        2. deprecated_at_chapter IS NULL OR deprecated_at_chapter > current_chapter（非已被废弃条目）
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = """
                SELECT * FROM vector_chunks
                WHERE created_at_chapter <= ?
                  AND (deprecated_at_chapter IS NULL OR deprecated_at_chapter > ?)
            """
            params: List[Any] = [current_chapter, current_chapter]
            if scope:
                query += " AND (scope = 'global' OR scope = ?)"
                params.append(scope)

            rows = cursor.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def rollback_to_chapter(self, target_chapter: int) -> Dict[str, int]:
        """
        向量库时空同步回滚两步走：
        1. 清理未来记忆：物理删除 created_at_chapter > target_chapter 的切片
        2. 复活历史设定：将 deprecated_at_chapter > target_chapter 的条目恢复为 NULL
        """
        deleted_count = 0
        revived_count = 0
        with sqlite3.connect(str(self.db_path)) as conn:
            # 1. 删除未来
            cursor = conn.execute(
                "DELETE FROM vector_chunks WHERE created_at_chapter > ?",
                (target_chapter,)
            )
            deleted_count = cursor.rowcount

            # 2. 复活历史
            cursor = conn.execute(
                "UPDATE vector_chunks SET deprecated_at_chapter = NULL WHERE deprecated_at_chapter > ?",
                (target_chapter,)
            )
            revived_count = cursor.rowcount
            conn.commit()

        return {"deleted_future_chunks": deleted_count, "revived_history_chunks": revived_count}
