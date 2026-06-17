"""RAG引擎 - 文档索引与检索"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.config import RAG_DIR, load_json, save_json, CHROMA_DIR


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

    CONFIG_PATH = RAG_DIR / "sources.json"

    def __init__(self):
        self.sources: list[RAGSource] = []
        self._client = None
        self._embedder = None

    def load_sources(self) -> list[RAGSource]:
        """加载数据源配置"""
        config = load_json(self.CONFIG_PATH)
        sources = []
        for item in config.get("sources", []):
            sources.append(RAGSource(
                name=item.get("name", ""),
                path=item.get("path", ""),
                source_type=item.get("type", "local"),
                enabled=item.get("enabled", True),
                file_count=item.get("file_count", 0),
                indexed=item.get("indexed", False),
            ))
        self.sources = sources
        return sources

    def save_sources(self) -> None:
        """保存数据源配置"""
        data = {
            "sources": [
                {
                    "name": s.name,
                    "path": s.path,
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
        """添加数据源"""
        source = RAGSource(name=name, path=path, source_type=source_type)
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

        doc_dir = Path(source.path)
        if not doc_dir.exists():
            return 0

        # 初始化ChromaDB
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        collection = client.get_or_create_collection(
            name=f"rag_{_safe_collection_name(source.name)}",
            metadata={"hnsw:space": "cosine"}
        )

        # 初始化切分器
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
        )

        # 支持的文件类型
        supported_extensions = {".txt", ".md", ".py", ".json", ".csv", ".html", ".xml"}

        count = 0
        for f in doc_dir.rglob("*"):
            if f.suffix.lower() in supported_extensions:
                try:
                    text = f.read_text(encoding="utf-8")
                    chunks = splitter.split_text(text)
                    if chunks:
                        ids = [f"{source.name}_{count}_{i}" for i in range(len(chunks))]
                        collection.upsert(
                            documents=chunks,
                            ids=ids,
                            metadatas=[{"source": str(f), "rag_name": source.name}] * len(chunks)
                        )
                        count += 1
                except Exception:
                    continue

        source.file_count = count
        source.indexed = True
        self.save_sources()
        return count

    async def _index_remote(self, source: RAGSource) -> int:
        """索引远程数据源（预留）"""
        # TODO: 支持远程文件访问
        return 0

    def search(self, query: str, top_k: int = 5) -> list[str]:
        """检索相关文档片段"""
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))

            # 在所有已启用的数据源中检索
            results = []
            for source in self.sources:
                if not source.enabled or not source.indexed:
                    continue
                try:
                    collection = client.get_collection(f"rag_{_safe_collection_name(source.name)}")
                    result = collection.query(
                        query_texts=[query],
                        n_results=top_k,
                    )
                    if result["documents"]:
                        results.extend(result["documents"][0])
                except Exception:
                    continue

            return results[:top_k]
        except Exception:
            return []

    def get_chroma_stats(self) -> dict[str, int]:
        """获取各数据源的索引统计"""
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            stats = {}
            for source in self.sources:
                try:
                    collection = client.get_collection(f"rag_{_safe_collection_name(source.name)}")
                    stats[source.name] = collection.count()
                except Exception:
                    stats[source.name] = 0
            return stats
        except Exception:
            return {}
