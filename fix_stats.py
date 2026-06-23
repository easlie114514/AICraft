"""修复 rag_engine.py 的 get_chroma_stats() 方法 — 移除多余的 embed_fn"""

path = r"E:\AICraft\src\core\rag_engine.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. get_chroma_stats 里的 get_collection 不需要 embedding_function（只做 count）
old = 'collection = client.get_collection(f"rag_{_safe_collection_name(source.name)}", embedding_function=embed_fn)\n                    stats[source.name] = collection.count()'
new = 'collection = client.get_collection(f"rag_{_safe_collection_name(source.name)}")\n                    stats[source.name] = collection.count()'
content = content.replace(old, new)

# 2. 给 _get_embedding_function 加更好的错误日志
old_import = 'from src.core.embedding import DeepSeekEmbeddingFunction, OpenAIEmbeddingFunction'
new_import = '''from src.core.embedding import DeepSeekEmbeddingFunction, OpenAIEmbeddingFunction
            import traceback'''
content = content.replace(old_import, new_import)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("OK - get_chroma_stats 已修复")
