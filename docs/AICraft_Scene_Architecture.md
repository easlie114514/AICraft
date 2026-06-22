# AICraft 场景架构设计

> 版本：v1.0 | 日期：2026-06-22

---

## 一、三层分离

```
┌──────────────────────────────────────────────────┐
│               聊天记录 (Chat Records)              │
│  前端 messages[]，纯展示层，只增不减               │
│  "之前聊了什么，全部能翻看到"                       │
└──────────────────────────────────────────────────┘
         │ 展示                            │ 展示
         ▼                                ▼
┌──────────────────┐          ┌──────────────────────┐
│  上下文 (Context)  │          │   记忆 (Memory)       │
│  后端 session_     │  新场景  │   project-notes/      │
│  history           │ ──────→ │   auto_compact +      │
│  当前场景的对话     │  打包    │   long_term           │
│  "AI 现在该知道什么"│          │  跨场景的长期知识      │
└──────────────────┘          └──────────────────────┘
```

| 层 | 存储位置 | 生命周期 | 用途 |
|---|---|---|---|
| 聊天记录 | 前端 `messages[]` | 应用运行期间只增不减 | 用户翻看 |
| 上下文 | 后端 `session_history` | 一个场景内有效，切场景即清空 | AI 当前对话上下文 |
| 记忆 | `memory/project-notes/` | 永久保留 | 跨场景知识召回 |

---

## 二、新场景（New Scene）

### 2.1 概念

"场景"是一段连续对话的上下文边界。用户点击「新场景」按钮时：

1. 当前场景的对话被**全量压缩**为记忆
2. 后端上下文**清空**，AI 从零开始
3. 前端聊天气泡**保留**，插入场景分隔线
4. 后续对话使用**新 conv_id**

### 2.2 按钮行为

```
用户点击「新场景」
    │
    ├─ 前端 (同步)
    │   ├─ messages 插入分隔线 { role: 'divider', scene: N, timestamp }
    │   ├─ 场景计数器 +1
    │   └─ ws.send({ type: 'new_scene' })
    │
    └─ 后端 (异步)
        ├─ 全量压缩 session_history → auto_compact_*.md
        ├─ session_history = []
        ├─ 生成新 conv_id → 返回前端
        └─ 后续消息挂在新的 conv_id 和 session_history 下
```

### 2.3 按钮状态

- AI 回复期间（`streaming === true`）：**禁用**
- 无对话内容时（`session_history` 为空）：**禁用**（没必要切）

---

## 三、场景切换触发记忆压缩

### 3.1 与定时压缩的区别

| | 定时压缩 | 场景压缩 |
|---|---|---|
| 触发条件 | 消息数/字符数达标 | 用户点「新场景」 |
| 压缩范围 | 最近 N 条（window） | **全部** session_history |
| 目的 | 增量保存 | 完整归档当前场景 |

### 3.2 压缩 prompt 差异

场景压缩需要更强调整体总结：
```
你是一个场景记忆归档器。以下是一段完整对话场景的全部内容。
请提取：
1. 用户的核心目标/任务
2. 已完成的进度和关键决策
3. 值得跨场景记住的用户偏好
4. 技术细节（如果涉及代码/配置）
输出格式：要点列表，每点一行。
```

---

## 四、跨场景记忆召回

当用户在新场景中提及之前场景的内容时：

```
用户: "之前那个登录页，按钮改成圆角"

AI 的处理路径：
  - 上下文 (session_history)：只有新场景的对话 → 不知道"登录页"
  - 记忆注入 (P4)：场景1压缩后的记忆 → "用户在开发登录页面，使用了 React"
  - RAG (P3)：可能检索到相关笔记 → 补充细节
  → AI 通过记忆知道登录页的存在，可以回答
```

上下文优先级 P6 最低会被裁剪，记忆 P4 更高不会被轻易砍掉——跨场景信息通过记忆而不是上下文来传递。

---

## 五、前端改动

### 5.1 `useChat.tsx`

新增消息类型 `divider`：
```typescript
interface ChatMessage {
  // ...existing fields
  scene?: number      // 场景编号（仅 divider 消息使用）
}
```

新增 action `NEW_SCENE`：
```typescript
case 'NEW_SCENE': {
  return {
    ...state,
    messages: [
      ...state.messages,
      {
        id: nextId(),
        role: 'divider' as const,
        content: `场景 ${state.sceneCount + 1} · ${new Date().toLocaleString('zh-CN')}`,
        timestamp: Date.now(),
        scene: state.sceneCount + 1,
      },
    ],
    sceneCount: state.sceneCount + 1,
  }
}
```

State 新增字段：
```typescript
interface ChatState {
  messages: ChatMessage[]
  streaming: boolean
  error: string | null
  contextInfo: ContextBudgetInfo | null
  sceneCount: number          // 新增
}
```

修改 `RESET` action：
- 删除 `RESET`（不再需要清空消息）
- 或被 `NEW_SCENE` 取代，保留向后兼容

