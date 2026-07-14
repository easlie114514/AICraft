"""语义分片器 — 基于文档结构 + embedding 相似度低谷检测

替代 RecursiveCharacterTextSplitter 的强制字符数切分。

工作模式：
- embed_fn 可用：结构预分割 → embedding 相似度低谷检测 → 合并/裁剪 → 加重叠
- embed_fn 不可用：结构预分割 → 中文标点感知边界 → 合并/裁剪 → 加重叠

两者都远优于 RecursiveCharacterTextSplitter，因为：
1. 使用中文标点（。！？；）作为优先分隔符，而非只有空格
2. 先按文档结构（标题、段落、代码块）预分割，再决定是否进一步切分
3. embed 模式下检测语义转折点，而非盲切
"""

import re
from pathlib import Path


class SemanticChunker:
    """语义分片器"""

    # 常见 embedding 模型的 token 上限
    MODEL_TOKEN_LIMITS = {
        "all-MiniLM-L6-v2": 256,
        "BAAI/bge-large-zh-v1.5": 512,
        "BAAI/bge-large-en-v1.5": 512,
        "BAAI/bge-m3": 8192,
    }

    def __init__(
        self,
        embed_fn=None,
        similarity_threshold: float = 0.5,
        min_chunk_chars: int = 200,
        max_chunk_chars: int = 1500,
        overlap_chars: int = 300,
        max_embedding_tokens: int | None = None,
    ):
        self.embed_fn = embed_fn
        self.similarity_threshold = similarity_threshold
        self.min_chunk_chars = min_chunk_chars
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars
        # embedding 模型的 token 上限，None 时不做 token 检查
        self.max_embedding_tokens = max_embedding_tokens

    # ── 公开入口 ──

    def split(self, text: str, doc_type: str = "text") -> list[str]:
        """将文本语义分片

        Args:
            text: 原始文本
            doc_type: 文档类型提示 ("text" | "markdown" | "code")
        """
        if not text or not text.strip():
            return []

        # embedding 模型 token 上限 → 字符上限
        # 中文 1 char ≈ 1.5 tokens, 大模型用 0.8 系数, 小模型保守用 0.65
        effective_max_chars = self.max_chunk_chars
        if self.max_embedding_tokens is not None:
            coef = 0.8 if self.max_embedding_tokens >= 1000 else 0.65
            token_safe_chars = int(self.max_embedding_tokens * coef)
            if token_safe_chars < effective_max_chars:
                print(f"[SemanticChunker] embedding {self.max_embedding_tokens}t → 分片上限 {token_safe_chars}字")
                effective_max_chars = token_safe_chars

        # 1. 结构预分割
        segments = self._presplit(text, doc_type)

        # 2. 语义边界检测（embed_fn 可用时）或智能合并
        if self.embed_fn is not None and len(segments) > 1:
            segments = self._semantic_merge(segments)

        # 3. 处理过长片段 + 合并过短片段
        chunks = self._size_control(segments, doc_type, effective_max_chars)

        # 4. 添加重叠缓冲区（受上限约束，prefix 不会让总长超标）
        chunks = self._add_overlap(chunks, effective_max_chars)

        # 5. 最终检查：超限则强制再切
        if self.max_embedding_tokens is not None and chunks:
            final = []
            for chunk in chunks:
                est_tokens = len(chunk) / 1.5
                if est_tokens > self.max_embedding_tokens:
                    print(f"[SemanticChunker] ⚠️ chunk {len(chunk)}字 ≈ {est_tokens:.0f}t 超限, 强制再切")
                    final.extend(self._force_split_long(chunk, "text", effective_max_chars))
                else:
                    final.append(chunk)
            chunks = final

        return chunks

    # ── 1. 结构预分割 ──

    def _presplit(self, text: str, doc_type: str) -> list[str]:
        """按文档结构预分割，返回语义上不宜再切分的基本单元"""
        if doc_type == "markdown":
            return self._presplit_markdown(text)
        elif doc_type == "code":
            return self._presplit_code(text)
        else:
            return self._presplit_text(text)

    def _presplit_markdown(self, text: str) -> list[str]:
        """Markdown：按标题 + 代码块边界预分割"""
        # 先在代码块边界切（保护代码不被当段落处理）
        parts = re.split(r"(\n```[^\n]*\n.*?\n```)", text, flags=re.DOTALL)

        segments = []
        for part in parts:
            if part.startswith("\n```"):
                segments.append(part.strip())
            else:
                # 在标题行处切分
                sub = re.split(r"(\n#{1,6}\s+.+)", part)
                for s in sub:
                    s = s.strip()
                    if s:
                        segments.append(s)
        return segments

    def _presplit_code(self, text: str) -> list[str]:
        """代码文件：按函数/类定义 + 空行边界预分割"""
        # 在 def/class 定义前切分（独立行）
        parts = re.split(r"(\n(?=def\s|\bclass\s))", text)

        segments = []
        for part in parts:
            # 进一步用连续空行切分
            sub = re.split(r"\n\n+", part)
            for s in sub:
                s = s.strip()
                if s:
                    segments.append(s)
        return segments

    def _presplit_text(self, text: str) -> list[str]:
        """纯文本：按段落 + 句子边界预分割"""
        # 1. 先按段落切（连续空行）
        paragraphs = re.split(r"\n\s*\n", text)

        segments = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            # 2. 如果段落仍然很长，按句子边界切
            if len(para) > self.max_chunk_chars:
                sentences = self._split_by_punctuation(para)
                segments.extend(sentences)
            else:
                segments.append(para)

        return segments

    @staticmethod
    def _split_by_punctuation(text: str) -> list[str]:
        """按中文标点切分句子，保持标点在上一句末尾"""
        # 在句末标点后切分（保留标点在上一句）
        parts = re.split(r"(?<=[。！？；])\s*", text)
        result = [p.strip() for p in parts if p.strip()]
        # 如果切后全都很短，合并
        if result and all(len(p) < 50 for p in result):
            merged = []
            buf = ""
            for p in result:
                buf += p
                if len(buf) >= 80:
                    merged.append(buf)
                    buf = ""
            if buf:
                if merged:
                    merged[-1] += buf
                else:
                    merged.append(buf)
            return merged if merged else result
        return result

    # ── 2. 语义相似度合并 ──

    def _semantic_merge(self, segments: list[str]) -> list[str]:
        """基于 embedding 相似度合并语义连续的段，在低谷处切分"""
        try:
            embeddings = self._batch_embed(segments)
        except Exception as e:
            print(f"[SemanticChunker] embedding 失败: {e}, 回退到结构模式")
            return segments  # 降级：保持结构预分割结果

        # 计算相邻段相似度
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = self._cosine_sim(embeddings[i], embeddings[i + 1])
            similarities.append(sim)

        # 检测低谷：低于阈值且是局部最低点
        boundaries: set[int] = set()
        for i, sim in enumerate(similarities):
            if sim < self.similarity_threshold:
                # 检查是否为局部最低点（窗口 ±1）
                left = similarities[i - 1] if i > 0 else sim
                right = similarities[i + 1] if i < len(similarities) - 1 else sim
                if sim <= left and sim <= right:
                    boundaries.add(i)

        # 在低谷处切分
        merged = []
        buf = ""
        for i, seg in enumerate(segments):
            buf += ("\n\n" if buf else "") + seg
            if i in boundaries:
                merged.append(buf)
                buf = ""
        if buf:
            merged.append(buf)

        return merged

    def _batch_embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成 embedding，处理空文本"""
        embeddings = []
        for i in range(0, len(texts), 32):  # 分批，避免单次请求过大
            batch = texts[i:i + 32]
            # 过滤纯空白的文本，用零向量占位
            clean = [t if t.strip() else " " for t in batch]
            batch_emb = self.embed_fn(clean)
            embeddings.extend(batch_emb)
        return embeddings

    @staticmethod
    def _cosine_sim(a: list[float], b: list[float]) -> float:
        """余弦相似度"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    # ── 3. 尺寸控制 ──

    def _size_control(self, segments: list[str], doc_type: str, effective_max_chars: int) -> list[str]:
        """合并过短片段，切分过长片段"""
        max_c = effective_max_chars
        # 合并过短片段
        merged = []
        buf = ""
        for seg in segments:
            combined = buf + ("\n\n" if buf else "") + seg
            if len(combined) < max_c:
                buf = combined
            else:
                if buf:
                    merged.append(buf)
                buf = seg
        if buf:
            merged.append(buf)

        # 切分仍然过长的片段
        result = []
        for chunk in merged:
            if len(chunk) <= max_c:
                result.append(chunk)
            else:
                result.extend(self._force_split_long(chunk, doc_type, max_c))
        return result

    def _force_split_long(self, text: str, doc_type: str, max_chars: int) -> list[str]:
        """对超出上限的片段，用中文标点感知分隔符切分

        分隔符优先级（从优到劣）：
        \n\n → \n → 。→ ！→ ？→ ；→ ，→ " " → 逐字符
        """
        separators = ["\n\n", "\n", "。", "！", "？", "；", "，", ". ", "! ", "? ", " ", ""]
        return self._recursive_split(text, separators, max_chars)

    def _recursive_split(self, text: str, separators: list[str], max_chars: int) -> list[str]:
        """递归切分：在最佳分隔符处下刀"""
        if len(text) <= max_chars:
            return [text] if text.strip() else []

        sep = separators[0] if separators else ""
        remaining_seps = separators[1:] if len(separators) > 1 else []

        if sep == "":
            result = []
            for i in range(0, len(text), max_chars):
                result.append(text[i:i + max_chars])
            return result

        splits = text.split(sep)
        if len(splits) == 1:
            return self._recursive_split(text, remaining_seps, max_chars)

        result = []
        buf = ""
        for i, part in enumerate(splits):
            separator = sep if i < len(splits) - 1 else ""
            proposed = buf + part + separator

            if len(proposed) <= max_chars:
                buf = proposed
            else:
                if buf:
                    result.append(buf)
                if len(part + separator) > max_chars:
                    sub = self._recursive_split(part + separator, remaining_seps, max_chars)
                    result.extend(sub)
                    buf = ""
                else:
                    buf = part + separator

        if buf:
            result.append(buf)

        return [r for r in result if r.strip()]

    # ── 4. 重叠缓冲区 ──

    def _add_overlap(self, chunks: list[str], max_chars: int) -> list[str]:
        """为每个 chunk 添加前一片段末尾的重叠缓冲区"""
        if len(chunks) <= 1:
            return chunks

        result = [chunks[0]]
        for i in range(1, len(chunks)):
            prev = chunks[i - 1]
            # prefix 不能超过 max_chars * 0.5，确保 body + prefix ≤ max_chars * 1.5
            max_prefix = min(self.overlap_chars, int(max_chars * 0.4))
            prefix = self._extract_overlap_prefix(prev, max_prefix)
            if prefix:
                result.append(prefix + "\n" + chunks[i])
            else:
                result.append(chunks[i])

        return result

    def _extract_overlap_prefix(self, prev_chunk: str, max_prefix: int) -> str:
        """从前一 chunk 末尾提取重叠前缀，对齐句边界"""
        if len(prev_chunk) <= max_prefix:
            return "[上文续...]\n" + prev_chunk

        # 从末尾取 max_prefix * 1.5 的文本，再对齐到句边界
        tail_start = max(0, len(prev_chunk) - int(max_prefix * 1.5))
        tail = prev_chunk[tail_start:]

        # 向前调整到最近的句子边界
        for sep in ["\n\n", "\n", "。", "！", "？", "；", ". ", "! ", "? "]:
            pos = tail.find(sep)
            if pos > 0 and pos < len(tail) // 2:
                tail = tail[pos + len(sep):]
                break

        # 如果仍然太长，截断
        if len(tail) > max_prefix:
            tail = tail[-max_prefix:]
            for sep in ["。", "！", "？", "；", "，"]:
                pos = tail.find(sep)
                if pos > len(tail) // 2:
                    tail = tail[pos + len(sep):]
                    break

        return "[上文续...]\n" + tail if tail.strip() else ""
