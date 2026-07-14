# AICraft RAG 改进方案

> 诊断日期：2026-07-13
> 诊断范围：`src/core/rag_engine.py`、`src/core/embedding.py`、`backend/chat_ws.py`

---

## 一、现状诊断

### 1.1 分片（Chunking）— ❌ 无语义分片

**当前实现** (`rag_engine.py:273-277`)：

```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
)
```

问题：

| 问题 | 影响 |
|------|------|
| `chunk_size=500` 字符过小 | 单个片段难以承载完整的语义单元，回答容易断章取义 |
| `chunk_overlap=50` (仅 10%) | 边界上下文丢失严重，相邻片段衔接断裂 |
| 固定字符数切分 | 不考虑句子/段落/语义边界，可能在句子中间截断 |
| 无语义分片 | 没有利用 embedding 相似度检测语义转折点，同一主题可能被切到两个不同片段 |

> `RecursiveCharacterTextSplitter` 虽然优先在 `\n\n` → `\n` → `。` → ` ` 等分隔符处切分，**比纯字符截断好**，但本质上仍是固定大小切分，不是语义分片。

#### LangChain 依赖说明

整个项目中 **仅此一处** 使用了 LangChain 生态的包：

| 位置 | 引用 |
|------|------|
| `src/core/rag_engine.py:243` | `from langchain_text_splitters import RecursiveCharacterTextSplitter` |
| `requirements.txt` | `langchain-text-splitters` |

项目没有引入 `langchain-core`、`langchain-community` 等重型依赖，只是为这一个切分器装了轻量包 `langchain-text-splitters`。**也就是说，项目中唯一用到 LangChain 的地方，就是被诊断出的"强制切片"问题所在。** 改为语义分片后，此依赖可以直接移除，反而让依赖树更干净。

### 1.2 召回（Retrieval）— ⚠️ 仅简单向量检索

**当前实现** (`rag_engine.py:339-382`)：

```python
result = collection.query(
    query_texts=[query],
    n_results=top_k,   # 固定 5
)
```

问题：

| 问题 | 影响 |
|------|------|
| 单一向量相似度检索 | 只能捕捉语义相似，无法匹配精确关键词 |
| `top_k=5` 固定且偏少 | 后续无重排，直接截断可能遗漏高价值片段 |
| 无查询改写 | 用户口语化提问与文档书面语不匹配时召回率低 |
| 无混合检索 | 缺少 BM25/关键词等稀疏检索互补 |

### 1.3 重排序（Reranking）— ❌ 完全缺失

**当前实现**：`search()` 方法直接返回 ChromaDB 的 cosine 相似度排序结果，**没有任何重排逻辑**。

缺失的能力：

| 缺失环节 | 说明 |
|----------|------|
| Cross-Encoder 重排 | 用更强的模型对召回结果重新打分，精度远高于双塔向量相似度 |
| 多样性重排 (MMR) | 召回结果可能高度重复，缺少去重/多样性控制 |
| 相关性阈值过滤 | 低相关度的片段也被注入，浪费上下文窗口 |
| 上下文窗口感知排序 | 不知道最终有多少 token 预算，无脑塞入所有结果 |

### 1.4 后处理（Post-processing）— ❌ 无过滤，粗暴拼接

**当前实现** (`chat_ws.py:594-610`)：

```python
rag_results = await loop.run_in_executor(None, deps.rag_engine.search, user_text, 5)
if rag_results:
    rag_text = "\n\n".join(rag_results)
    system_pieces.append(("rag_results", prompt_prefix + rag_text, 3))
```

问题：

| 问题 | 影响 |
|------|------|
| 所有结果无脑拼接 | 低相关片段浪费 token 预算 |
| 无去重 | 高度相似的片段重复注入 |
| 无上下文压缩 | 片段可能很长，超出实际需要 |
| 预算裁剪粗暴 (`context_budget.py:152-155`) | 超预算时直接砍掉后半段，可能丢失关键信息 |

---

## 二、改进方案

### 方案总览

