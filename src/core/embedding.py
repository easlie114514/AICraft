"""Embedding 函数 — 支持 SiliconFlow API 和本地 onnx 两种模式"""

import json
from typing import Any

import httpx
from chromadb.api.types import EmbeddingFunction


class SiliconFlowEmbeddingFunction(EmbeddingFunction):
    """通过硅基流动 API 生成向量

    支持的模型:
    - BAAI/bge-large-zh-v1.5  (中文, 1024维, 免费)
    - BAAI/bge-large-en-v1.5  (英文, 1024维, 免费)
    - BAAI/bge-m3              (多语言, 1024维, 免费)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "BAAI/bge-large-zh-v1.5",
        api_base: str = "https://api.siliconflow.cn/v1",
    ):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base.rstrip("/")
        self._client = httpx.Client(timeout=60.0)

    def __del__(self):
        """析构时关闭 HTTP 客户端，释放连接池"""
        try:
            self._client.close()
        except Exception:
            pass

    def close(self):
        """显式关闭 HTTP 客户端"""
        self._client.close()

    def __call__(self, input: list[str]) -> list[list[float]]:
        batch_size = 64
        all_embeddings: list[list[float]] = []
        for i in range(0, len(input), batch_size):
            batch = input[i : i + batch_size]
            try:
                # 手动序列化 JSON 确保中文等非 ASCII 字符正确编码为 UTF-8
                body = json.dumps(
                    {"model": self.model, "input": batch},
                    ensure_ascii=False,
                ).encode("utf-8")
                resp = self._client.post(
                    f"{self.api_base}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json; charset=utf-8",
                    },
                    content=body,
                )
                resp.raise_for_status()
                data = resp.json()["data"]
                data.sort(key=lambda x: x["index"])
                all_embeddings.extend([d["embedding"] for d in data])
            except httpx.HTTPStatusError as e:
                print(f"[Embedding] API 错误: {e.response.status_code} {e.response.text[:200]}")
                raise
            except Exception as e:
                print(f"[Embedding] 请求异常: {type(e).__name__}: {e}")
                raise
        return all_embeddings

    @staticmethod
    def name() -> str:
        return "siliconflow"

    def default_space(self) -> str:
        return "cosine"

    def get_config(self) -> dict[str, Any]:
        return {
            "api_key": self.api_key,
            "model": self.model,
            "api_base": self.api_base,
        }

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "SiliconFlowEmbeddingFunction":
        return SiliconFlowEmbeddingFunction(
            api_key=config.get("api_key", ""),
            model=config.get("model", "BAAI/bge-large-zh-v1.5"),
            api_base=config.get("api_base", "https://api.siliconflow.cn/v1"),
        )


def get_embedding_function(mode: str = "auto", api_key: str = "") -> EmbeddingFunction | None:
    """获取 embedding 函数

    mode="api"   → 强制硅基流动API（需api_key）
    mode="local" → 本地onnx（返回None，ChromaDB用默认）
    mode="auto"  → 有key用API，否则本地
    """
    if mode == "api":
        if not api_key:
            raise ValueError("API 模式需要提供硅基流动 API Key")
        return SiliconFlowEmbeddingFunction(api_key=api_key)
    if mode == "local":
        return None
    # auto
    if api_key:
        return SiliconFlowEmbeddingFunction(api_key=api_key)
    return None
