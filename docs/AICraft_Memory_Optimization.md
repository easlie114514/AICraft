---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_Memory_Optimization.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782099803109
    ReservedCode2: ""
---
# AICraft 记忆系统优化方案

## 1. 问题诊断

### 1.1 当前架构
```
memory/
├── conversations/          # 完整对话JSON（每条消息一个文件）
└── project-notes/          # 记忆压缩产物（auto_compact_*.md）
```

### 1.2 核心缺陷

| 问题 | 现状 | 影响 |
|------|------|------|
| 碎片化 | 20个compact文件，每个155-886字节 | 同一话题被拆散，检索困难 |
| 注入无上限 | `load_all_notes()` 全量注入 | compact多了直接撑爆context |
| 触发方式单一 | 仅按字符数(5000)触发 | 用户无法按条数控制 |
| 压缩窗口小 | 硬编码最近20条消息 | 上下文截断丢失关键信息 |
| 无合并机制 | compact只增不减 | 文件无限增长，内容重复 |
| 配置不可控 | 仅3个配置项 | 用户无法自定义策略 |

### 1.3 当前代码定位

| 文件 | 职责 | 需改 |
|------|------|------|
| `src/core/memory.py` | MemoryManager + compact_memory() | 重构 |
| `src/core/chat_history.py` | 对话存储/加载 | 小改 |
| `backend/chat_ws.py` | 记忆压缩触发 + 跨会话注入 | 改触发逻辑 |
| `backend/routers/memory.py` | 记忆API | 扩展接口 |
| `src/utils/config.py` | get_context_config() | 扩展配置 |

---

## 2. 优化设计

### 2.1 分层记忆架构

```
                    ┌─────────────────────┐
                    │  Layer 0: 实时对话   │  session_history（内存，不落盘）
                    │  (当前WS会话)        │  裁剪到 max_history_chars
                    └──────────┬──────────┘
                               │ 达到触发条件
                    ┌──────────▼──────────┐
                    │  Layer 1: 短期记忆   │  auto_compact_*.md
                    │  (单个压缩片段)      │  每次压缩生成一个
                    └──────────┬──────────┘
                               │ 文件数 ≥ merge_threshold
                    ┌──────────▼──────────┐
                    │  Layer 2: 长期记忆   │  long_term_memory.md
                    │  (合并摘要)         │  多个compact合并为一个
                    └─────────────────────┘
```

### 2.2 记忆压缩：可配置触发条件

**新增配置项**（扩展 `model.json` 的 `context` 字段）：

```jsonc
{
  "context": {
    // ── 历史裁剪 ──
    "max_history_chars": 50000,          // session_history最大字符数（保留）

    // ── 压缩触发 ──
    "memory_compact_enabled": true,
    "memory_compact_trigger": "messages", // "chars" | "messages" | "both"
    "memory_compact_interval_chars": 8000, // trigger="chars"时：累积多少字符触发
    "memory_compact_interval_msgs": 20,    // trigger="messages"时：累积多少条消息触发
                                           // trigger="both"时：任一条件满足即触发

    // ── 压缩质量 ──
    "memory_compact_window": 40,          // 压缩时取最近N条消息做总结（原硬编码20）
    "memory_compact_max_tokens": 800,     // 压缩输出max_tokens（原硬编码500）

    // ── 长期合并 ──
    "memory_merge_threshold": 8,          // compact文件数达到N时自动合并

    // ── 注入控制 ──
    "memory_inject_max_chars": 4000,      // 注入system prompt的记忆最大字符数
    "memory_inject_strategy": "latest",   // "latest"(最近N字) | "relevant"(RAG检索)
    "cross_session_inject_count": 10      // 跨会话记忆注入条数（原硬编码10）
  }
}
```

**触发逻辑变更**（`chat_ws.py`）：

```python
# 当前：仅按字符计数
memory_char_counter += new_char_count
if memory_char_counter >= memory_compact_interval:

# 优化后：双计数器 + 三种触发模式
memory_char_counter += new_char_count
memory_msg_counter += 1

trigger_chars = (trigger in ("chars", "both")) and (memory_char_counter >= interval_chars)
trigger_msgs  = (trigger in ("messages", "both")) and (memory_msg_counter >= interval_msgs)

if trigger_chars or trigger_msgs:
    memory_char_counter = 0
    memory_msg_counter = 0
    # ... 执行压缩
```