`resetChat` → 重命名为 `newScene`：
```typescript
const newScene = useCallback(() => {
  if (wsRef.current?.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: 'new_scene' }))
  }
  dispatch({ type: 'NEW_SCENE' })
  convIdRef.current = ''
}, [])
```

返回值重命名：
```typescript
return {
  ...,
  newScene: ctx.newScene,      // 替代 resetChat
  resetChat: ctx.resetChat,    // 保留兼容
}
```

### 5.2 `ChatPage.tsx`

新增「新场景」按钮：
- 放置在输入区域，与发送按钮同行
- 图标：`Plus` 或 `RefreshCw`
- 流式中禁用（`disabled={streaming}`）
- 无消息时隐藏或禁用

移除旧的 `resetChat` 按钮（如果有）。

### 5.3 `ChatMessage.tsx`

新增 `role === 'divider'` 渲染：
```tsx
if (role === 'divider') {
  return (
    <div className="flex items-center gap-3 py-3">
      <div className="flex-1 h-px bg-border" />
      <span className="text-xs text-muted-foreground shrink-0">{content}</span>
      <div className="flex-1 h-px bg-border" />
    </div>
  )
}
```

---

## 六、后端改动

### 6.1 `chat_ws.py`

新增消息类型处理 `new_scene`：
```python
if msg_type == "new_scene":
    # 1. 全量压缩当前 session_history
    if session_history:
        asyncio.create_task(_compact_current_scene(
            session_history=list(session_history),
            model_config=model_config or get_current_model_config(),
            role_name=current_role,
        ))
    
    # 2. 清空上下文
    session_history.clear()
    memory_char_counter = 0
    memory_msg_counter = 0
    
    # 3. 生成新 conv_id
    new_conv_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    await ws.send_json({
        "type": "conv_id",
        "id": new_conv_id,
    })
    continue
```

全量压缩函数：
```python
async def _compact_current_scene(
    session_history: list[dict],
    model_config: dict,
    role_name: str,
):
    """场景切换时全量压缩（非 window 限制）"""
    try:
        compact_model = select_model_for_task("memory_compact", model_config)
        
        # 全量文本（不限制 window）
        conv_text = "\n".join(
            f"[{m['role']}]: {str(m.get('content', ''))[:300]}"
            for m in session_history
            if m.get('role') in ('user', 'assistant')
        )
        
        prompt = (
            "你是一个场景记忆归档器。以下是一段完整对话场景的全部内容。\n\n"
            "请提取：\n"
            "1. 用户的核心目标/任务\n"
            "2. 已完成的进度和关键决策\n"
            "3. 值得跨场景记住的用户偏好\n"
            "4. 技术细节（如果涉及代码/配置）\n\n"
            "用要点形式输出，每点一行。不要包含闲聊。\n\n"
            f"{conv_text}\n\n"
            "场景归档："
        )
        
        summary = await simple_completion(
            model_config=compact_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
        )
        
        if summary and summary.strip():
            from pathlib import Path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = NOTES_DIR / f"scene_compact_{timestamp}.md"
            path.write_text(
                f"# 场景记忆归档 {timestamp}\n"
                f"角色: {role_name}\n\n---\n\n{summary}",
                encoding="utf-8"
            )
    except Exception:
        pass
```

### 6.2 `routers/memory.py`

`list_notes()` 已支持展示 `scene_compact_*` 文件（glob `*.md` 会匹配）。

---

## 七、改动清单

| 文件 | 改动 |
|---|---|
| `frontend/src/hooks/useChat.tsx` | `NEW_SCENE` action + `sceneCount` 状态 + `newScene()` 方法 |
| `frontend/src/pages/ChatPage.tsx` | 新场景按钮 + 接收 `newScene` |
| `frontend/src/components/ChatMessage.tsx` | `divider` 角色渲染 |
| `backend/chat_ws.py` | `new_scene` 消息处理 + 全量压缩函数 |

不改动：`memory.py`、`chat_history.py`、`config.py`、`model.json`。

---

## 八、不变更的部分

- `_trim_history()` 继续按字符数裁剪会话历史（上下文层）
- 定时压缩继续按计数器触发（记忆层，保留双触发器）
- ContextBudget 继续统筹注入内容（预算层）
- `load_memory_for_inject()` 继续按预算注入（注入层）

场景压缩产出 `scene_compact_*.md`，与定时压缩的 `auto_compact_*.md` 共存，合并时一起处理。

---

## 九、验证清单

1. 发几条消息 → 点「新场景」→ 气泡保留，出现分隔线
2. 新场景中发消息 → AI 上下文是全新的（不记得之前对话中的临时细节）
3. 新场景中提及之前场景的核心内容 → AI 通过记忆注入可以回想
4. streaming 中点「新场景」→ 按钮禁用，无法操作
5. 无对话时点「新场景」→ 按钮禁用或无效
6. 检查 `memory/project-notes/` 下是否生成 `scene_compact_*.md`
7. 多次切场景 → 多条分隔线，场景编号递增

---

> 本内容由 Claude Code 生成。
