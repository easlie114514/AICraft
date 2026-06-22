---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_Thinking_Feature.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782092735584
    ReservedCode2: ""
---
# AICraft Thinking 功能实现文档

## 1. 功能概述

### 用户需求
- 对话页面新增 **Thinking 开关**（默认关闭）
- 开启后，AI 回答先输出思考过程（thinking），思考完成后再输出最终内容
- Thinking 内容自动折叠，用户可点击展开按钮查看
- 优先支持 DeepSeek `reasoning_content`，其次支持 Claude `thinking` block

### 交互流程
```
用户发送消息
  → 后端流式返回 thinking 增量
    → 前端实时渲染 thinking 区域（带闪烁动画，表示正在思考）
  → thinking 结束
    → 前端折叠 thinking 区域，显示"已思考 X 秒"摘要
    → 后端继续流式返回正式回复
  → 正式回复完成
    → 用户可点击 thinking 折叠区域展开查看完整思考过程
```

---

## 2. 技术分析

### 2.1 DeepSeek reasoning_content

DeepSeek V3/V4 在流式响应中，`delta` 对象包含两个文本字段：
- `delta.reasoning_content`：思考过程（流式增量）
- `delta.content`：正式回复（流式增量）

时序保证：`reasoning_content` 一定在 `content` 之前完成输出。

litellm 兼容性：litellm 的 `acompletion` 流式返回中，`chunk.choices[0].delta` 会原样透传 `reasoning_content` 字段。

```python
# DeepSeek 流式 chunk 示例
chunk.choices[0].delta.reasoning_content = "让我想想..."  # 思考增量
chunk.choices[0].delta.content = "答案是..."              # 正式回复增量
```

### 2.2 Claude thinking block

Claude 的 extended thinking 通过 `thinking` 类型的 content block 实现：

```python
# Claude 流式事件序列
# 1. content_block_start: type="thinking"
# 2. content_block_delta: type="thinking_delta", thinking="让我分析..."
# 3. content_block_stop
# 4. content_block_start: type="text"
# 5. content_block_delta: type="text_delta", text="答案是..."
# 6. content_block_stop
```

litellm 兼容性：litellm 将 Claude 的 thinking_delta 映射到 `delta.reasoning_content`，与 DeepSeek 统一。但需要确认当前版本是否已支持此映射。

**统一方案**：后端统一处理 `delta.reasoning_content`，无论底层模型是 DeepSeek 还是 Claude，都走同一条代码路径。

### 2.3 litellm 当前行为验证

需要确认的关键点：
- litellm 是否将 Claude 的 `thinking_delta` 映射到 `delta.reasoning_content`
- 如果未映射，需要在 `agent_loop.py` 中手动处理

建议在实际编码前，用以下命令快速验证：
```python
import litellm
# 查看 litellm 版本
print(litellm.__version__)
# 若版本 < 1.60，可能不支持 Claude thinking 映射，需升级或手动处理
```

---

## 3. WebSocket 协议扩展

### 3.1 新增事件类型

在现有 WebSocket 事件基础上，新增两个 thinking 相关事件：

```json
// 思考增量（流式，可能触发多次）
{
  "type": "thinking",
  "content": "让我分析一下这个问题..."
}

// 思考结束（一次性）
{
  "type": "thinking_end",
  "duration_ms": 3500
}
```

### 3.2 完整事件时序

```
客户端 → 服务端: {"type": "message", "content": "...", "toggles": {"thinking": true, ...}}
服务端 → 客户端: {"type": "thinking", "content": "正在思考"}        ← 可多次
服务端 → 客户端: {"type": "thinking", "content": "分析中..."}      ← 可多次
服务端 → 客户端: {"type": "thinking_end", "duration_ms": 3500}    ← 一次性
服务端 → 客户端: {"type": "text", "content": "答案"}              ← 正式回复，可多次
服务端 → 客户端: {"type": "done"}
```

### 3.3 请求参数扩展

`message` 事件的 `toggles` 字段新增 `thinking`：

```json
{
  "type": "message",
  "content": "用户输入",
  "model_id": "deepseek/deepseek-v4-pro",
  "role": "通用助手",
  "toggles": {
    "rag": false,
    "memory": true,
    "thinking": true    // ← 新增
  }
}
```

---

## 4. 后端改动

### 4.1 agent_loop.py — 核心改动

在流式 chunk 处理循环中，新增 `reasoning_content` 检测：