```
                        当前                              改进后
                  ┌──────────────┐              ┌──────────────────┐
  文档 ──────────→│ 固定500字切分  │     文档 ──→│ 语义分片           │
                  └──────┬───────┘              │ (SemanticChunker) │
                         ↓                      └────────┬─────────┘
                  ┌──────────────┐                       ↓
  查询 ──────────→│ 原始查询      │     查询 ──→│ 查询改写 + 混合检索  │
                  └──────┬───────┘              └────────┬─────────┘
                         ↓                               ↓
                  ┌──────────────┐              ┌──────────────────┐
                  │ 向量检索 top5 │              │ 向量 + BM25 粗排  │
                  └──────┬───────┘              │ 召回 top_k=20     │
                         ↓                      └────────┬─────────┘
                  ┌──────────────┐                       ↓
                  │ (无重排)      │              ┌──────────────────┐
                  └──────┬───────┘              │ Cross-Encoder 精排│
                         ↓                      │ + MMR 多样性去重   │
                  ┌──────────────┐              └────────┬─────────┘
                  │ 粗暴拼接注入  │                       ↓
                  └──────────────┘              ┌──────────────────┐
                                                │ 相关性过滤 + 压缩  │
                                                │ 预算感知注入       │
                                                └──────────────────┘
```

### 2.1 语义分片（Semantic Chunking）

#### 方案选择

| 方案 | 原理 | 适用场景 | 复杂度 |
|------|------|----------|--------|
| **A. 基于 Embedding 相似度** | 计算相邻句子的 embedding 余弦相似度，在相似度"低谷"处切分 | 通用文档 | 中 |
| B. 基于 LLM 分割 | 让 LLM 判断语义边界 | 高度结构化文档 | 高（成本大） |
| C. 基于段落/标题结构 | 按 Markdown 标题/段落层级切分 | Markdown/结构化文档 | 低 |

#### 推荐：**方案 A + C 混合**（嵌入相似度 + 文档结构感知）

```
算法流程:
1. 按文档结构预分割（Markdown 标题、段落、代码块等）
2. 对每个预分割单元用 embedding 模型生成向量
3. 计算相邻单元的余弦相似度
4. 在相似度低于阈值(如 0.5)处切分
5. 合并过小的片段，保证最小 100 token、最大 800 token
6. 重叠缓冲区：每个 chunk 从上一 chunk 末尾取 100~200 token 作为前缀
```

**关键参数建议**：

| 参数 | 当前值 | 建议值 | 说明 |
|------|--------|--------|------|
| chunk_size | 500 字符 | 500~800 token | 根据文档类型自适应，约合中文 750~1200 字符 |
| chunk_overlap | 50 字符 | 100~200 token | 约合中文 150~300 字符，作为检索时的上下文安全垫 |
| 相似度阈值 | — | 0.5~0.6 | 低于此值视为语义边界 |
| 最小chunk | — | 100 token | 低于此值合并到相邻片段 |

> **为什么用 token 而不是字符？** Embedding 模型和 LLM 都以 token 为粒度计费/计量。中文 1 token ≈ 1.5 字符，直接以 token 设计可以精确控制窗口占用，避免中英混排时字符数失真。

#### 重叠缓冲区设计

语义分片的切分点由相似度低谷决定，而非固定步长滑动。因此重叠缓冲区需要**语义边界感知**：

```
┌─────────────────────────────────────────────────────────────┐
│  原文:  ...段落A... │ ←低谷→ │ ...段落B... │ ←低谷→ │ ...段落C...  │
└─────────────────────────────────────────────────────────────┘
                          ↓ 切分
┌──────────────────────┬──────────────────────┬──────────────────────┐
│ Chunk 1: A (主体)     │ Chunk 2: B (主体)     │ Chunk 3: C (主体)     │
│ 无前缀               │ 前缀: A 末尾 100-200t │ 前缀: B 末尾 100-200t │
│                      │ 标记: [上文续...]     │ 标记: [上文续...]     │
└──────────────────────┴──────────────────────┴──────────────────────┘
```

**重叠内容选择策略**（三步）：

