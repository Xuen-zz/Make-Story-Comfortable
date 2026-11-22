import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.schemas.project import ProjectConfig


class ProjectBundle:
    """
    本地工程持久化管理器 (Project Bundle)
    收口 project.json、SQLite WAL (state.db)、vector_db/、workflows/、chapters/
    """
    def __init__(self, root_dir: str):
        self.root = Path(root_dir).resolve()
        self.config_path = self.root / "project.json"
        self.db_path = self.root / "state.db"
        self.vector_dir = self.root / "vector_db"
        self.workflows_dir = self.root / "workflows"
        self.chapters_dir = self.root / "chapters"

    @contextmanager
    def _get_conn(self):
        """每次操作获取独立连接，配合 WAL 模式避免高并发锁库"""
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ------------------------------------------
    # A. 工程初始化与配置读写
    # ------------------------------------------
    def init_project(self, config: ProjectConfig):
        """一键创建工程目录、project.json 和 SQLite 表结构"""
        for d in [self.root, self.vector_dir, self.workflows_dir, self.chapters_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.save_config(config)
        self._init_sqlite()

    def save_config(self, config: ProjectConfig):
        self.config_path.write_text(
            config.model_dump_json(indent=2), encoding="utf-8"
        )

    def load_config(self) -> ProjectConfig:
        if not self.config_path.exists():
            raise FileNotFoundError(f"未找到工程配置文件: {self.config_path}")
        return ProjectConfig.model_validate_json(
            self.config_path.read_text(encoding="utf-8")
        )

    def _init_sqlite(self):
        with self._get_conn() as conn:
            # 开启 WAL 模式：高并发读与后台写入互不阻塞
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")

            # 1. 替代内存 RUNS_DB：持久化 DAG 运行状态与断点数据
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    graph_json TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    paused_node_id TEXT,
                    paused_inputs_json TEXT,
                    updated_at INTEGER NOT NULL
                )
            """)

            # 2. 替代内存 NODE_CACHE：持久化 ComfyUI 式脏检查缓存
            conn.execute("""
                CREATE TABLE IF NOT EXISTS node_cache (
                    cache_key TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    output_payload_json TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)

            # 3. 章节快照与增量补丁表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chapter_commits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_index INTEGER NOT NULL,
                    is_full_snapshot BOOLEAN NOT NULL,
                    full_state_json TEXT,
                    diff_patches_json TEXT,
                    status TEXT DEFAULT 'ACTIVE',
                    created_at INTEGER NOT NULL
                )
            """)

    # ------------------------------------------
    # B. DAG 运行状态持久化
    # ------------------------------------------
    def save_run(self, run_state_dict: Dict[str, Any]):
        """保存或更新某次工作流运行快照（支持软件重启后从断点恢复）"""
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO workflow_runs
                    (run_id, status, graph_json, context_json, paused_node_id, paused_inputs_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status = excluded.status,
                    context_json = excluded.context_json,
                    paused_node_id = excluded.paused_node_id,
                    paused_inputs_json = excluded.paused_inputs_json,
                    updated_at = excluded.updated_at
                """,
                (
                    run_state_dict["run_id"],
                    run_state_dict["status"],
                    json.dumps(run_state_dict["graph"], ensure_ascii=False),
                    json.dumps(run_state_dict.get("context", {}), ensure_ascii=False),
                    run_state_dict.get("paused_node_id"),
                    json.dumps(run_state_dict.get("paused_inputs"), ensure_ascii=False)
                    if run_state_dict.get("paused_inputs") is not None
                    else None,
                    int(time.time()),
                ),
            )

    def load_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if not row:
                return None
            return {
                "run_id": row["run_id"],
                "status": row["status"],
                "graph": json.loads(row["graph_json"]),
                "context": json.loads(row["context_json"]),
                "paused_node_id": row["paused_node_id"],
                "paused_inputs": json.loads(row["paused_inputs_json"])
                if row["paused_inputs_json"]
                else None,
            }

    # ------------------------------------------
    # C. 脏检查缓存持久化
    # ------------------------------------------
    def get_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT output_payload_json FROM node_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
            return json.loads(row["output_payload_json"]) if row else None

    def set_cache(self, cache_key: str, node_type: str, output_payload: Dict[str, Any]):
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO node_cache (cache_key, node_type, output_payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    output_payload_json = excluded.output_payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    cache_key,
                    node_type,
                    json.dumps(output_payload, ensure_ascii=False),
                    int(time.time()),
                ),
            )

    def clear_old_cache(self, keep_latest: int = 500):
        """防止千万字写到后期缓存表无限膨胀，保留最近 N 条节点缓存"""
        with self._get_conn() as conn:
            conn.execute(
                """
                DELETE FROM node_cache
                WHERE cache_key NOT IN (
                    SELECT cache_key FROM node_cache ORDER BY updated_at DESC LIMIT ?
                )
                """,
                (keep_latest,),
            )

    # ------------------------------------------
    # D. 工作流模板与章节 Markdown 文件管理
    # ------------------------------------------
    def save_workflow(self, name: str, graph_dict: Dict[str, Any]):
        path = self.workflows_dir / f"{name}.json"
        path.write_text(
            json.dumps(graph_dict, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def load_workflow(self, name: str) -> Dict[str, Any]:
        path = self.workflows_dir / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"工作流模板未找到: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def save_chapter(self, volume: int, chapter_index: int, title: str, content: str) -> Path:
        """按卷分目录存放 Markdown 正文"""
        vol_dir = self.chapters_dir / f"vol_{volume:02d}"
        vol_dir.mkdir(parents=True, exist_ok=True)
        safe_title = "".join(c for c in title if c not in r'\/:*?"<>|').strip()
        file_path = vol_dir / f"ch_{chapter_index:04d}_{safe_title}.md"
        file_path.write_text(f"# 第{chapter_index}章 {title}\n\n{content}", encoding="utf-8")
        return file_path

    def export_full_txt(self, output_path: str) -> Path:
        """一键按卷/章顺序合并导出全书 TXT"""
        out = Path(output_path)
        md_files = sorted(self.chapters_dir.rglob("ch_*.md"))
        with out.open("w", encoding="utf-8") as f:
            for md in md_files:
                f.write(md.read_text(encoding="utf-8").strip())
                f.write("\n\n" + "=" * 30 + "\n\n")
        return out