```python
# 当前代码（agent_loop.py 约第 70 行）
async for chunk in response:
    delta = chunk.choices[0].delta

    # 文本增量 → 实时 yield 给 UI
    if delta.content:
        full_text += delta.content
        yield {"type": "text", "content": delta.content}

    # 工具调用增量 ...
```

**改为：**

```python
# 新增 thinking 状态追踪
thinking_start_time: float | None = None
full_thinking = ""

async for chunk in response:
    delta = chunk.choices[0].delta

    # ── Thinking 增量（reasoning_content）──
    reasoning = getattr(delta, 'reasoning_content', None) or getattr(delta, 'thinking', None)
    if reasoning:
        if thinking_start_time is None:
            thinking_start_time = time.time()
        full_thinking += reasoning
        yield {"type": "thinking", "content": reasoning}

    # ── 文本增量 → 实时 yield 给 UI ──
    if delta.content:
        # 如果之前有 thinking，在首次收到 content 时发送 thinking_end
        if thinking_start_time is not None:
            duration_ms = int((time.time() - thinking_start_time) * 1000)
            yield {"type": "thinking_end", "duration_ms": duration_ms}
            thinking_start_time = None
        full_text += delta.content
        yield {"type": "text", "content": delta.content}

    # ── 工具调用增量（不变）──
    if delta.tool_calls:
        ...
```

关键点：
- `reasoning_content` 和 `thinking` 两种属性名都检测，兼容 DeepSeek 和 Claude
- `thinking_end` 在首次收到 `content` 时自动触发，不需要额外判断
- `thinking_start_time` 用 `time.time()` 追踪思考时长

### 4.2 chat_ws.py — 透传 thinking 开关

在 `msg_type == "message"` 处理中：

```python
toggles = data.get("toggles", {})
# 现有: rag, memory
# 新增: thinking
thinking_enabled = toggles.get("thinking", False)
```

将 `thinking_enabled` 传入 `agent_loop`。当 `thinking_enabled = False` 时，即使模型返回了 `reasoning_content`，也应忽略（不 yield thinking 事件）：

```python
async for event in agent_loop(
    messages=messages,
    tools=all_tools,
    model_config=model_config,
    mcp_manager=deps.mcp_manager,
    thinking_enabled=thinking_enabled,  # ← 新增参数
):
    await ws.send_json(event)
```

### 4.3 agent_loop 函数签名更新

```python
async def agent_loop(
    messages: list[dict],
    tools: list[dict] | None,
    model_config: dict | None = None,
    mcp_manager: Any | None = None,
    max_rounds: int = 10,
    thinking_enabled: bool = False,  # ← 新增
) -> AsyncGenerator[dict[str, Any], None]:
```

### 4.4 DeepSeek 特殊处理：启用 reasoning

DeepSeek 需要在请求参数中显式启用推理：

```python
# 在 _build_llm_kwargs 中
if thinking_enabled and model_config.get("provider", "") == "deepseek":
    # DeepSeek 需要额外参数启用推理
    # 方式1: 在消息中添加触发词（不推荐，不稳定）
    # 方式2: 使用 litellm 的 thinking 参数（推荐）
    kwargs["thinking"] = {"type": "enabled", "budget_tokens": 10000}
```

注意：具体参数取决于 DeepSeek API 和 litellm 的最新支持情况，编码时需查阅最新文档。

Claude 的 extended thinking 需要：
```python
if thinking_enabled and "claude" in model_config.get("model_id", "").lower():
    kwargs["thinking"] = {"type": "enabled", "budget_tokens": 10000}
```

### 4.5 llm.py — 无需改动

`llm.py` 中的 `chat_completion` 函数当前未被 `agent_loop.py` 使用（agent_loop 直接调用 litellm），因此不需要修改。

如果后续重构将 LLM 调用统一回 `llm.py`，则需要在其中也添加 `reasoning_content` 的处理。

---

## 5. 前端改动

### 5.1 useChat.tsx — 类型与 Reducer 扩展

#### 类型扩展

```typescript
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'tool_call' | 'tool_result' | 'system' | 'inject'
  content: string
  timestamp: number
  toolName?: string
  toolArgs?: Record<string, unknown>
  toolResult?: string
  // ← 新增 thinking 字段
  thinking?: string        // 思考内容全文
  thinkingDuration?: number // 思考耗时（ms）
}
```

#### Reducer 新增 Action

```typescript
type ChatAction =
  | ... // 现有 actions
  | { type: 'APPEND_THINKING'; content: string }
  | { type: 'END_THINKING'; durationMs: number }
```

#### Reducer 处理逻辑