### 2.3 记忆合并：碎片整合

当 `project-notes/` 下的 compact 文件数量 ≥ `memory_merge_threshold` 时：

1. 读取所有 compact 文件内容
2. 用 Flash 模型将它们合并为一个长期记忆摘要
3. 写入 `memory/long_term_memory.md`
4. 删除已合并的 compact 文件

**合并 prompt**：

```
你是一个记忆整合器。以下是多段对话记忆压缩片段，它们来自不同时间的对话。

请将所有内容整合为一份连贯的长期记忆摘要：
- 合并重复信息，保留最新版本
- 按主题分类（技术决策/用户偏好/项目进度/其他）
- 删除已过时或自相矛盾的信息
- 每个主题下用要点形式记录

格式：
## [主题名]
- 要点1
- 要点2

片段内容：
{all_compacts_content}
```

**合并后的文件结构**：

```
memory/
├── conversations/
├── project-notes/              # 只有最近的compact（不超过merge_threshold）
│   └── auto_compact_xxx.md
└── long_term_memory.md         # 合并后的长期记忆（单一文件）
```

### 2.4 记忆注入：有预算地注入

**当前问题**：`load_all_notes()` 无脑全量注入

**优化策略**：

```python
def load_memory_for_inject(self, max_chars: int = 4000, strategy: str = "latest") -> str:
    """按预算加载记忆，不再全量注入"""
    
    # 1. 先加载长期记忆（如果有）
    long_term = self._load_long_term_memory()
    
    # 2. 再加载最近的compact
    recent_compacts = self._load_recent_compacts()
    
    if strategy == "latest":
        # 按时间倒序拼接，截断到max_chars
        parts = []
        total = 0
        # 长期记忆优先（更浓缩）
        if long_term:
            total += len(long_term)
            parts.append(long_term)
        # 再补最近的compact
        for compact in recent_compacts:
            if total + len(compact["content"]) > max_chars:
                # 截断到预算内
                remaining = max_chars - total
                if remaining > 100:  # 至少100字才有价值
                    parts.append(compact["content"][:remaining] + "\n...(已截断)")
                break
            parts.append(compact["content"])
            total += len(compact["content"])
        return "\n\n---\n\n".join(parts)
    
    elif strategy == "relevant":
        # 用RAG检索与当前话题相关的记忆片段
        # （需要当前query作为参数，后续迭代实现）
        pass
```

### 2.5 配置热更新

`get_context_config()` 已经支持热更新（每次消息都重新读取），只需扩展字段：

```python
def get_context_config() -> dict:
    profile_config = load_profile_config("model")
    ctx = profile_config.get("context", {})
    return {
        "max_history_chars": int(ctx.get("max_history_chars", 50000)),
        "memory_compact_enabled": bool(ctx.get("memory_compact_enabled", True)),
        "memory_compact_trigger": str(ctx.get("memory_compact_trigger", "messages")),
        "memory_compact_interval_chars": int(ctx.get("memory_compact_interval_chars", 8000)),
        "memory_compact_interval_msgs": int(ctx.get("memory_compact_interval_msgs", 20)),
        "memory_compact_window": int(ctx.get("memory_compact_window", 40)),
        "memory_compact_max_tokens": int(ctx.get("memory_compact_max_tokens", 800)),
        "memory_merge_threshold": int(ctx.get("memory_merge_threshold", 8)),
        "memory_inject_max_chars": int(ctx.get("memory_inject_max_chars", 4000)),
        "memory_inject_strategy": str(ctx.get("memory_inject_strategy", "latest")),
        "cross_session_inject_count": int(ctx.get("cross_session_inject_count", 10)),
    }
```

---

## 3. 前端UI：记忆设置面板

在设置页面增加「记忆」选项卡：

