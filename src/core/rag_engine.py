"""RAG引擎 - 文档索引与检索"""

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.config import RAG_STATE_DIR, load_json, save_json, CHROMA_DIR, resolve_path, CONFIG_DIR
from src.core.embedding import get_embedding_function
from src.core.reranker import get_reranker


def _safe_collection_name(name: str) -> str:
    """将数据源名称转换为 ChromaDB 合法的集合名称（仅 [a-zA-Z0-9._-]）"""
    # 保留字母数字和 . _ -
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    # 确保以字母数字开头和结尾
    safe = safe.strip("_.-")
    if not safe or len(safe) < 3:
        safe = "src_" + hashlib.md5(name.encode()).hexdigest()[:12]
    # 如果首字符不是字母数字，加前缀
    if not safe[0].isalnum():
        safe = "src_" + safe
    # 如果尾字符不是字母数字
    if not safe[-1].isalnum():
        safe = safe + "0"
    return safe


def _deduplicate_chunks(chunks: list[str], threshold: float = 0.75) -> list[str]:
    """基于 Jaccard 相似度去除重复/高度相似的文本片段"""
    if len(chunks) <= 1:
        return chunks
    import re
    def _ngrams(text: str, n: int = 3) -> set[str]:
        clean = re.sub(r"\s+", " ", text)
        if len(clean) < n:
            return {clean}
        return {clean[i:i+n] for i in range(len(clean) - n + 1)}
    keep = []
    keep_ngrams: list[set[str]] = []
    for chunk in chunks:
        c_ngrams = _ngrams(chunk)
        is_dup = False
        for existing in keep_ngrams:
            if not c_ngrams or not existing:
                continue
            intersection = len(c_ngrams & existing)
            union = len(c_ngrams | existing)
            jaccard = intersection / union if union > 0 else 0
            if jaccard >= threshold:
                is_dup = True
                break
        if not is_dup:
            keep.append(chunk)
            keep_ngrams.append(c_ngrams)
    if len(keep) < len(chunks):
        print(f"[RAG] 去重: {len(chunks)} -> {len(keep)} 条 (移除 {len(chunks) - len(keep)} 条重复)")
    return keep


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """余弦相似度"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _distance_filter(docs, distances, threshold=1.2):
    """基于 ChromaDB cosine distance 过滤低相关片段"""
    if not docs or len(docs) != len(distances):
        return docs, distances
    filtered = [(d, dist) for d, dist in zip(docs, distances) if dist <= threshold]
    if not filtered:
        best_idx = min(range(len(distances)), key=lambda i: distances[i])
        return [docs[best_idx]], [distances[best_idx]]
    kept = len(filtered)
    dropped = len(docs) - kept
    if dropped > 0:
        print(f"[RAG] 距离过滤: {len(docs)} -> {kept} 条 (阈值 {threshold}, 移除 {dropped} 条)")
    return [d for d, _ in filtered], [dist for _, dist in filtered]


def _mmr_rerank(docs, doc_embeddings, query_embedding, lambda_param=0.7, top_n=5):
    """MMR 多样性重排"""
    if len(docs) <= top_n:
        return docs
    relevance_scores = [_cosine_sim(emb, query_embedding) for emb in doc_embeddings]
    selected: list[int] = []
    remaining = list(range(len(docs)))
    while len(selected) < top_n and remaining:
        mmr_scores = []
        for i in remaining:
            relevance = relevance_scores[i]
            if selected:
                max_sim = max(_cosine_sim(doc_embeddings[i], doc_embeddings[j]) for j in selected)
            else:
                max_sim = 0.0
            mmr = lambda_param * relevance - (1 - lambda_param) * max_sim
            mmr_scores.append((mmr, i))
        best_mmr, best_idx = max(mmr_scores, key=lambda x: x[0])
        selected.append(best_idx)
        remaining.remove(best_idx)
    return [docs[i] for i in selected]



def _extract_text(file_path: Path) -> str:
    """从文件中提取文本内容，支持 txt/md/py/json/csv/html/xml/docx/pdf"""
    suffix = file_path.suffix.lower()

    if suffix == ".docx":
        import docx
        doc = docx.Document(str(file_path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    if suffix == ".pdf":
        from PyPDF2 import PdfReader
        reader = PdfReader(str(file_path))
        return "\n".join(p.extract_text() or "" for p in reader.pages)

    # 其他文本格式直接 UTF-8 读取
    return file_path.read_text(encoding="utf-8", errors="ignore")


@dataclass
class RAGSource:
    """RAG数据源"""
    name: str
    path: str  # 本地目录或远程IP
    source_type: str  # local / remote
    enabled: bool = True
    file_count: int = 0
    indexed: bool = False


class RAGEngine:
    """RAG检索增强引擎"""

    CONFIG_PATH = RAG_STATE_DIR / "sources.json"

    def __init__(self):
        self.sources: list[RAGSource] = []
        self._client = None
        self._embedder = None

    # ── 路径可移植辅助方法 ──

    @staticmethod
    def _resolve_source_path(path: str) -> str:
        """加载时解析路径：相对→绝对；过时绝对路径自动自愈"""
        from pathlib import Path
        from src.utils.config import BASE_DIR
        p = Path(path)
        if p.is_absolute():
            if p.exists():
                return str(p)
            # 自愈：绝对路径不存在，尝试在当前 BASE_DIR 下查找同名路径
            healed = RAGEngine._heal_source_path(path, BASE_DIR)
            if healed is not None:
                return healed
            return str(p)
        # 相对路径 → 绝对
        return str(resolve_path(path))

    @staticmethod
    def _heal_source_path(abs_path: str, base_dir) -> str | None:
        """自愈过时的绝对路径：尝试在 base_dir 下查找同名文件/目录"""
        from pathlib import Path
        p = Path(abs_path)
        parts = p.parts
        for i in range(1, len(parts)):
            candidate = Path(base_dir, *parts[i:])
            if candidate.exists():
                return str(candidate)
        return None

    @staticmethod
    def _relativize_source_path(path: str) -> str:
        """保存时：将项目内绝对路径转回相对路径，保证跨机器可移植"""
        from pathlib import Path
        from src.utils.config import BASE_DIR
        p = Path(path)
        if p.is_absolute():
            try:
                rel = p.relative_to(BASE_DIR)
                return rel.as_posix()
            except ValueError:
                pass
        return path

    # ── Embedding 配置 ──

    def _get_rag_config(self) -> dict:
        """读取 RAG 配置"""
        return load_json(CONFIG_DIR / "rag_config.json")

    def _get_embed_fn(self):
        """根据配置获取 embedding 函数，失败返回 None 并打印警告"""
        try:
            config = self._get_rag_config()
            mode = config.get("embedding_mode", "auto")
            api_key = config.get("embedding_api_key", "")
            model = config.get("embedding_model", "BAAI/bge-m3")
            api_base = config.get("embedding_api_base", "https://api.siliconflow.cn/v1")
            return get_embedding_function(mode=mode, api_key=api_key, model=model, api_base=api_base)
        except ValueError as e:
            print(f"[RAG] Embedding 不可用: {e}")
            return None
        except Exception as e:
            print(f"[RAG] Embedding 初始化异常: {type(e).__name__}: {e}")
            return None

    def _get_reranker(self):
        """根据配置获取 reranker 实例，失败返回 None 并跳过精排"""
        try:
            config = self._get_rag_config()
            rerank_cfg = config.get("reranking", {})
            if not rerank_cfg.get("enabled", False):
                return None
            mode = rerank_cfg.get("mode", "none")
            api_key = config.get("embedding_api_key", "")
            model = rerank_cfg.get("model", "BAAI/bge-reranker-v2-m3")
            api_base = config.get("embedding_api_base", "https://api.siliconflow.cn/v1")
            return get_reranker(mode=mode, api_key=api_key, model=model, api_base=api_base)
        except Exception as e:
            print(f"[RAG] Reranker 初始化异常: {type(e).__name__}: {e}")
            return None


    # ── 配置持久化 ──

    def load_sources(self) -> list[RAGSource]:
        """加载数据源配置（自动自愈过时路径 + 解析相对路径）

        自愈后或 ChromaDB 集合缺失/为空时，将 indexed 重置为 False，
        确保下次 search 前触发重新索引。
        """
        from pathlib import Path
        config = load_json(self.CONFIG_PATH)
        sources = []
        for item in config.get("sources", config if isinstance(config, list) else []):
            raw_path = item.get("path", "")
            resolved = self._resolve_source_path(raw_path)

            # 自愈仅指：原本是过时绝对路径（如 E:\...），被修复为当前绝对路径
            raw_is_absolute = Path(raw_path).is_absolute()
            was_healed = raw_is_absolute and raw_path != resolved
            is_missing = not Path(resolved).exists()

            indexed = item.get("indexed", False)
            file_count = item.get("file_count", 0)

            if was_healed or is_missing:
                indexed = False
                file_count = 0
            elif indexed:
                # 路径正确但 ChromaDB 集合可能为空/不存在（换机器后残留）
                try:
                    import chromadb
                    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
                    embed_fn = self._get_embed_fn()
                    get_kwargs = {}
                    if embed_fn is not None:
                        get_kwargs["embedding_function"] = embed_fn
                    col = client.get_collection(
                        f"rag_{_safe_collection_name(item.get('name', ''))}",
                        **get_kwargs,
                    )
                    if col.count() == 0:
                        indexed = False
                        file_count = 0
                except ValueError as e:
                    if "Embedding function conflict" in str(e):
                        indexed = False
                        file_count = 0
                except Exception:
                    indexed = False
                    file_count = 0

            sources.append(RAGSource(
                name=item.get("name", ""),
                path=resolved,
                source_type=item.get("type", "local"),
                enabled=item.get("enabled", True),
                file_count=file_count,
                indexed=indexed,
            ))
        self.sources = sources
        return sources

    def save_sources(self) -> None:
        """保存数据源配置（项目内路径自动转回相对路径）"""
        data = {
            "sources": [
                {
                    "name": s.name,
                    "path": self._relativize_source_path(s.path),
                    "type": s.source_type,
                    "enabled": s.enabled,
                    "file_count": s.file_count,
                    "indexed": s.indexed,
                }
                for s in self.sources
            ]
        }
        save_json(self.CONFIG_PATH, data)

    def add_source(self, name: str, path: str, source_type: str = "local") -> RAGSource:
        """添加数据源（相对路径自动解析为绝对路径）"""
        resolved_path = str(resolve_path(path))
        source = RAGSource(name=name, path=resolved_path, source_type=source_type)
        self.sources.append(source)
        self.save_sources()
        return source

    def remove_source(self, name: str) -> None:
        """移除数据源"""
        self.sources = [s for s in self.sources if s.name != name]
        self.save_sources()

    def toggle_source(self, name: str, enabled: bool) -> None:
        """开关数据源"""
        for s in self.sources:
            if s.name == name:
                s.enabled = enabled
                break
        self.save_sources()

    async def index_source(self, source: RAGSource) -> int:
        """索引指定数据源的文档，返回索引文件数"""
        if source.source_type == "local":
            return await self._index_local(source)
        else:
            return await self._index_remote(source)

    async def _index_local(self, source: RAGSource) -> int:
        """索引本地目录"""
        import chromadb
        from src.core.semantic_chunker import SemanticChunker

        doc_dir = resolve_path(source.path)
        if not doc_dir.exists():
            print(f"[RAG] 目录不存在，无法索引: {doc_dir}")
            return 0

        config = self._get_rag_config()
        model_name = config.get("embedding_model", "BAAI/bge-m3")
        mode = config.get("embedding_mode", "auto")

        # 初始化ChromaDB（检测模型变更自动重建）
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        embed_fn = self._get_embed_fn()
        col_name = f"rag_{_safe_collection_name(source.name)}"
        want_meta = {"hnsw:space": "cosine", "rag_model": model_name, "rag_mode": mode}
        try:
            collection = client.get_collection(col_name, embedding_function=embed_fn)
            existing = collection.metadata or {}
            if existing.get("rag_model") != model_name or existing.get("rag_mode") != mode:
                print(f"[RAG] 模型变更 ({existing.get('rag_model')}->{model_name}), 自动重建: {col_name}")
                client.delete_collection(col_name)
                collection = client.create_collection(
                    name=col_name, metadata=want_meta, embedding_function=embed_fn,
                )
        except (ValueError, Exception):
            try:
                client.delete_collection(col_name)
            except Exception:
                pass
            collection = client.create_collection(
                name=col_name, metadata=want_meta, embedding_function=embed_fn,
            )

        # 初始化语义分片器：用户配置值被模型硬上限 clamp
        model_token_limit = SemanticChunker.MODEL_TOKEN_LIMITS.get(model_name)
        if model_token_limit is None:
            if mode == "local" or (mode == "auto" and not config.get("embedding_api_key")):
                model_token_limit = 256
            else:
                model_token_limit = 512
        if mode == "local":
            chunk_max_tokens = 200
        else:
            chunk_max_tokens = int(config.get("chunk_max_tokens", 800))
        effective_limit = min(chunk_max_tokens, model_token_limit)

        splitter = SemanticChunker(
            embed_fn=embed_fn,
            similarity_threshold=0.5,
            min_chunk_chars=200,
            max_chunk_chars=1500,
            overlap_chars=300,
            max_embedding_tokens=effective_limit,
        )

        supported_extensions = {".txt", ".md", ".py", ".json", ".csv", ".html", ".xml", ".docx", ".pdf"}

        count = 0
        for f in doc_dir.rglob("*"):
            if f.suffix.lower() not in supported_extensions:
                continue
            try:
                text = _extract_text(f)
                suffix = f.suffix.lower()
                if suffix == ".md":
                    doc_type = "markdown"
                elif suffix in (".py", ".json", ".html", ".xml", ".csv"):
                    doc_type = "code"
                else:
                    doc_type = "text"
                chunks = splitter.split(text, doc_type)
                if chunks:
                    ids = [f"{source.name}_{count}_{i}" for i in range(len(chunks))]
                    # 自己调 embedding，绕过 ChromaDB 内部序列化可能的模型名丢失
                    embeddings = embed_fn(chunks)
                    collection.upsert(
                        documents=chunks,
                        embeddings=embeddings,
                        ids=ids,
                        metadatas=[{"source": str(f), "rag_name": source.name}] * len(chunks)
                    )
                    count += 1
            except Exception as e:
                err_msg = str(e)
                if "dimension" in err_msg.lower() or "embedding" in err_msg.lower():
                    print(f"[RAG] 索引失败 {f}: embedding 不兼容，请清空旧数据后重新索引")
                elif "400" in err_msg or "20015" in err_msg:
                    print(f"[RAG] 索引失败 {f}: API 参数错误，请检查模型名称或 API Key")
                else:
                    print(f"[RAG] 索引文件失败 {f}: {type(e).__name__}: {e}")
                continue

        source.file_count = count
        source.indexed = True
        self.save_sources()
        return count

    async def _index_remote(self, source: RAGSource) -> int:
        """索引远程数据源（预留）"""
        # TODO: 支持远程文件访问
        return 0

    async def warmup(self) -> bool:
        """预热：提前下载 Embedding 模型 / 验证 API 连通性

        返回 True 表示 embedding 就绪，False 表示失败。
        """
        import asyncio

        try:
            embed_fn = self._get_embed_fn()
            if embed_fn is not None:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, embed_fn, ["warmup"])
                return len(result) > 0 and len(result[0]) > 0
            else:
                # 本地 ONNX 模式
                import chromadb
                client = chromadb.PersistentClient(path=str(CHROMA_DIR))
                collection = client.get_or_create_collection(
                    name="warmup_test",
                    metadata={"hnsw:space": "cosine"},
                )
                collection.upsert(documents=["warmup"], ids=["warmup_1"])
                client.delete_collection("warmup_test")
                return True
        except Exception as e:
            print(f"[RAG] warmup 失败: {type(e).__name__}: {e}")
            return False

    def search(self, query: str, top_k: int | None = None) -> list[str]:
        """检索相关文档片段

        流程: 向量粗排 -> 去重 -> 精排（API优先 / 本地降级）-> 阈值过滤
        """
        print(f"\n{'='*60}")
        print(f"[RAG] 查询: {query[:80]}")
        try:
            config = self._get_rag_config()
            if top_k is None:
                top_k = config.get("top_k", 20)
            rerank_cfg = config.get("reranking", {})
            rerank_enabled = rerank_cfg.get("enabled", False)
            coarse_k = top_k * 4 if rerank_enabled else top_k

            embed_fn = self._get_embed_fn()

            import chromadb
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))

            # 阶段1: 粗排
            print(f"[RAG] 阶段1 粗排: coarse_k={coarse_k}, rerank={'ON' if rerank_enabled else 'OFF'}")
            results: list[str] = []
            results_distances: list[float] = []
            results_embeddings: list[list[float]] = []
            for source in self.sources:
                if not source.enabled or not source.indexed:
                    continue
                try:
                    embed_fn = self._get_embed_fn()
                    collection = client.get_collection(
                        f"rag_{_safe_collection_name(source.name)}",
                        embedding_function=embed_fn,
                    )
                    result = collection.query(
                        query_texts=[query],
                        n_results=coarse_k,
                        include=["documents", "distances", "embeddings"],
                    )
                    if result.get("documents") and result["documents"]:
                        docs = result["documents"][0]
                        dists = result.get("distances", [[]])[0] if result.get("distances") else []
                        embs = result.get("embeddings", [[]])[0] if result.get("embeddings") else []

                        results.extend(docs)
                        results_distances.extend(dists if dists else [0.0] * len(docs))
                        results_embeddings.extend(embs if embs else [[0.0]] * len(docs))

                        print(f"  [{source.name}] 粗排 top-{len(docs)}:")
                        for j, (d, dist) in enumerate(zip(docs, dists)):
                            preview = d[:60].replace('\n', ' ')
                            print(f"    #{j+1} dist={dist:.3f} | {preview}...")
                    else:
                        print(f"  [{source.name}] 无结果 (总数={collection.count()})")
                except ValueError as e:
                    if "Embedding function conflict" in str(e) or "dimension" in str(e).lower():
                        print(f"  [{source.name}] 跳过: embedding 维度不兼容，需重新索引")
                    else:
                        print(f"  [{source.name}] 跳过: {e}")
                    continue
                except Exception as e:
                    print(f"  [{source.name}] 失败: {type(e).__name__}: {e}")

            if not results:
                print(f"[RAG] 无结果\n{'='*60}\n")
                return []

            print(f"[RAG] 粗排合计: {len(results)} 条")

            # 阶段2: 去重
            print(f"[RAG] 阶段2 去重")
            kept_docs = _deduplicate_chunks(results)
            if len(kept_docs) < len(results):
                used_indices: list[int] = []
                seen = set()
                for i, doc in enumerate(results):
                    key = doc[:100]
                    if key not in seen:
                        seen.add(key)
                        used_indices.append(i)
                if len(used_indices) > len(kept_docs):
                    used_indices = used_indices[:len(kept_docs)]
                results = kept_docs
                results_distances = [results_distances[i] for i in used_indices if i < len(results_distances)]
                results_embeddings = [results_embeddings[i] for i in used_indices if i < len(results_embeddings)]
            else:
                results = kept_docs
            print(f"  去重后: {len(results)} 条")
            for j, (d, dist) in enumerate(zip(results, results_distances)):
                preview = d[:60].replace('\n', ' ')
                print(f"    #{j+1} dist={dist:.3f} | {preview}...")

            # 阶段3: 精排
            print(f"[RAG] 阶段3 精排")
            if rerank_enabled and len(results) > top_k:
                reranker = self._get_reranker()
                if reranker is not None:
                    try:
                        scored = reranker.rerank(query, results, top_n=top_k)
                        threshold = rerank_cfg.get("relevance_threshold", 0.3)
                        print(f"  API 精排结果:")
                        for j, (doc, score) in enumerate(scored):
                            mark = "v" if score >= threshold else "x"
                            preview = doc[:60].replace('\n', ' ')
                            print(f"    #{j+1} score={score:.3f} {mark} | {preview}...")
                        filtered = [(doc, score) for doc, score in scored if score >= threshold]
                        if filtered:
                            results = [doc for doc, _ in filtered]
                            print(f"  阈值过滤({threshold}): {len(scored)} -> {len(results)} 条")
                        else:
                            results = [scored[0][0]] if scored else results[:1]
                            print(f"  全部低于阈值，取 top-1 兜底")
                    except Exception as e:
                        print(f"  API 精排失败: {type(e).__name__}: {e}")
                    finally:
                        try:
                            reranker.close()
                        except Exception:
                            pass
                else:
                    print(f"  本地降级: 距离过滤 + MMR")
                    if results_distances:
                        before = len(results)
                        results, results_distances = _distance_filter(
                            results, results_distances,
                            threshold=rerank_cfg.get("distance_threshold", 1.2),
                        )
                        if len(results) < before:
                            print(f"  距离过滤: {before} -> {len(results)} 条")
                    if results_embeddings and len(results) > top_k and embed_fn is not None:
                        try:
                            before = len(results)
                            query_emb = embed_fn([query])[0]
                            results = _mmr_rerank(
                                results, results_embeddings, query_emb,
                                lambda_param=rerank_cfg.get("mmr_lambda", 0.7),
                                top_n=top_k,
                            )
                            print(f"  MMR 重排: {before} -> {len(results)} 条")
                        except Exception as e:
                            print(f"  MMR 失败: {type(e).__name__}: {e}")
                            results = results[:top_k]
                    else:
                        results = results[:top_k]
                        print(f"  截断至 top-{top_k}")
            else:
                if len(results) > top_k:
                    results = results[:top_k]
                    print(f"  未启用精排，截断至 top-{top_k}")
                else:
                    print(f"  候选数 <= top_k，跳过精排")

            print(f"\n[RAG] 最终 Top-{len(results)}:")
            for j, doc in enumerate(results):
                preview = doc[:80].replace('\n', ' ')
                print(f"  #{j+1} {preview}...")
            print(f"{'='*60}\n")

            return results
        except Exception as e:
            print(f"[RAG] search 异常: {type(e).__name__}: {e}")
            print(f"{'='*60}\n")
            return []

    def get_chroma_stats(self) -> dict[str, int]:
        """获取各数据源的索引统计"""
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            stats = {}
            embed_fn = self._get_embed_fn()
            get_kwargs = {}
            if embed_fn is not None:
                get_kwargs["embedding_function"] = embed_fn
            for source in self.sources:
                try:
                    collection = client.get_collection(
                        f"rag_{_safe_collection_name(source.name)}",
                        **get_kwargs,
                    )
                    stats[source.name] = collection.count()
                except ValueError as e:
                    if "Embedding function conflict" in str(e):
                        stats[source.name] = 0
                    else:
                        stats[source.name] = 0
                except Exception:
                    stats[source.name] = 0
            return stats
        except Exception:
            return {}