```typescript
case 'APPEND_THINKING': {
  const msgs = [...state.messages]
  const last = msgs[msgs.length - 1]
  // 如果最后一条是 assistant 消息且正在 thinking，追加到其 thinking 字段
  if (last && last.role === 'assistant' && last.thinking !== undefined) {
    msgs[msgs.length - 1] = {
      ...last,
      thinking: last.thinking + action.content,
    }
  } else {
    // 新建一条 assistant 消息，只有 thinking，content 为空
    msgs.push({
      id: nextId(),
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      thinking: action.content,
    })
  }
  return { ...state, messages: msgs }
}

case 'END_THINKING': {
  const msgs = [...state.messages]
  const last = msgs[msgs.length - 1]
  if (last && last.role === 'assistant' && last.thinking !== undefined) {
    msgs[msgs.length - 1] = {
      ...last,
      thinkingDuration: action.durationMs,
    }
  }
  return { ...state, messages: msgs }
}
```

#### WebSocket 消息处理

```typescript
ws.onmessage = (e) => {
  try {
    const data = JSON.parse(e.data)
    switch (data.type) {
      case 'thinking':
        dispatch({ type: 'APPEND_THINKING', content: data.content })
        break
      case 'thinking_end':
        dispatch({ type: 'END_THINKING', durationMs: data.duration_ms })
        break
      case 'text':
        dispatch({ type: 'APPEND_TEXT', content: data.content })
        break
      // ... 其余不变
    }
  } catch {}
}
```

#### toggles 类型扩展

sendMessage 中的 toggles 类型新增 thinking：

```typescript
sendMessage: (
  content: string,
  modelId: string,
  role: string,
  toggles: Record<string, boolean>  // 已包含 thinking
) => void
```

### 5.2 ChatPage.tsx — 新增 Thinking 开关

在现有 toggles 区域（RAG、记忆）旁边新增 Thinking 开关：

```tsx
<div className="flex items-center gap-6">
  {/* 现有 RAG 开关 */}
  <div className="flex items-center gap-2">
    <Switch id="toggle-rag" ... />
    <Label htmlFor="toggle-rag" ...>RAG检索</Label>
  </div>

  {/* 现有 记忆 开关 */}
  <div className="flex items-center gap-2">
    <Switch id="toggle-memory" ... />
    <Label htmlFor="toggle-memory" ...>记忆注入</Label>
  </div>

  {/* ← 新增 Thinking 开关 */}
  <div className="flex items-center gap-2">
    <Switch
      id="toggle-thinking"
      className="rounded-xl"
      checked={toggles.thinking}
      onCheckedChange={(v) => setToggles({ ...toggles, thinking: v })}
    />
    <Label htmlFor="toggle-thinking" className="text-xs text-muted-foreground cursor-pointer">
      深度思考
    </Label>
  </div>
</div>
```

toggles 初始值更新：

```typescript
const [toggles, setToggles] = useState({ rag: false, memory: true, thinking: false })
//                                                                    ^^^^^^^^ 新增，默认关闭
```

### 5.3 ChatMessage.tsx — Thinking 折叠区域

参考现有 `ToolCallCard.tsx` 的 `Collapsible` 模式，在 assistant 消息气泡内添加 thinking 折叠区域：

```tsx
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Brain, ChevronDown } from 'lucide-react'

export default function ChatMessage({ message }: Props) {
  const { role, content, timestamp, thinking, thinkingDuration } = message
  const [thinkingOpen, setThinkingOpen] = useState(false)
  const isThinkingStreaming = thinking !== undefined && thinkingDuration === undefined
  // thinking 存在但 thinkingDuration 还没设置 = 正在思考中

  // ... system / tool_call 处理不变

  const isUser = role === 'user'

  return (
    <div className={cn('flex flex-col py-1.5', isUser ? 'items-end' : 'items-start')}>
      {/* Timestamp */}
      <div className={cn('px-1 mb-0.5', isUser ? 'text-right' : 'text-left')}>
        <span className="text-[10px] text-muted-foreground/60">{formatTime(timestamp)}</span>
      </div>

      {/* Bubble */}
      <div className={cn(
        'max-w-[85%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed',
        isUser ? 'bg-primary/10 text-foreground' : 'bg-muted text-foreground'
      )}>
        {isUser ? (
          <p className="whitespace-pre-wrap break-words">{content}</p>
        ) : (
          <>
            {/* Thinking 折叠区域 */}
            {thinking && (
              <Collapsible open={thinkingOpen} onOpenChange={setThinkingOpen}>
                <CollapsibleTrigger className="flex items-center gap-1.5 w-full mb-2 text-xs text-muted-foreground hover:text-foreground transition-colors">
                  <Brain className="h-3.5 w-3.5" />
                  {isThinkingStreaming ? (
                    <span className="animate-pulse">正在思考...</span>
                  ) : (
                    <span>已思考 {(thinkingDuration! / 1000).toFixed(1)}s</span>
                  )}
                  <ChevronDown className={cn(
                    "h-3.5 w-3.5 transition-transform",
                    thinkingOpen && "rotate-180"
                  )} />
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <div className="text-xs text-muted-foreground bg-muted/50 p-2.5 rounded-lg mb-2 max-h-64 overflow-auto border border-border/50">
                    <MarkdownRenderer content={thinking} />
                  </div>
                </CollapsibleContent>
              </Collapsible>
            )}

            {/* 正式回复 */}
            {content && <MarkdownRenderer content={content} />}
          </>
        )}
      </div>
    </div>
  )
}
```