```python
def _build_overlap(prev_chunk: str, overlap_tokens: int = 150) -> str:
    """
    从上一 chunk 末尾提取重叠缓冲区。
    不做固定字符截断，而是找到最近的完整句子边界。
    """
    # 1. 估算目标字符数（中文 1 token ≈ 1.5 chars）
    target_chars = overlap_tokens * 1.5

    # 2. 从 prev_chunk 末尾向前扫描
    tail = prev_chunk[-int(target_chars * 1.5):]  # 多取 50%，防止欠取

    # 3. 向前调整到最近的句子边界（。！？\n\n）
    #    避免从句子中间开始
    sentence_breaks = ['。', '！', '？', '\n\n', '. ', '! ', '? ']
    best_pos = 0
    for sep in sentence_breaks:
        pos = tail.find(sep)
        if 0 < pos < best_pos or best_pos == 0:
            best_pos = pos + len(sep)

    if best_pos > 0:
        tail = tail[best_pos:]

    # 4. 如果仍然超过限制，tokenize 后精确截断到 overlap_tokens
    tokens = tokenize(tail)
    if len(tokens) > overlap_tokens:
        tail = detokenize(tokens[-overlap_tokens:])

    return "[上文续...]\n" + tail
```

**边界处的关键处理**：
- 重叠区加上 `[上文续...]` 标记，让 LLM 知道这是上下文衔接而非独立段落
- 如果 prev_chunk 本身就小于 overlap_tokens，直接整体作为下一个 chunk 的前缀（即 chunk_overlap > chunk 本身时，两 chunk 共享同一段文本——这在极小文档中可能发生，属于正常降级）
- 检索时两 chunk 都被命中 → LLM 看到的上下文是连续的，不会出现"断章取义"

**为什么是 100~200 token？**

| overlap | 效果 |
|---------|------|
| < 50 token | 边界上下文不足，检索到 chunk 边界附近的内容时容易缺失前文 |
| 100~200 token | 约 2-4 个中文句子，覆盖绝大多数语义衔接的必备上下文 |
| > 300 token | 冗余过多，多个 chunk 重复内容占比高，浪费向量存储和 token 预算 |

权衡后取 **150 token 默认**，约 3 句中文，可配置为 100~200 区间。

#### 更新后的伪代码

```python
class SemanticChunker:
    def __init__(self, embed_fn, similarity_threshold=0.5,
                 min_chunk_tokens=100, max_chunk_tokens=800,
                 overlap_tokens=150):
        ...

    def split(self, text: str, doc_type: str = "text") -> list[str]:
        # 1. 预分割：按文档结构/句子
        segments = self._presplit(text, doc_type)
        # 2. 计算相邻段 embedding 相似度
        embeddings = [self.embed_fn([s])[0] for s in segments]
        similarities = [cosine_sim(embeddings[i], embeddings[i+1])
                        for i in range(len(embeddings)-1)]
        # 3. 在相似度低谷处切分
        boundaries = self._find_boundaries(similarities)
        # 4. 合并过小片段、限制最大 token 数
        chunks = self._merge_and_trim(segments, boundaries)
        # 5. 为每个 chunk 构建重叠缓冲区（从上一 chunk 末尾取）
        chunks = self._add_overlap(chunks)
        return chunks

    def _add_overlap(self, chunks: list[str]) -> list[str]:
        result = [chunks[0]]  # 第一个 chunk 不需要前缀
        for i in range(1, len(chunks)):
            prefix = self._build_overlap(chunks[i-1], self.overlap_tokens)
            result.append(prefix + chunks[i])
        return result
```

---

### 2.2 混合检索（Hybrid Retrieval）

#### 当前：仅向量检索
#### 改进：向量 + 关键词 混合

| 检索方式 | 优势 | 劣势 |
|----------|------|------|
| 向量检索 (Dense) | 语义匹配，同义词/改写 | 对精确关键词（代码、ID、术语）弱 |
| 关键词检索 (Sparse/BM25) | 精确匹配，专有名词 | 无法理解同义改写 |

#### 推荐方案：**向量 + BM25 混合**，使用 RRF (Reciprocal Rank Fusion) 融合

