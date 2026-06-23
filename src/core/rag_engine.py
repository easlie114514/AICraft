"""RAG引擎 - 文档索引与检索"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.config import RAG_STATE_DIR, load_json, save_json, CHROMA_DIR, resolve_path, CONFIG_DIR
from src.core.embedding import get_embedding_function


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
            return get_embedding_function(mode=mode, api_key=api_key)
        except ValueError as e:
            print(f"[RAG] Embedding 不可用: {e}")
            return None
        except Exception as e:
            print(f"[RAG] Embedding 初始化异常: {type(e).__name__}: {e}")
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
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        doc_dir = resolve_path(source.path)
        if not doc_dir.exists():
            print(f"[RAG] 目录不存在，无法索引: {doc_dir}")
            return 0

        # 初始化ChromaDB
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        embed_fn = self._get_embed_fn()
        col_name = f"rag_{_safe_collection_name(source.name)}"
        try:
            collection = client.get_or_create_collection(
                name=col_name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=embed_fn,
            )
        except ValueError as e:
            # embedding 函数不兼容（如从 local 切换到 api），删除旧集合重建
            if "Embedding function conflict" in str(e):
                print(f"[RAG] Embedding 函数变更，删除旧集合并重建: {col_name}")
                client.delete_collection(col_name)
                collection = client.get_or_create_collection(
                    name=col_name,
                    metadata={"hnsw:space": "cosine"},
                    embedding_function=embed_fn,
                )
            else:
                raise

        # 初始化切分器
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
        )

        # 支持的文件类型
        supported_extensions = {".txt", ".md", ".py", ".json", ".csv", ".html", ".xml", ".docx", ".pdf"}

        count = 0
        for f in doc_dir.rglob("*"):
            if f.suffix.lower() not in supported_extensions:
                continue
            try:
                text = _extract_text(f)
                chunks = splitter.split_text(text)
                if chunks:
                    ids = [f"{source.name}_{count}_{i}" for i in range(len(chunks))]
                    collection.upsert(
                        documents=chunks,
                        ids=ids,
                        metadatas=[{"source": str(f), "rag_name": source.name}] * len(chunks)
                    )
                    count += 1
            except Exception as e:
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

    def search(self, query: str, top_k: int = 5) -> list[str]:
        """检索相关文档片段"""
        try:
            embed_fn = self._get_embed_fn()
            # embed_fn 为 None 表示使用 ChromaDB 默认 ONNX（本地模式），合法

            import chromadb
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))

            # 在所有已启用的数据源中检索
            results = []
            for source in self.sources:
                if not source.enabled or not source.indexed:
                    continue
                try:
                    embed_fn = self._get_embed_fn()
                    collection = client.get_collection(
                        f"rag_{_safe_collection_name(source.name)}",
                        embedding_function=embed_fn,
                    )
                    print(f"[RAG] 检索 '{source.name}': collection 存在, 文档数={collection.count()}")
                    result = collection.query(
                        query_texts=[query],
                        n_results=top_k,
                    )
                    if result.get("documents") and result["documents"]:
                        docs = result["documents"][0]
                        results.extend(docs)
                        print(f"[RAG] 检索 '{source.name}': 命中 {len(docs)} 条")
                    else:
                        print(f"[RAG] 检索 '{source.name}': 无结果 (collection 有 {collection.count()} 条文档)")
                except ValueError as e:
                    if "Embedding function conflict" in str(e):
                        print(f"[RAG] 检索 '{source.name}': embedding 函数不兼容，跳过 (需重新索引)")
                        continue
                    raise
                except Exception as e:
                    print(f"[RAG] 检索 '{source.name}' 失败: {type(e).__name__}: {e}")

            return results[:top_k]
        except Exception as e:
            print(f"[RAG] search 异常: {type(e).__name__}: {e}")
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
