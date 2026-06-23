"""AICraft RAG 全链路诊断脚本 — 跑完就知道哪里断了"""
import sys
import os
import json
import traceback

sys.path.insert(0, r"E:\AICraft")
os.chdir(r"E:\AICraft")

print("=" * 60)
print("AICraft RAG 诊断")
print("=" * 60)

# ─── Step 1: 能不能 import embedding.py ───
print("\n[1] 测试 embedding.py 导入...")
try:
    from src.core.embedding import DeepSeekEmbeddingFunction, OpenAIEmbeddingFunction
    print("    OK - 导入成功")
except Exception as e:
    print(f"    FAIL - 导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# ─── Step 2: 能不能拿到 API Key ───
print("\n[2] 测试获取 API Key...")
api_key = ""
model_dir = r"E:\AICraft\models"
for f in os.listdir(model_dir):
    if f.endswith(".json"):
        with open(os.path.join(model_dir, f), "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
            if cfg.get("api_key"):
                api_key = cfg["api_key"]
                print(f"    OK - 找到 Key (来自 {f}): {api_key[:8]}...")
                print(f"    base_url: {cfg.get('base_url', 'N/A')}")
                break

if not api_key:
    print("    FAIL - 没找到 API Key!")
    sys.exit(1)

# ─── Step 3: DeepSeek Embedding API 能不能用 ───
print("\n[3] 测试 DeepSeek Embedding API...")
import httpx

client = httpx.Client(timeout=30.0)

for endpoint in [
    "https://api.deepseek.com/v1/embeddings",
    "https://api.deepseek.com/embeddings",
]:
    try:
        resp = client.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "deepseek-embedding", "input": ["AICraft测试文本"]},
        )
        print(f"    {endpoint}")
        print(f"    状态码: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            dim = len(data["data"][0]["embedding"])
            print(f"    OK - 成功! 向量维度: {dim}")
            break
        else:
            print(f"    FAIL - 失败: {resp.text[:200]}")
    except Exception as e:
        print(f"    FAIL - 异常: {e}")

# ─── Step 4: 测试 embedding.py 的 EmbeddingFunction ───
print("\n[4] 测试 DeepSeekEmbeddingFunction...")
try:
    embed_fn = DeepSeekEmbeddingFunction(api_key=api_key)
    result = embed_fn(["AICraft测试文本"])
    print(f"    OK - 成功! 返回 {len(result)} 条向量, 维度: {len(result[0])}")
except Exception as e:
    print(f"    FAIL - 失败: {e}")
    traceback.print_exc()

# ─── Step 5: 测试 rag_engine 的 _get_embedding_function ───
print("\n[5] 测试 rag_engine._get_embedding_function()...")
try:
    from src.core.rag_engine import RAGEngine
    from src.utils.config import RAG_DIR, CHROMA_DIR
    
    engine = RAGEngine.__new__(RAGEngine)
    engine.rag_dir = RAG_DIR
    engine.chroma_dir = CHROMA_DIR
    
    fn = engine._get_embedding_function()
    if fn is None:
        print("    FAIL - 返回 None! 这是 RAG 不工作的直接原因")
        print("    -> _get_embedding_function() 内部获取 API Key 失败")
    else:
        print(f"    OK - 返回: {type(fn).__name__}")
        test_result = fn(["测试"])
        print(f"    OK - 向量维度: {len(test_result[0])}")
except Exception as e:
    print(f"    FAIL - 异常: {e}")
    traceback.print_exc()

# ─── Step 6: 检查 ChromaDB 数据 ───
print("\n[6] 检查 ChromaDB 现有数据...")
import chromadb
try:
    cclient = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collections = cclient.list_collections()
    print(f"    集合数量: {len(collections)}")
    for col in collections:
        count = col.count()
        print(f"    - {col.name}: {count} 条记录")
        if count > 0:
            peek = col.peek(1)
            if peek and peek.get("embeddings") and len(peek["embeddings"]) > 0:
                dim = len(peek["embeddings"][0])
                print(f"      向量维度: {dim}")
except Exception as e:
    print(f"    FAIL - 异常: {e}")
    traceback.print_exc()

# ─── Step 7: 测试完整 search 流程 ───
print("\n[7] 测试 RAGEngine.search()...")
try:
    from src.core.rag_engine import RAGEngine
    from src.utils.config import RAG_DIR, CHROMA_DIR
    
    engine = RAGEngine.__new__(RAGEngine)
    engine.rag_dir = RAG_DIR
    engine.chroma_dir = CHROMA_DIR
    engine.sources = []
    
    from src.utils.config import CONFIG_DIR
    rag_config = CONFIG_DIR / "rag_sources.json"
    if rag_config.exists():
        with open(rag_config, "r", encoding="utf-8") as f:
            sources_data = json.load(f)
            print(f"    rag_sources.json: {len(sources_data)} 个数据源")
    
    results = engine.search("AICraft怎么用", top_k=3)
    print(f"    搜索结果: {len(results)} 条")
    for r in results:
        print(f"    - [{r.get('source','?')}] {r.get('content','')[:80]}...")
except Exception as e:
    print(f"    FAIL - 异常: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