```
算法:
1. 用户查询 → 向量检索 top_k*2 条
2. 用户查询 → BM25 检索 top_k*2 条
3. RRF 融合两个排序结果:
   RRF_score(d) = Σ 1/(k + rank_i(d))   # k=60
4. 取融合后 top_k 条进入精排
```

**为什么不用 ChromaDB 内置的 BM25？** ChromaDB 目前不支持 BM25，需要额外引入轻量级方案：

- **推荐**：使用 `rank_bm25` (纯 Python，无额外依赖) 构建内存中 BM25 索引
- **备选**：集成 Elasticsearch / Meilisearch（重量级，适合大规模）

对于 AICraft 的项目规模（本地知识库，数百到数千文档），`rank_bm25` 完全够用。

#### 查询改写（Query Rewriting）

在检索前增加一个轻量级查询优化步骤：

```
原始查询: "怎么配置那个AI模型"
改写后: "如何配置 AI 模型 API Key"
```

- **触发条件**：查询过短 (< 10字) 或包含口语化指代词（"那个"、"这个"）
- **实现方式**：用 Flash 模型做一次快速改写（约 50 tokens），几乎无感延迟
- **设计为可选**：配置开关，用户可选择关闭以节省 token

#### 伪代码

```python
class HybridRetriever:
    def __init__(self, vector_store, bm25_index, embed_fn):
        ...

    def retrieve(self, query: str, top_k: int = 20,
                 rewrite: bool = True) -> list[dict]:
        # 可选：查询改写
        if rewrite and self._needs_rewrite(query):
            query = self._rewrite_query(query)

        # 向量检索
        dense_results = self.vector_store.query(query, n_results=top_k * 2)

        # BM25 关键词检索
        sparse_results = self.bm25_index.search(query, top_k * 2)

        # RRF 融合
        fused = self._rrf_fusion(dense_results, sparse_results, k=60)
        return fused[:top_k]
```

---

### 2.3 Cross-Encoder 精排（Reranking）

#### 推荐方案：本地 Reranker 模型

| 方案 | 模型 | 延迟 | 精度 |
|------|------|------|------|
| **A. 本地 ONNX** | `bge-reranker-v2-m3` / `ms-marco-MiniLM` | ~50ms/条 | ⭐⭐⭐⭐ |
| B. API 调用 | SiliconFlow Rerank API / Cohere Rerank | ~200ms | ⭐⭐⭐⭐⭐ |
| C. LLM 打分 | 用 Flash 模型对每条打分 | ~500ms | ⭐⭐⭐⭐⭐ |

#### 推荐：**方案 A（本地 ONNX）+ B（API 备选）**

理由：
- 本地模型延迟低，可对 top_k=20 结果在 ~1s 内完成重排
- 项目已有 `onnxruntime` 依赖和 ONNX 模型管理经验
- 保留 API 选项作为高精度模式

#### 推荐的 Reranker 模型

| 模型 | 大小 | 说明 |
|------|------|------|
| `BAAI/bge-reranker-v2-m3` | ~1.5GB | 多语言，中文效果好 |
| `BAAI/bge-reranker-base` | ~1.1GB | 轻量级 |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | ~90MB | 极轻量，英文为主 |

对于 AICraft 的中文场景，推荐 `bge-reranker-v2-m3`，通过 ONNX 量化后约 600MB，可以接受。

#### 精排流程

```
粗排 top_k=20 → Cross-Encoder 逐条打分 → 按 relevance 排序 → MMR 去重 → 取 top_n=5
```

#### MMR (Maximal Marginal Relevance) 多样性去重

```python
def mmr_rerank(docs: list[dict], scores: list[float],
               lambda_param: float = 0.7, top_n: int = 5) -> list[dict]:
    """
    lambda_param: 相关性 vs 多样性权重
    0.7 = 偏相关性, 0.5 = 平衡, 0.3 = 偏多样性
    """
    selected = []
    remaining = list(range(len(docs)))

    while len(selected) < top_n and remaining:
        mmr_scores = []
        for i in remaining:
            relevance = scores[i]
            # 与已选文档的最大相似度
            max_sim = max(
                (cosine_sim(docs[i].embedding, docs[j].embedding)
                 for j in selected),
                default=0
            )
            mmr = lambda_param * relevance - (1 - lambda_param) * max_sim
            mmr_scores.append(mmr)

        best = remaining[argmax(mmr_scores)]
        selected.append(best)
        remaining.remove(best)

    return [docs[i] for i in selected]
```