```
┌──────────────────────────────────────────┐
│  记忆设置                                 │
├──────────────────────────────────────────┤
│                                          │
│  记忆压缩         [开启 ●]              │
│                                          │
│  触发条件         ○按字符数 ○按消息条数   │
│                  ●两者任一               │
│                                          │
│  字符阈值         [8000    ] 字符        │
│  条数阈值         [20      ] 条消息      │
│  压缩窗口         [40      ] 条消息      │
│  压缩输出上限     [800     ] tokens      │
│                                          │
│  ── 长期记忆 ──                          │
│  自动合并阈值     [8       ] 个片段      │
│                                          │
│  ── 注入控制 ──                          │
│  注入上限         [4000    ] 字符        │
│  注入策略         [最近优先 ▼]           │
│  跨会话条数       [10      ] 条          │
│                                          │
│  ── 状态 ──                              │
│  短期记忆片段     20 个  [合并现在]      │
│  长期记忆大小     0 字节                  │
│                                          │
│         [恢复默认]  [保存]               │
└──────────────────────────────────────────┘
```

**API端点扩展**（`backend/routers/memory.py`）：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/memory/stats` | 记忆统计（compact数/长期记忆大小/总字符数） |
| POST | `/api/memory/merge` | 手动触发合并 |
| GET | `/api/memory/config` | 获取记忆配置 |
| PUT | `/api/memory/config` | 更新记忆配置 |

---

## 4. 实现优先级

### P0 — 必做（解决核心痛点）
1. **配置扩展**：`config.py` + `model.json` 新增字段，支持热更新
2. **双触发器**：`chat_ws.py` 增加 `memory_msg_counter`，支持 chars/messages/both 三种触发
3. **压缩窗口放大**：`memory.py` 的 `compact_memory()` 用配置的 `memory_compact_window` 替代硬编码20
4. **注入上限**：`memory.py` 新增 `load_memory_for_inject(max_chars)`，替代无脑全量注入

### P1 — 应做（结构性改进）
5. **自动合并**：compact文件数 ≥ threshold 时自动触发合并，生成 `long_term_memory.md`
6. **记忆统计API**：`/api/memory/stats` + `/api/memory/merge`
7. **前端设置面板**：记忆配置可视化编辑

### P2 — 可做（锦上添花）
8. **RAG检索注入**：`memory_inject_strategy="relevant"` 用向量检索替代按时间注入
9. **记忆重要性评分**：压缩时给每条记忆标注重要性，注入时优先高权重
10. **记忆手动编辑**：前端可直接编辑/删除单条记忆

---

## 5. 关键实现细节

### 5.1 chat_ws.py 改动

```python
# 新增消息计数器（与memory_char_counter并列）
memory_msg_counter = 0

# 在消息处理循环中，更新双计数器
memory_char_counter += new_char_count
memory_msg_counter += new_msg_count  # 新增

# 触发判断
trigger = ctx_config["memory_compact_trigger"]
should_compact = False
if trigger in ("chars", "both"):
    should_compact = should_compact or memory_char_counter >= ctx_config["memory_compact_interval_chars"]
if trigger in ("messages", "both"):
    should_compact = should_compact or memory_msg_counter >= ctx_config["memory_compact_interval_msgs"]

if ctx_config["memory_compact_enabled"] and should_compact:
    memory_char_counter = 0
    memory_msg_counter = 0
    # 压缩逻辑不变，但传 window 参数
    asyncio.create_task(_compact())

# 记忆注入部分
# 旧代码：notes = deps.memory_manager.load_all_notes()
# 新代码：
inject_max = ctx_config["memory_inject_max_chars"]
notes = deps.memory_manager.load_memory_for_inject(max_chars=inject_max)
```

### 5.2 memory.py 改动

```python
# 新增方法
def load_memory_for_inject(self, max_chars: int = 4000) -> str:
    """按预算加载记忆"""
    parts = []
    total = 0
    
    # 长期记忆优先
    long_term_path = MEMORY_DIR / "long_term_memory.md"
    if long_term_path.exists():
        content = long_term_path.read_text(encoding="utf-8")
        if total + len(content) <= max_chars:
            parts.append(content)
            total += len(content)
    
    # 最近的compact补充
    compacts = sorted(NOTES_DIR.glob("auto_compact_*.md"), reverse=True)
    for f in compacts:
        content = f.read_text(encoding="utf-8")
        remaining = max_chars - total
        if remaining <= 100:
            break
        if len(content) <= remaining:
            parts.append(content)
            total += len(content)
        else:
            parts.append(content[:remaining] + "\n...(已截断)")
            break
    
    return "\n\n---\n\n".join(parts) if parts else ""


