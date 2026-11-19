# patch_vectorstore_utils.py
with open('novel_generator/vectorstore_utils.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Replace langchain import
old_imp = "from langchain.embeddings.base import Embeddings as LCEmbeddings"
new_imp = """try:
        from langchain_core.embeddings import Embeddings as LCEmbeddings
    except ImportError:
        from langchain.embeddings.base import Embeddings as LCEmbeddings"""

count = code.count(old_imp)
print(f"Found {count} occurrences of old_imp")
code = code.replace(old_imp, new_imp)

# 2. Add DummyEmbeddingAdapter check in init_vector_store
init_target = """def init_vector_store(embedding_adapter, texts, filepath: str):
    \"\"\"
    在 filepath 下创建/初始化一个 Chroma 库并存入 texts。
    若Embedding失败，则返回 None。
    \"\"\""""

init_replacement = """def init_vector_store(embedding_adapter, texts, filepath: str):
    \"\"\"
    在 filepath 下创建/初始化一个 Chroma 库并存入 texts。
    若Embedding失败，则返回 None。
    \"\"\"
    if not embedding_adapter or getattr(embedding_adapter, '__class__', None) and embedding_adapter.__class__.__name__ == 'DummyEmbeddingAdapter':
        logging.info("本地免密/纯文学模式 (DummyEmbeddingAdapter)，跳过向量库构建。")
        return None"""

if init_target in code:
    code = code.replace(init_target, init_replacement, 1)
    print("Patched init_vector_store")
else:
    print("init_target not found")

# 3. Add DummyEmbeddingAdapter check in update_vector_store
update_target = """def update_vector_store(embedding_adapter, new_chapter: str, filepath: str):
    \"\"\"
    将新章节文本追加到向量库中。
    若库不存在则尝试初始化/若初始化失败则静默跳过。
    \"\"\""""

update_replacement = """def update_vector_store(embedding_adapter, new_chapter: str, filepath: str):
    \"\"\"
    将新章节文本追加到向量库中。
    若库不存在则尝试初始化/若初始化失败则静默跳过。
    \"\"\"
    if not embedding_adapter or getattr(embedding_adapter, '__class__', None) and embedding_adapter.__class__.__name__ == 'DummyEmbeddingAdapter':
        return"""

if update_target in code:
    code = code.replace(update_target, update_replacement, 1)
    print("Patched update_vector_store")
else:
    print("update_target not found")

# 4. Add DummyEmbeddingAdapter check in load_vector_store
load_target = """def load_vector_store(embedding_adapter, filepath: str):
    \"\"\"
    读取已存在的 Chroma 库。若库不存在则返回 None。
    若加载失败（如 embedding 适配器失效或IO问题）则返回 None。
    \"\"\""""

load_replacement = """def load_vector_store(embedding_adapter, filepath: str):
    \"\"\"
    读取已存在的 Chroma 库。若库不存在则返回 None。
    若加载失败（如 embedding 适配器失效或IO问题）则返回 None。
    \"\"\"
    if not embedding_adapter or getattr(embedding_adapter, '__class__', None) and embedding_adapter.__class__.__name__ == 'DummyEmbeddingAdapter':
        return None"""

if load_target in code:
    code = code.replace(load_target, load_replacement, 1)
    print("Patched load_vector_store")
else:
    print("load_target not found")

with open('novel_generator/vectorstore_utils.py', 'w', encoding='utf-8', newline='') as f:
    f.write(code)

print("Successfully updated novel_generator/vectorstore_utils.py")