---

### 2.4 后处理增强

#### 2.4.1 相关性阈值过滤

设置相关性分数阈值，低于阈值的片段不注入：

```python
RELEVANCE_THRESHOLD = 0.3  # 可配置
filtered = [d for d, s in zip(docs, scores) if s >= RELEVANCE_THRESHOLD]
```

#### 2.4.2 上下文窗口感知压缩

根据 ContextBudget 的剩余 token 预算动态决定注入多少 RAG 内容：

```python
def inject_rag_results(docs: list[dict], budget: ContextBudget, max_chars: int = 3000):
    """按预算注入 RAG 结果，优先保留高相关度片段"""
    remaining = budget.remaining_tokens * 2  # token → 字符估算
    injected = []
    for doc in docs:  # 已按 relevance 排序
        snippet = doc.content[:500]  # 单条最多 500 字符
        if len("\n\n".join(injected)) + len(snippet) > min(max_chars, remaining):
            break
        injected.append(snippet)
    return injected
```

#### 2.4.3 片段格式化

每条 RAG 结果附带来源文件名（已存储在 ChromaDB metadata 中）：

```python
# 当前: 纯文本拼接
# 改进: 带来源标注
formatted = []
for doc in docs:
    source = doc.metadata.get("source", "未知")
    fname = Path(source).name
    formatted.append(f"📄 [{fname}]\n{doc.content}")
```

---

## 三、实施优先级

### Phase 1：短期（1-2 周）— 最大收益 / 最小改动

| 任务 | 改动范围 | 预期效果 |
|------|----------|----------|
| **1.1 增大 chunk_size 和 overlap** | `rag_engine.py` 2 行 | 立即改善片段连贯性 |
| `chunk_size: 500字 → 800 token, overlap: 50字 → 150 token` | | |
| **1.2 添加 Cross-Encoder 精排** | 新增 `src/core/reranker.py` | 召回精度提升 30-50% |
| 用 `bge-reranker-v2-m3` ONNX 模型 | | |
| **1.3 RAG 结果去重** | `rag_engine.py` search 末尾 | 减少重复内容注入 |
| 基于 Jaccard/编辑距离的简单去重 | | |

### Phase 2：中期（2-4 周）— 体验质变

| 任务 | 改动范围 | 预期效果 |
|------|----------|----------|
| **2.1 语义分片** | 新增 `src/core/semantic_chunker.py` | 片段语义完整性大幅提升 |
| 基于 embedding 相似度低谷 | | |
| **2.2 混合检索 (向量 + BM25)** | 新增 `src/core/hybrid_retriever.py` | 精确关键词匹配能力 |
| **2.3 相关性阈值过滤** | `rag_engine.py` search() | 减少低质量片段注入 |
| **2.4 上下文窗口感知压缩** | `chat_ws.py` RAG 注入段 | token 预算利用率提升 |

### Phase 3：长期（1-2 月）— 锦上添花

| 任务 | 改动范围 | 预期效果 |
|------|----------|----------|
| **3.1 查询改写** | `rag_engine.py` search 前置 | 口语化查询召回率提升 |
| **3.2 MMR 多样性重排** | 并入精排流程 | 避免冗余片段 |
| **3.3 RAG 评估反馈** | 新模块 | 两两对比/用户反馈优化检索参数 |
| **3.4 增量索引** | `rag_engine.py` | 大目录改动时只索引变更文件 |

---

### 待优化项总览

#### 分片

| # | 项 | 现状 | 预期 |
|---|----|------|------|
| 1 | 语义分片 | `RecursiveCharacterTextSplitter` 固定 500 字硬切 | 改为基于 embedding 相似度低谷检测，片段内语义连贯，不再从中截断 |
| 2 | chunk_size | 500 字符，完整语义单元被切碎 | 增大到 500~800 token（约合中文 750~1200 字符），完整段落不再被切断 |
| 3 | chunk_overlap | 50 字符（仅 10%），边界上下文丢失 | 增大到 100~200 token（约合中文 150~300 字符），边界处上下文平滑过渡，chunk 间语义连续 |
| 4 | LangChain 依赖 | 仅为 `RecursiveCharacterTextSplitter` 引入 `langchain-text-splitters` | 语义分片后移除该依赖，减少依赖树体积 |

