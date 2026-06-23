"""临时脚本：修复 rag_engine.py 的 search() 方法"""
import re

path = r"E:\AICraft\src\core\rag_engine.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. 在 search() 方法的 chromadb.PersistentClient 后加 embed_fn
old1 = """            client = chromadb.PersistentClient(path=str(CHROMA_DIR))

            # 在所有已启用的数据源中检索"""
new1 = """            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            embed_fn = self._get_embedding_function()

            # 在所有已启用的数据源中检索"""
content = content.replace(old1, new1)

# 2. 给 get_collection 加 embedding_function 参数
old2 = 'collection = client.get_collection(f"rag_{_safe_collection_name(source.name)}")'
new2 = 'collection = client.get_collection(f"rag_{_safe_collection_name(source.name)}", embedding_function=embed_fn)'
content = content.replace(old2, new2)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("OK - search() 已修复")