关键设计点：
- **正在思考时**：显示"正在思考..."带脉冲动画，折叠区域默认收起
- **思考完成后**：显示"已思考 X.Xs"，折叠区域默认收起
- **用户主动展开**：点击触发器可展开查看完整思考过程
- **思考中内容实时更新**：`APPEND_THINKING` action 持续更新 `thinking` 字段，但折叠区域保持收起
- **样式**：thinking 区域用更淡的背景色和更小的字号，与正式回复视觉区分

### 5.4 思考中的实时展示优化

用户可能想在思考过程中就看到 thinking 内容（而不是等完成后再展开）。建议增加一个交互：**点击"正在思考..."时展开，后续增量内容实时流入**。

实现方式：`isThinkingStreaming` 为 true 时，如果用户手动展开，后续的 `APPEND_THINKING` 会在展开状态下实时追加内容。这天然支持——因为 `thinking` 字段在 reducer 中持续更新，展开的 CollapsibleContent 自然显示最新内容。

---

## 6. 数据流全图

```
┌─────────────────────────────────────────────────────────┐
│ Frontend                                                │
│                                                         │
│  ChatPage                                               │
│  ├─ toggles: { thinking: true } ──────────────────┐    │
│  │                                                 │    │
│  │  WebSocket send:                                │    │
│  │  { type: "message", toggles: { thinking: true } }    │
│  │                                                       │
│  │  WebSocket receive:                                   │
│  │  ├─ { type: "thinking", content: "..." }              │
│  │  │   → dispatch(APPEND_THINKING)                      │
│  │  │   → ChatMessage.thinking 实时更新                  │
│  │  │                                                    │
│  │  ├─ { type: "thinking_end", duration_ms: 3500 }       │
│  │  │   → dispatch(END_THINKING)                         │
│  │  │   → ChatMessage.thinkingDuration = 3500            │
│  │  │   → 折叠区域收起，显示"已思考 3.5s"               │
│  │  │                                                    │
│  │  ├─ { type: "text", content: "..." }                  │
│  │  │   → dispatch(APPEND_TEXT)                           │
│  │  │   → ChatMessage.content 正式回复                    │
│  │  │                                                    │
│  │  └─ { type: "done" }                                  │
│  └───────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│ Backend                                                 │
│                                                         │
│  chat_ws.py                                             │
│  ├─ 接收 toggles.thinking                               │
│  └─ 传入 agent_loop(thinking_enabled=True)              │
│                                                         │
│  agent_loop.py                                          │
│  ├─ 检测 delta.reasoning_content / delta.thinking       │
│  │   ├─ thinking_enabled=True → yield thinking 事件     │
│  │   └─ thinking_enabled=False → 忽略                   │
│  ├─ 首次收到 delta.content 时 → yield thinking_end      │
│  └─ 继续正常 text 流式输出                               │
│                                                         │
│  litellm.acompletion()                                  │
│  ├─ DeepSeek: 透传 reasoning_content                    │
│  └─ Claude: 映射 thinking_delta → reasoning_content     │
└─────────────────────────────────────────────────────────┘
```

---

## 7. 边界情况处理

### 7.1 模型不支持 thinking
- 不是所有模型都返回 `reasoning_content`
- 如果模型不返回，前端不会收到 `thinking` 事件，thinking 区域不显示
- 开关打开但模型不支持 = 无害，等同于没开

### 7.2 工具调用期间的 thinking
- DeepSeek 的 reasoning_content 只在最终回复前出现
- 如果 LLM 在工具调用前思考，thinking 事件会在 `tool_call` 之前发出
- 需要确保 `thinking_end` 在 `tool_call` 之前发送