#### 召回

| # | 项 | 现状 | 预期 |
|---|----|------|------|
| 5 | 混合检索 | 仅向量相似度检索 | 向量 + BM25 混合 + RRF 融合，精确关键词（代码/ID/术语）也能命中，召回率提升 20-40% |
| 6 | top_k | 固定 5 条，无精排直接截断 | 粗排召回 20 条，留给精排充足候选池，减少遗漏 |
| 7 | 查询改写 | 无 | 口语化提问自动改写为检索友好的书面语，模糊查询召回率明显提升 |

#### 重排

| # | 项 | 现状 | 预期 |
|---|----|------|------|
| 8 | Cross-Encoder 精排 | ChromaDB cosine 排序直接使用 | Cross-Encoder 逐对打分重排，排序精度比双塔向量提升 30-50%，最相关内容排在前面 |
| 9 | 多样性去重 (MMR) | 无 | 抑制高度相似片段的重复注入，相同 token 预算覆盖更多不同角度 |
| 10 | 相关性阈值过滤 | 无 | 低于阈值（如 0.3）的片段直接丢弃，不浪费上下文窗口 |

#### 后处理

| # | 项 | 现状 | 预期 |
|---|----|------|------|
| 11 | 结果去重 | 不同数据源可能返回相似内容，不做去重 | Jaccard 相似度去重，相同内容不重复占 token |
| 12 | 上下文预算感知 | 超预算时粗暴砍半 | 按 relevance 排序后从低到高裁剪，优先保留高价值片段 |
| 13 | 来源标注 | 纯文本拼接，用户不知道片段来自哪个文档 | 每条结果带 `📄 [文件名]` 标注，可追溯、可验证 |

#### 工程化

| # | 项 | 现状 | 预期 |
|---|----|------|------|
| 14 | 增量索引 | 每次全量重建整个目录 | 仅索引新增/修改的文件，大目录重建从分钟级降到秒级 |
| 15 | 参数配置化 | `chunk_size`/`overlap`/`top_k` 全部硬编码在源码中 | 全部参数集中在 `rag_config.json`，调整无需改代码，运行时即时生效 |

---

## 四、配置化设计

所有 RAG 高级参数应集中在 `config/rag_config.json`，支持运行时调整：

```json
{
  "embedding_mode": "auto",
  "embedding_api_key": "",
  "embedding_model": "BAAI/bge-large-zh-v1.5",
  "embedding_api_base": "https://api.siliconflow.cn/v1",

  "chunking": {
    "mode": "semantic",
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "similarity_threshold": 0.5,
    "min_chunk_size": 200,
    "max_chunk_size": 1500
  },

  "retrieval": {
    "mode": "hybrid",
    "top_k": 20,
    "rrf_k": 60,
    "enable_query_rewrite": false
  },

  "reranking": {
    "enabled": true,
    "model": "BAAI/bge-reranker-v2-m3",
    "mode": "local",
    "top_n": 5,
    "relevance_threshold": 0.3,
    "mmr_lambda": 0.7
  },

  "injection": {
    "max_chars": 3000,
    "format": "source_annotated",
    "enable_dedup": true
  }
}
```

---

## 五、兼容性说明

1. **平滑升级**：新参数都有默认值，老配置文件无需修改即可运行
2. **降级策略**：
   - 语义分片失败 → 回退到 `RecursiveCharacterTextSplitter`
   - Reranker 加载失败 → 跳过精排，用粗排结果
   - BM25 索引构建失败 → 仅用向量检索
3. **重新索引提示**：chunking 模式变更后，提示用户重新索引数据源
4. **ONNX 模型管理**：Reranker 模型按 `models/onnx/` 的现有惯例管理，支持 PyInstaller 打包
