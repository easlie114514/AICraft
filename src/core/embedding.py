"""Embedding 函数 — 支持 SiliconFlow API 和本地 ONNX 两种模式

本地模式使用项目内置的 all-MiniLM-L6-v2 ONNX 模型（models/onnx/），
无需联网下载，开箱即用。
"""

import json
from pathlib import Path
from typing import Any

import httpx
from chromadb.api.types import EmbeddingFunction

from src.utils.config import ONNX_MODEL_DIR

BUNDLED_MODEL_DIR = ONNX_MODEL_DIR

# ── 引导 ChromaDB 默认 ONNX 模型指向项目内置目录 ──
# ChromaDB 的 ONNXMiniLM_L6_V2 默认从 ~/.cache/chroma/onnx_models/ 下载模型。
# 这里把路径指向项目内置的 models/onnx/，用户无需联网即可使用本地 Embedding。
#
# 注：import onnx_mini_lm_l6_v2 会触发父包 __init__.py 导入全部 embedding function，
# 其中 sentence_transformer 仅在 __init__ 方法内懒加载 torch，运行时不会实际 import
# torch。PyInstaller 通过 excludes 跳过 torch 即可（see AICraft.spec）。
try:
    import chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 as _onnx_module
    _onnx_module.ONNXMiniLM_L6_V2.DOWNLOAD_PATH = BUNDLED_MODEL_DIR
except Exception:
    pass  # chromadb 未安装时静默跳过


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


def is_local_embedding_available() -> bool:
    """检测本地 Embedding 是否可用（模型文件 + onnxruntime 运行时）"""
    # 1. 检查模型文件是否内置
    model_dir = BUNDLED_MODEL_DIR / "onnx"
    required_files = [
        "config.json", "model.onnx", "special_tokens_map.json",
        "tokenizer.json", "tokenizer_config.json", "vocab.txt",
    ]
    for f in required_files:
        if not (model_dir / f).exists():
            return False

    # 2. 检查 onnxruntime 运行时
    try:
        import onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def get_embedding_function(mode: str = "auto", api_key: str = "") -> EmbeddingFunction | None:
    """获取 embedding 函数

    mode="api"   → 强制硅基流动 API（需 api_key）
    mode="local" → 本地 ONNX 模型（项目内置，无需联网；返回 None = ChromaDB 默认）
    mode="auto"  → 有 Key 用 API，否则本地
    """
    if mode == "api":
        if not api_key:
            raise ValueError("API 模式需要提供硅基流动 API Key")
        return SiliconFlowEmbeddingFunction(api_key=api_key)

    if mode == "local":
        return None  # ChromaDB 使用默认 ONNX，路径已在模块顶部指向内置模型

    # auto 模式
    if api_key:
        return SiliconFlowEmbeddingFunction(api_key=api_key)
    return None  # 本地 ONNX