方案：在检测到 `delta.tool_calls` 时，如果 `thinking_start_time` 不为 None，也触发 `thinking_end`：

```python
if delta.tool_calls:
    # 如果之前有 thinking，先结束
    if thinking_start_time is not None:
        duration_ms = int((time.time() - thinking_start_time) * 1000)
        yield {"type": "thinking_end", "duration_ms": duration_ms}
        thinking_start_time = None
    # ... 原有 tool_calls 累积逻辑
```

### 7.3 多轮工具调用
- 每轮 LLM 调用可能产生独立的 thinking
- 建议只显示最后一轮的 thinking（用户最关心的是最终推理过程）
- 实现：在 agent_loop 每轮开始时重置 thinking 状态

```python
for round_num in range(max_rounds):
    # 每轮重置 thinking 状态
    thinking_start_time = None
    full_thinking = ""
    ...
```

### 7.4 thinking 内容为空
- 某些情况下模型可能返回空的 `reasoning_content`（空字符串）
- 前端判断：`thinking && thinking.trim()` 才显示折叠区域

### 7.5 停止输出时 thinking 未结束
- 用户点击停止按钮，thinking 可能还在进行中
- 前端收到 `done` 事件后，如果 `thinkingDuration` 仍为 undefined，手动设置一个估算值

```typescript
case 'SET_DONE': {
  const msgs = [...state.messages]
  const last = msgs[msgs.length - 1]
  // 如果正在 thinking 但收到 done，结束 thinking
  if (last && last.role === 'assistant' && last.thinking !== undefined && last.thinkingDuration === undefined) {
    msgs[msgs.length - 1] = { ...last, thinkingDuration: 0 }
  }
  return { ...state, messages: msgs, streaming: false }
}
```

---

## 8. 实现清单

### 后端（3 个文件）

| 文件 | 改动 | 优先级 |
|------|------|--------|
| `src/core/agent_loop.py` | 新增 `thinking_enabled` 参数；流式处理 `reasoning_content`；yield `thinking` / `thinking_end` 事件 | P0 |
| `backend/chat_ws.py` | 透传 `toggles.thinking`；传参给 `agent_loop` | P0 |
| `src/core/llm.py` | **本次不改**，后续统一 LLM 调用时再改 | P2 |

### 前端（3 个文件）

| 文件 | 改动 | 优先级 |
|------|------|--------|
| `frontend/src/hooks/useChat.tsx` | 新增 `APPEND_THINKING` / `END_THINKING` action；ChatMessage 类型扩展 thinking 字段；WebSocket 处理新事件 | P0 |
| `frontend/src/pages/ChatPage.tsx` | 新增 Thinking 开关；toggles 初始值添加 `thinking: false` | P0 |
| `frontend/src/components/ChatMessage.tsx` | Thinking 折叠区域渲染（Collapsible）；正在思考/已思考两种状态；脉冲动画 | P0 |

### 不需要改动的文件

- `frontend/src/components/ToolCallCard.tsx` — 不变
- `frontend/src/components/MarkdownRenderer.tsx` — 不变
- `frontend/src/components/ui/collapsible.tsx` — 已存在，直接使用
- `src/utils/config.py` — 不变（thinking 开关是前端状态，不需要持久化）

---

## 9. 验证方案

### 基本验证
1. 打开 Thinking 开关，使用 DeepSeek 模型发送问题
2. 确认：先出现"正在思考..."带脉冲动画
3. 确认：thinking 完成后折叠，显示"已思考 X.Xs"
4. 确认：正式回复正常流式输出
5. 点击折叠区域，确认可展开查看完整思考过程

### 边界验证
1. **关闭 Thinking 开关**：确认不显示 thinking 区域
2. **不支持 thinking 的模型**：确认无害，等同于没开
3. **工具调用场景**：确认 thinking_end 在 tool_call 之前
4. **停止输出**：确认 thinking 状态正确结束
5. **长 thinking 内容**：确认折叠区域有滚动条

### Claude thinking 验证（如果有 Claude API Key）
1. 切换到 Claude 模型
2. 开启 Thinking
3. 确认 thinking 内容正确捕获和展示

---

## 10. 后续优化（不在本次范围）

- **Thinking token 计数**：在 `thinking_end` 中附带 thinking 消耗的 token 数
- **Thinking 预算控制**：允许用户设置 thinking token 上限
- **Thinking 内容持久化**：保存到对话历史时包含 thinking 字段
- **Thinking 统计面板**：展示本次会话的 thinking 总耗时和 token 消耗

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
