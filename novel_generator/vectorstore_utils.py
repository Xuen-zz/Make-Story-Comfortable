#novel_generator/vectorstore_utils.py
# -*- coding: utf-8 -*-
"""
向量库相关操作（初始化、更新、检索、清空、文本切分等）
"""
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
import logging
import traceback
# import nltk (lazy imported in chunk_text)
import numpy as np
import re
import ssl
import requests
import warnings
from langchain_chroma import Chroma
logging.basicConfig(
    filename='app.log',      # 日志文件名
    filemode='a',            # 追加模式（'w' 会覆盖）
    level=logging.INFO,      # 记录 INFO 及以上级别的日志
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
# 禁用特定的Torch警告
warnings.filterwarnings('ignore', message='.*Torch was not compiled with flash attention.*')
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # 禁用tokenizer并行警告
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from chromadb.config import Settings
from langchain_core.documents import Document
# from sklearn.metrics.pairwise import cosine_similarity
from .common import call_with_retry

def get_vectorstore_dir(filepath: str) -> str:
    """获取 vectorstore 路径"""
    return os.path.join(filepath, "vectorstore")

def clear_vector_store(filepath: str) -> bool:
    """清空 清空向量库"""
    import shutil
    store_dir = get_vectorstore_dir(filepath)
    if not os.path.exists(store_dir):
        logging.info("No vector store found to clear.")
        return False
    try:
        shutil.rmtree(store_dir)
        logging.info(f"Vector store directory '{store_dir}' removed.")
        return True
    except Exception as e:
        logging.error(f"无法删除向量库文件夹，请关闭程序后手动删除 {store_dir}。\n {str(e)}")
        traceback.print_exc()
        return False

def init_vector_store(embedding_adapter, texts, filepath: str):
    """
    在 filepath 下创建/加载一个 Chroma 向量库并插入 texts。
    如果Embedding失败，则返回 None，不中断任务。
    """
    if not embedding_adapter or (getattr(embedding_adapter, '__class__', None) and embedding_adapter.__class__.__name__ == 'DummyEmbeddingAdapter'):
        logging.info("本地免密/纯文学模式 (DummyEmbeddingAdapter)，跳过向量库构建。")
        return None
    try:
        from langchain_core.embeddings import Embeddings as LCEmbeddings
    except ImportError:
        from langchain.embeddings.base import Embeddings as LCEmbeddings

    store_dir = get_vectorstore_dir(filepath)
    os.makedirs(store_dir, exist_ok=True)
    documents = [Document(page_content=str(t)) for t in texts]

    try:
        class LCEmbeddingWrapper(LCEmbeddings):
            def embed_documents(self, texts):
                return call_with_retry(
                    func=embedding_adapter.embed_documents,
                    max_retries=3,
                    fallback_return=[],
                    texts=texts
                )
            def embed_query(self, query: str):
                res = call_with_retry(
                    func=embedding_adapter.embed_query,
                    max_retries=3,
                    fallback_return=[],
                    query=query
                )
                return res

        chroma_embedding = LCEmbeddingWrapper()
        vectorstore = Chroma.from_documents(
            documents,
            embedding=chroma_embedding,
            persist_directory=store_dir,
            client_settings=Settings(anonymized_telemetry=False),
            collection_name="novel_collection"
        )
        return vectorstore
    except Exception as e:
        logging.warning(f"Init vector store failed: {e}")
        traceback.print_exc()
        return None

def load_vector_store(embedding_adapter, filepath: str):
    """
    读取已存在的 Chroma 向量库。若不存在则返回 None。
    如果加载失败（embedding 或IO问题），则返回 None。
    """
    if not embedding_adapter or (getattr(embedding_adapter, '__class__', None) and embedding_adapter.__class__.__name__ == 'DummyEmbeddingAdapter'):
        return None
    try:
        from langchain_core.embeddings import Embeddings as LCEmbeddings
    except ImportError:
        from langchain.embeddings.base import Embeddings as LCEmbeddings
    store_dir = get_vectorstore_dir(filepath)
    if not os.path.exists(store_dir):
        logging.info("Vector store not found. Will return None.")
        return None

    try:
        class LCEmbeddingWrapper(LCEmbeddings):
            def embed_documents(self, texts):
                return call_with_retry(
                    func=embedding_adapter.embed_documents,
                    max_retries=3,
                    fallback_return=[],
                    texts=texts
                )
            def embed_query(self, query: str):
                res = call_with_retry(
                    func=embedding_adapter.embed_query,
                    max_retries=3,
                    fallback_return=[],
                    query=query
                )
                return res

        chroma_embedding = LCEmbeddingWrapper()
        return Chroma(
            persist_directory=store_dir,
            embedding_function=chroma_embedding,
            client_settings=Settings(anonymized_telemetry=False),
            collection_name="novel_collection"
        )
    except Exception as e:
        logging.warning(f"Failed to load vector store: {e}")
        traceback.print_exc()
        return None

def split_by_length(text: str, max_length: int = 500):
    """按照 max_length 切分文本"""
    segments = []
    start_idx = 0
    while start_idx < len(text):
        end_idx = min(start_idx + max_length, len(text))
        segment = text[start_idx:end_idx]
        segments.append(segment.strip())
        start_idx = end_idx
    return segments

def split_text_for_vectorstore(chapter_text: str, max_length: int = 500, similarity_threshold: float = 0.7):
    """
    对新的章节文本进行分段后,再用于存入向量库。
    使用 embedding 进行文本相似度计算。
    """
    if not chapter_text.strip():
        return []
    
    # nltk.download('punkt', quiet=True)
    # nltk.download('punkt_tab', quiet=True)
    try:
        import nltk
        sentences = nltk.sent_tokenize(chapter_text)
    except Exception:
        sentences = [s.strip() for s in re.split(r'(?<=[.!?。！？\n])\s*', chapter_text) if s.strip()]
    if not sentences:
        return []
    
    # 直接按长度分段,不做相似度合并
    final_segments = []
    current_segment = []
    current_length = 0
    
    for sentence in sentences:
        sentence_length = len(sentence)
        if current_length + sentence_length > max_length:
            if current_segment:
                final_segments.append(" ".join(current_segment))
            current_segment = [sentence]
            current_length = sentence_length
        else:
            current_segment.append(sentence)
            current_length += sentence_length
    
    if current_segment:
        final_segments.append(" ".join(current_segment))
    
    return final_segments

def update_vector_store(embedding_adapter, new_chapter: str, filepath: str):
    """
    将最新章节文本插入到向量库中。
    若库不存在则初始化；若初始化/更新失败，则跳过。
    """
    if not embedding_adapter or (getattr(embedding_adapter, '__class__', None) and embedding_adapter.__class__.__name__ == 'DummyEmbeddingAdapter'):
        return
    from utils import read_file, clear_file_content, save_string_to_txt
    splitted_texts = split_text_for_vectorstore(new_chapter)
    if not splitted_texts:
        logging.warning("No valid text to insert into vector store. Skipping.")
        return

    store = load_vector_store(embedding_adapter, filepath)
    if not store:
        logging.info("Vector store does not exist or failed to load. Initializing a new one for new chapter...")
        store = init_vector_store(embedding_adapter, splitted_texts, filepath)
        if not store:
            logging.warning("Init vector store failed, skip embedding.")
        else:
            logging.info("New vector store created successfully.")
        return

    try:
        docs = [Document(page_content=str(t)) for t in splitted_texts]
        store.add_documents(docs)
        logging.info("Vector store updated with the new chapter splitted segments.")
    except Exception as e:
        logging.warning(f"Failed to update vector store: {e}")
        traceback.print_exc()

def get_relevant_context_from_vector_store(
    embedding_adapter, query: str, filepath: str, k: int = 2,
    score_threshold: float = 0.35,
) -> str:
    """
    从向量库中检索与 query 最相关的 k 条文本，拼接后返回。
    如果向量库加载/检索失败，则返回空字符串。
    最终只返回最多2000字符的检索片段。

    score_threshold: 相关度下限 (0~1, 越高越严格)。
                     低于该阈值的结果将被丢弃，避免注入无关内容。
    """
    store = load_vector_store(embedding_adapter, filepath)
    if not store:
        logging.info("No vector store found or load failed. Returning empty context.")
        return ""

    try:
        # 使用带相关度评分的检索，过滤低质量结果
        docs_with_scores = store.similarity_search_with_relevance_scores(query, k=k)
        if not docs_with_scores:
            logging.info(f"No relevant documents found for query '{query}'. Returning empty context.")
            return ""

        filtered = [(doc, score) for doc, score in docs_with_scores if score >= score_threshold]
        if not filtered:
            logging.info(
                f"All {len(docs_with_scores)} results below threshold {score_threshold} "
                f"(best={docs_with_scores[0][1]:.3f}). Returning empty context."
            )
            return ""

        if len(filtered) < len(docs_with_scores):
            logging.info(
                f"Knowledge retrieval: kept {len(filtered)}/{len(docs_with_scores)} results "
                f"(threshold={score_threshold}, scores={[f'{s:.3f}' for _, s in docs_with_scores]})"
            )

        combined = "\n".join([doc.page_content for doc, _ in filtered])
        if len(combined) > 2000:
            combined = combined[:2000]
        return combined
    except Exception as e:
        logging.warning(f"Similarity search failed: {e}")
        traceback.print_exc()
        return ""

def import_knowledge_to_vectorstore(embedding_adapter, knowledge_text: str, filepath: str):
    """
    将知识库文本导入到向量库中。
    若库不存在则初始化；若初始化/更新失败，则跳过。
    """
    splitted_texts = split_text_for_vectorstore(knowledge_text)
    if not splitted_texts:
        logging.warning("No valid text to import into vector store. Skipping.")
        return

    store = load_vector_store(embedding_adapter, filepath)
    if not store:
        logging.info("Vector store does not exist or failed to load. Initializing a new one for knowledge import...")
        store = init_vector_store(embedding_adapter, splitted_texts, filepath)
        if not store:
            logging.warning("Init vector store failed, skip knowledge import.")
        else:
            logging.info("Knowledge imported successfully (new vector store created).")
        return

    try:
        docs = [Document(page_content=str(t)) for t in splitted_texts]
        store.add_documents(docs)
        logging.info("Knowledge imported successfully (appended to existing vector store).")
    except Exception as e:
        logging.warning(f"Failed to import knowledge: {e}")
        traceback.print_exc()

def get_author_vectorstore_dir(filepath: str = "", style_name: str = "", styles_dir: str = "") -> str:
    """获取作者参考库 vectorstore 路径。
    优先使用 style_name + styles_dir（文风绑定模式）；
    如果未指定 style_name，回退到 filepath（兼容旧逻辑）。
    """
    if style_name and styles_dir:
        return os.path.join(styles_dir, f"{style_name}_author_vectorstore")
    # 兼容旧的 project-bound 模式
    return os.path.join(filepath, "author_vectorstore")


def init_author_vector_store(embedding_adapter, texts: list, filepath: str = "",
                             style_name: str = "", styles_dir: str = ""):
    """
    创建/加载一个作者参考库 Chroma 向量库并插入 texts。
    使用独立的 collection name: author_reference_collection。
    """
    try:
        from langchain_core.embeddings import Embeddings as LCEmbeddings
    except ImportError:
        from langchain.embeddings.base import Embeddings as LCEmbeddings

    store_dir = get_author_vectorstore_dir(filepath=filepath, style_name=style_name, styles_dir=styles_dir)
    os.makedirs(store_dir, exist_ok=True)
    documents = [Document(page_content=str(t)) for t in texts]

    try:
        class LCEmbeddingWrapper(LCEmbeddings):
            def embed_documents(self, texts):
                return call_with_retry(
                    func=embedding_adapter.embed_documents,
                    max_retries=3,
                    fallback_return=[],
                    texts=texts
                )
            def embed_query(self, query: str):
                return call_with_retry(
                    func=embedding_adapter.embed_query,
                    max_retries=3,
                    fallback_return=[],
                    query=query
                )

        chroma_embedding = LCEmbeddingWrapper()
        vectorstore = Chroma.from_documents(
            documents,
            embedding=chroma_embedding,
            persist_directory=store_dir,
            client_settings=Settings(anonymized_telemetry=False),
            collection_name="author_reference_collection"
        )
        return vectorstore
    except Exception as e:
        logging.warning(f"Init author vector store failed: {e}")
        traceback.print_exc()
        return None


def load_author_vector_store(embedding_adapter, filepath: str = "",
                             style_name: str = "", styles_dir: str = ""):
    """
    读取已存在的作者参考库 Chroma 向量库。若不存在则返回 None。
    """
    try:
        from langchain_core.embeddings import Embeddings as LCEmbeddings
    except ImportError:
        from langchain.embeddings.base import Embeddings as LCEmbeddings

    store_dir = get_author_vectorstore_dir(filepath=filepath, style_name=style_name, styles_dir=styles_dir)
    if not os.path.exists(store_dir):
        logging.info("Author vector store not found. Will return None.")
        return None

    try:
        class LCEmbeddingWrapper(LCEmbeddings):
            def embed_documents(self, texts):
                return call_with_retry(
                    func=embedding_adapter.embed_documents,
                    max_retries=3,
                    fallback_return=[],
                    texts=texts
                )
            def embed_query(self, query: str):
                return call_with_retry(
                    func=embedding_adapter.embed_query,
                    max_retries=3,
                    fallback_return=[],
                    query=query
                )

        chroma_embedding = LCEmbeddingWrapper()
        return Chroma(
            persist_directory=store_dir,
            embedding_function=chroma_embedding,
            client_settings=Settings(anonymized_telemetry=False),
            collection_name="author_reference_collection"
        )
    except Exception as e:
        logging.warning(f"Failed to load author vector store: {e}")
        traceback.print_exc()
        return None


def get_author_reference_context(
    embedding_adapter, query: str, filepath: str = "", k: int = 3,
    score_threshold: float = 0.3,
    style_name: str = "", styles_dir: str = "",
    max_chars: int = 2000,
) -> str:
    """
    从作者参考库中检索文风参考片段，采用混合策略：
    - 语义检索：取与当前章节主题最相关的片段（对话/动作/描写等场景匹配）
    - 随机采样：从全库随机抽取片段，确保覆盖作者多种写作手法

    最终返回不超过 max_chars 字符的参考文本，以 \\n---\\n 分隔。
    """
    import random

    store = load_author_vector_store(embedding_adapter, filepath=filepath,
                                     style_name=style_name, styles_dir=styles_dir)
    if not store:
        logging.info("No author vector store found. Returning empty context.")
        return ""

    try:
        collection = store._collection
        total_count = collection.count()
        if total_count == 0:
            logging.info("Author vector store is empty.")
            return ""

        selected_texts = []
        used_ids = set()

        # ── 第一部分：语义检索（取与章节主题相关的片段）──
        semantic_k = min(max(k // 2, 1), total_count)  # 至少1条语义结果
        try:
            docs_with_scores = store.similarity_search_with_relevance_scores(query, k=semantic_k + 3)
            for doc, score in docs_with_scores:
                if score >= score_threshold and len(selected_texts) < semantic_k:
                    doc_id = hash(doc.page_content)
                    if doc_id not in used_ids:
                        selected_texts.append(doc.page_content)
                        used_ids.add(doc_id)
            logging.info(
                f"Author ref semantic: {len(selected_texts)}/{len(docs_with_scores)} hits "
                f"(threshold={score_threshold}, query='{query[:50]}...')"
            )
        except Exception as e:
            logging.warning(f"Author ref semantic search failed: {e}")

        # ── 第二部分：随机采样（覆盖不同写作风格片段）──
        random_k = k - len(selected_texts)  # 剩余名额给随机
        if random_k > 0 and total_count > len(selected_texts):
            try:
                all_docs = collection.get()
                all_contents = all_docs.get("documents", [])
                # 排除已选中的片段
                candidates = [t for t in all_contents if hash(t) not in used_ids]
                if candidates:
                    sample_n = min(random_k, len(candidates))
                    random_picks = random.sample(candidates, sample_n)
                    selected_texts.extend(random_picks)
                    logging.info(f"Author ref random: sampled {sample_n} from {len(candidates)} candidates")
            except Exception as e:
                logging.warning(f"Author ref random sampling failed: {e}")

        if not selected_texts:
            logging.info("Author ref: no texts selected after both strategies.")
            return ""

        combined = "\n---\n".join(selected_texts)
        if len(combined) > max_chars:
            # 按片段截断而非硬切字符串，避免截断到半句话
            result_parts = []
            current_len = 0
            for text in selected_texts:
                if current_len + len(text) + 5 > max_chars:  # 5 for "\n---\n"
                    break
                result_parts.append(text)
                current_len += len(text) + 5
            combined = "\n---\n".join(result_parts) if result_parts else selected_texts[0][:max_chars]

        logging.info(f"Author ref final: {len(selected_texts)} fragments, {len(combined)} chars")
        return combined
    except Exception as e:
        logging.warning(f"Author reference search failed: {e}")
        traceback.print_exc()
        return ""


def clear_author_vector_store(filepath: str = "", style_name: str = "", styles_dir: str = "") -> None:
    """清空作者参考库向量库"""
    import shutil
    store_dir = get_author_vectorstore_dir(filepath=filepath, style_name=style_name, styles_dir=styles_dir)
    if not os.path.exists(store_dir):
        logging.info("No author vector store found to clear.")
        return
    try:
        shutil.rmtree(store_dir)
        logging.info(f"Author vector store directory '{store_dir}' removed.")
    except Exception as e:
        logging.error(f"无法删除作者参考库文件夹 {store_dir}。\n {str(e)}")
        traceback.print_exc()


def _get_sentence_transformer(model_name: str = 'paraphrase-MiniLM-L6-v2'):
    """获取sentence transformer模型，处理SSL问题"""
    try:
        # 设置torch环境变量
        os.environ["TORCH_ALLOW_TF32_CUBLAS_OVERRIDE"] = "0"
        os.environ["TORCH_CUDNN_V8_API_ENABLED"] = "0"
        
        # 禁用SSL验证
        ssl._create_default_https_context = ssl._create_unverified_context
        
        # ...existing code...
    except Exception as e:
        logging.error(f"Failed to load sentence transformer model: {e}")
        traceback.print_exc()
        return None


# ═════════════════════════════════════════════════════════════════════════════
# 设定条目化向量资产库 (Entity-Based Vector Asset Store)
# 核心技巧：
# 1. 严格按实体/条目切片（一个地点/一个功法/一个角色一个独立 Chunk），杜绝按字数机械切碎
# 2. 善用 Metadata 过滤：入库打标 status=active，设定过时废弃时设为 deprecated，检索时直接过滤
# ═════════════════════════════════════════════════════════════════════════════

def _get_entity_catalog_path(filepath: str) -> str:
    return os.path.join(filepath, "entity_catalog.json")


def load_entity_catalog(filepath: str) -> list[dict]:
    """读取当前书籍的设定实体条目清单。"""
    path = _get_entity_catalog_path(filepath)
    if not os.path.exists(path):
        return []
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"读取 entity_catalog.json 失败: {e}")
        return []


def save_entity_catalog(filepath: str, entities: list[dict]) -> None:
    """持久化保存设定实体条目清单。"""
    path = _get_entity_catalog_path(filepath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entities, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"保存 entity_catalog.json 失败: {e}")


def add_or_update_entity_item(embedding_adapter, filepath: str, item: dict) -> dict:
    """
    按设定条目添加或更新一个实体 Chunk 到向量库与实体清单中。
    item 格式:
    {
      "id": "loc_blackstone_city",
      "type": "location" | "faction" | "cultivation" | "character" | "lore" | "plot_recap",
      "name": "黑石城",
      "content": "完整的地点定义描述...",
      "tags": ["大秦帝国", "边陲", "禁空法阵"],
      "status": "active" | "deprecated",
      "valid_from_chapter": 1,
      "deprecated_at_chapter": null
    }
    """
    eid = str(item.get("id") or f"ent_{int(__import__('time').time()*1000)}")
    ename = str(item.get("name") or "未命名设定").strip()
    etype = str(item.get("type") or "lore").strip()
    econtent = str(item.get("content") or "").strip()
    etags = item.get("tags") or []
    status = str(item.get("status") or "active").strip()
    valid_from = int(item.get("valid_from_chapter") or 1)
    dep_at = item.get("deprecated_at_chapter")

    record = {
        "id": eid,
        "type": etype,
        "name": ename,
        "content": econtent,
        "tags": etags,
        "status": status,
        "valid_from_chapter": valid_from,
        "deprecated_at_chapter": dep_at,
        "updated_at": __import__('time').time(),
    }

    # 1. 更新 JSON 清单
    catalog = load_entity_catalog(filepath)
    new_cat = [c for c in catalog if str(c.get("id")) != eid]
    new_cat.append(record)
    save_entity_catalog(filepath, new_cat)

    # 2. 如果提供了 embedding_adapter 且存在有效内容，插入/更新 Chroma 向量库
    if embedding_adapter and econtent:
        store = load_vector_store(embedding_adapter, filepath)
        page_text = f"【{etype.upper()}: {ename}】\n{econtent}"
        metadata = {
            "entity_id": eid,
            "entity_type": etype,
            "name": ename,
            "status": status,
            "valid_from_chapter": valid_from,
            "deprecated_at_chapter": dep_at or -1,
        }
        doc = Document(page_content=page_text, metadata=metadata)
        try:
            if not store:
                init_vector_store(embedding_adapter, [page_text], filepath)
            else:
                store.add_documents([doc])
            logging.info(f"实体条目已入向量库: [{etype}] {ename} (status={status})")
        except Exception as e:
            logging.warning(f"实体条目入库失败: {e}")

    return record


def deprecate_entity_item(embedding_adapter, filepath: str, entity_id: str, chapter_num: int) -> bool:
    """
    将旧设定标记为废弃 (deprecated)，检索时自动过滤，防止新旧设定打架吃书。
    """
    catalog = load_entity_catalog(filepath)
    found = False
    for item in catalog:
        if str(item.get("id")) == str(entity_id):
            item["status"] = "deprecated"
            item["deprecated_at_chapter"] = int(chapter_num)
            found = True
            break
    if found:
        save_entity_catalog(filepath, catalog)
        # 同步更新向量库记录状态（若支持直接修改元数据）
        logging.info(f"设定条目 {entity_id} 已在第 {chapter_num} 章被标记为废弃")
    return found


def query_active_entities(
    embedding_adapter,
    filepath: str,
    query: str,
    current_chapter: int = 1,
    top_k: int = 4,
    entity_types: list[str] | None = None,
) -> list[dict]:
    """
    根据当前章节大纲/上下文，语义检索活跃设定条目。
    - 严格过滤 status == 'active'
    - 严格过滤 valid_from_chapter <= current_chapter
    - 严格过滤已废弃条目 (deprecated_at_chapter <= current_chapter)
    """
    catalog = load_entity_catalog(filepath)
    # 本地有效候选集（保证任何情况都有保底检索）
    active_candidates = [
        c for c in catalog
        if c.get("status", "active") == "active"
        and int(c.get("valid_from_chapter", 1)) <= current_chapter
        and (not c.get("deprecated_at_chapter") or int(c.get("deprecated_at_chapter")) > current_chapter)
        and (not entity_types or c.get("type") in entity_types)
    ]

    if not active_candidates:
        return []

    # 1. 尝试使用 Chroma 向量库检索
    store = load_vector_store(embedding_adapter, filepath)
    if store and query.strip():
        try:
            # 带 metadata status 过滤
            res_with_scores = store.similarity_search_with_relevance_scores(
                query, k=top_k * 2, filter={"status": "active"}
            )
            matched_items: list[dict] = []
            seen_ids = set()
            for doc, score in res_with_scores:
                eid = doc.metadata.get("entity_id")
                vf = int(doc.metadata.get("valid_from_chapter") or 1)
                dep = int(doc.metadata.get("deprecated_at_chapter") or -1)
                if dep > 0 and dep <= current_chapter:
                    continue
                if vf > current_chapter:
                    continue
                # 从 catalog 中匹配完整条目
                cat_item = next((c for c in active_candidates if c.get("id") == eid), None)
                if cat_item and eid not in seen_ids:
                    seen_ids.add(eid)
                    item_copy = dict(cat_item)
                    item_copy["relevance_score"] = float(score)
                    matched_items.append(item_copy)
                    if len(matched_items) >= top_k:
                        break
            if matched_items:
                return matched_items
        except Exception as e:
            logging.warning(f"向量库语义召回异常，使用本地条目匹配: {e}")

    # 2. 保底：关键词/实体名匹配
    q_lower = query.lower()
    scored = []
    for c in active_candidates:
        score = 0
        name = str(c.get("name", "")).lower()
        if name and name in q_lower:
            score += 10
        for tag in c.get("tags") or []:
            if str(tag).lower() in q_lower:
                score += 3
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    if scored:
        return [x[1] for x in scored[:top_k]]

    # 默认返回最新入库的前几个重要活跃设定
    return active_candidates[:top_k]


def format_entities_for_prompt(entities: list[dict]) -> str:
    """格式化召回的活跃实体为 Prompt 注入块。"""
    if not entities:
        return ""
    lines = ["=== 📚 召回关联设定与世界观条目（当前活跃生效，禁止吃书） ==="]
    for ent in entities:
        t_label = ent.get("type", "lore").upper()
        name = ent.get("name", "未命名")
        content = ent.get("content", "").strip()
        lines.append(f"【{t_label}: {name}】\n{content}")
    lines.append("==========================================================")
    return "\n\n".join(lines)