async def merge_compacts(self, model_config: dict) -> str | None:
    """合并所有短期compact为长期记忆"""
    compacts = sorted(NOTES_DIR.glob("auto_compact_*.md"))
    if not compacts:
        return None
    
    # 读取所有compact内容
    all_content = []
    for f in compacts:
        content = f.read_text(encoding="utf-8")
        all_content.append(content)
    
    if not all_content:
        return None
    
    merged_text = "\n\n---片段分隔---\n\n".join(all_content)
    
    # 用Flash模型合并
    prompt = (
        "你是一个记忆整合器。以下是多段对话记忆压缩片段。\n"
        "请将所有内容整合为一份连贯的长期记忆摘要：\n"
        "- 合并重复信息，保留最新版本\n"
        "- 按主题分类（技术决策/用户偏好/项目进度/其他）\n"
        "- 删除已过时或自相矛盾的信息\n"
        "- 每个主题下用要点形式记录\n\n"
        f"片段内容：\n{merged_text}"
    )
    
    try:
        import litellm
        kwargs = {
            "model": model_config.get("model_id", ""),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1500,
        }
        for key in ("api_key", "api_base"):
            val = model_config.get(key, "")
            if val:
                kwargs[key] = val
        
        response = await litellm.acompletion(**kwargs)
        summary = response.choices[0].message.content or ""
        if not summary.strip():
            return None
        
        # 写入长期记忆（覆盖式，每次合并都是全量重写）
        long_term_path = MEMORY_DIR / "long_term_memory.md"
        header = "# 长期记忆（自动合并）\n\n"
        long_term_path.write_text(header + summary, encoding="utf-8")
        
        # 删除已合并的compact
        for f in compacts:
            f.unlink()
        
        return str(long_term_path)
    except Exception:
        return None


# compact_memory 改动：使用配置的 window 和 max_tokens
async def compact_memory(self, messages: list[dict], model_config: dict, 
                         role: str = "", window: int = 40, 
                         max_tokens: int = 800) -> str | None:
    # ...
    filtered = [m for m in messages if m.get("role") != "system"]
    if len(filtered) < 2:
        return None
    
    conv_text = "\n".join(
        f"[{m['role']}]: {str(m.get('content', ''))[:500]}"
        for m in filtered[-window:]  # 使用配置的window而非硬编码20
    )
    # kwargs中 max_tokens 使用传入参数
    kwargs["max_tokens"] = max_tokens
    # ...其余不变
```

### 5.3 合并触发时机

两个触发点：
1. **自动**：`chat_ws.py` 在压缩后检查compact文件数，≥threshold时自动合并
2. **手动**：前端设置面板点"合并现在"→ 调 `/api/memory/merge`

```python
# chat_ws.py _compact() 末尾追加
async def _compact():
    try:
        compact_model = select_model_for_task("memory_compact", model_config)
        path = await deps.memory_manager.compact_memory(
            list(session_history),
            compact_model,
            role_name or str(deps.role_loader.get_default_role()),
            window=ctx_config["memory_compact_window"],
            max_tokens=ctx_config["memory_compact_max_tokens"],
        )
        if path:
            await ws.send_json({
                "type": "inject_info",
                "items": [f"记忆: 已压缩到 memory/project-notes/{Path(path).name}"]
            })
            
            # 检查是否需要自动合并
            compact_count = len(list(NOTES_DIR.glob("auto_compact_*.md")))
            if compact_count >= ctx_config["memory_merge_threshold"]:
                merge_path = await deps.memory_manager.merge_compacts(compact_model)
                if merge_path:
                    await ws.send_json({
                        "type": "inject_info",
                        "items": [f"记忆: 已将 {compact_count} 个片段合并为长期记忆"]
                    })
    except Exception:
        pass
```

---

## 6. 迁移说明

对现有用户**零迁移成本**：
- 新配置字段都有默认值，不配置则用默认行为
- 现有的 `auto_compact_*.md` 文件格式不变，只是增加了合并机制
- `long_term_memory.md` 是新文件，不影响已有逻辑
- 旧配置 `memory_compact_interval_chars` 保留兼容，新字段增量添加

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
