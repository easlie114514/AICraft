"""Reranker — Cross-Encoder 精排模块

在向量粗排之后，用更强的 Cross-Encoder 模型对候选片段逐对打分重排，
显著提升检索精度。

支持两种模式：
- api: 硅基流动 Rerank API（BAAI/bge-reranker-v2-m3）
- local: 本地 ONNX 模型（Phase 2 实现）
- none: 跳过精排
"""

import json
from typing import Any

import httpx


class SiliconFlowReranker:
    """通过硅基流动 Rerank API 进行精排

    支持的模型:
    - BAAI/bge-reranker-v2-m3  (多语言, 推荐)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "BAAI/bge-reranker-v2-m3",
        api_base: str = "https://api.siliconflow.cn/v1",
    ):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base.rstrip("/")
        self._client = httpx.Client(timeout=30.0)

    def __del__(self):
        try:
            self._client.close()
        except Exception:
            pass

    def close(self):
        self._client.close()

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int = 5,
    ) -> list[tuple[str, float]]:
        """对文档列表进行精排

        Args:
            query: 用户查询
            documents: 候选文档列表（粗排结果）
            top_n: 返回最相关的 top_n 条

        Returns:
            [(文档文本, 相关度分数), ...]  按分数降序排列
        """
        if not documents:
            return []

        # 限制单次请求的文档数（API 限制通常为 32-64 条）
        max_docs = min(len(documents), 32)
        docs_to_rank = documents[:max_docs]

        try:
            body = json.dumps(
                {
                    "model": self.model,
                    "query": query,
                    "documents": docs_to_rank,
                    "top_n": min(top_n, len(docs_to_rank)),
                },
                ensure_ascii=False,
            ).encode("utf-8")

            resp = self._client.post(
                f"{self.api_base}/rerank",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                content=body,
            )
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            # 按 index 排序后返回 (文档, 分数)
            scored = [
                (docs_to_rank[r["index"]], r["relevance_score"])
                for r in results
            ]
            return scored

        except httpx.HTTPStatusError as e:
            print(f"[Reranker] API 错误: {e.response.status_code} {e.response.text[:200]}")
            return [(d, 0.0) for d in documents[:top_n]]  # 降级：保持原序
        except Exception as e:
            print(f"[Reranker] 请求异常: {type(e).__name__}: {e}")
            return [(d, 0.0) for d in documents[:top_n]]


def get_reranker(
    mode: str = "none",
    api_key: str = "",
    model: str = "BAAI/bge-reranker-v2-m3",
    api_base: str = "https://api.siliconflow.cn/v1",
) -> SiliconFlowReranker | None:
    """获取 Reranker 实例

    mode="api"  → 硅基流动 Rerank API（需 api_key）
    mode="none" → 跳过精排，返回 None
    """
    if mode == "api":
        if not api_key:
            print("[Reranker] API 模式需要提供 API Key，已跳过精排")
            return None
        return SiliconFlowReranker(
            api_key=api_key,
            model=model,
            api_base=api_base,
        )

    # "none" 或未知模式
    return None
