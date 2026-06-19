---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_Agent_Constraint_v7.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1781770754711
    ReservedCode2: ""
---
# AICraft Agent 约束规范 v7 — 反幻觉与行为控制

> v6管「长什么样」，v7管「怎么思考」
> 基于 develop_new 分支（commit cecf702）实际代码审查后编写
> 目标：让AICraft的Agent行为可预期、不编造、不失控

---

## 一、核心原则

1. **观察优先于推理**：没有工具输出就没有结论，禁止模型凭空编造
2. **动态注入**：每次请求的system prompt和工具列表必须实时构建，禁止静态拼接
3. **失败显式传递**：工具调用失败时，错误信息必须返回模型，模型必须告知用户
4. **结构化调用**：工具调用走function calling，不走文本描述让模型自己编

---

## 二、System Prompt 构建规则

### 2.1 当前代码问题（chat_ws.py）

| 问题 | 代码位置 | 影响 |
|------|----------|------|
| 没注入当前日期 | chat_ws.py | 模型编造日期（如"2025年7月11日"） |
| Skill描述全注入 | chat_ws.py L89 `build_skill_prompt()` | 模型念出自己有哪些技能 |
| 记忆注入无约束前缀 | chat_ws.py L99-110 | 模型在回复中提及"我看到了你的笔记" |
| 历史消息可能重复 | chat_ws.py | session_history + get_recent_messages(20) 重叠 |

### 2.2 修复方案

#### 构建顺序（每次请求动态构建）

```
1. 角色设定 + 当前日期（始终注入）
2. 可用工具声明（动态：只注入已启用且已连接的工具）
3. 注入内容（RAG/记忆，按开关状态动态注入，带约束前缀）
4. 行为约束（固定尾部约束）
```

#### 角色设定

```python
# chat_ws.py 中 build_system_prompt 后追加日期
system_content = deps.role_loader.build_system_prompt(role_name or None)
system_content += f"\n\n当前日期时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}"
```

#### Skill 描述精简

```python
# 当前：把整个SKILL.md塞进去 → 模型念出来
# 修改：只注入简短描述，不注入完整SKILL.md内容

def build_skill_prompt(self) -> str:
    enabled = self.get_enabled_skills()
    if not enabled:
        return ""
    parts = ["\n\n# 可用技能\n你具备以下技能，当用户问题匹配时可以调用对应工具：\n"]
    for skill in enabled:
        # 只注入名称和简短描述，不注入完整SKILL.md
        parts.append(f"- {skill.name}：{skill.description}")
    return "\n".join(parts)
```

#### 注入内容约束前缀

```python
# RAG
if rag_results:
    system_content += (
        "\n\n[知识库检索结果 — 供参考，基于这些信息回答。"
        "如果片段中没有相关信息请如实说明，不要编造。]\n"
        + rag_text
    )

# 跨会话记忆
if cross_memories:
    system_content += (
        "\n\n[跨会话记忆 — 之前的对话片段，供参考，"
        "不要在回复中提及你看到了这些内容，自然运用即可。]\n"
        + mem_text
    )

# 项目笔记
if notes:
    system_content += (
        "\n\n[项目笔记 — 供参考，"
        "不要在回复中提及你看到了笔记，自然运用相关信息即可。]\n"
        + notes
    )
```

#### 固定尾部约束

```python
BEHAVIOR_CONSTRAINT = (
    "\n\n# 行为约束\n"
    "- 不要编造你不知道的信息，不知道就说不知道\n"
    "- 不要编造工具调用结果，只有真正执行了工具才能报告结果\n"
    "- 如果工具调用失败，如实告知用户失败原因\n"
    "- 不要在回复中提及你看到了注入的笔记、搜索结果等内容\n"
    "- 当前时间是{datetime}，不要编造日期和时间"
)
```

---

## 三、工具调用规范

### 3.1 当前代码状态（已基本正确）

- ✅ agent_loop.py：结构化function calling，流式输出
- ✅ mcp_client.py：`get_enabled_tools()` 只返回 enabled+connected 的工具
- ✅ web_search.py：已改为function calling工具定义
- ✅ 工具调用失败返回error文本

### 3.2 需要修复

#### 联网搜索不再受toggle控制

```python
# chat_ws.py 当前代码（L115）：
if toggles.get("web_search"):
    tools.append(WEB_SEARCH_TOOL)

# 修改为：始终加入搜索工具，让模型自行判断是否需要搜索
tools.append(WEB_SEARCH_TOOL)
```

同时前端 ChatPage.tsx 删掉联网搜索开关：

```tsx
// 删除 web_search 的 Switch，toggles 只保留 rag 和 memory
const [toggles, setToggles] = useState({ rag: false, memory: true })
```

#### 工具不可用时注入提示

```python
# 当没有任何可用工具时（MCP全关、无Skill工具）
if not tools:
    system_content += (
        "\n\n# 工具状态\n"
        "你当前没有任何外部工具可用，不要编造工具调用。"
        "如果需要执行操作（如读写文件、搜索等），请告知用户需要启用对应工具。"
    )
```

#### 工具调用次数限制（已实现）

- ✅ agent_loop.py `max_rounds=10`，超限输出提示
- 无需修改

---

## 四、上下文管理规范

### 4.1 当前代码状态

- ✅ 按字符数裁剪历史（`_trim_history`，默认50K）
- ✅ 记忆压缩（`compact_memory`，默认5K字符触发）
- ✅ 角色切换时提取事实摘要、重置风格
- ✅ 压缩后通知前端

### 4.2 需要修复：历史消息去重

```python
# chat_ws.py 当前代码：
# 1. memory toggle 开启时注入 get_recent_messages(20) 到 system prompt
# 2. session_history 保留了当前WS会话的完整历史
# 问题：同一段对话数据出现两次

# 修改方案：
# memory toggle 只注入「跨会话」的历史（排除当前session的对话）
# 当前session的上下文由 session_history 自然提供，不需要重复注入

if toggles.get("memory"):
    # 只注入其他会话的最近消息（排除当前session的对话）
    cross_memories = await loop.run_in_executor(None, get_recent_messages, 10)
    # 过滤掉当前session已包含的消息（按内容去重）
    session_contents = {m.get("content", "") for m in session_history if m.get("role") in ("user", "assistant")}
    unique_memories = [m for m in cross_memories if m.get("content", "") not in session_contents]
    if unique_memories:
        mem_text = "\n".join(
            f"[{m['role']}]: {m.get('content', '')[:200]}"
            for m in unique_memories[:10]
        )
        system_content += f"\n\n[跨会话记忆 — 之前其他对话的片段，供参考，不要在回复中提及。]\n{mem_text}"

    # 项目笔记（这部分不重复，可以保留）
    notes = await loop.run_in_executor(None, deps.memory_manager.load_all_notes)
    if notes:
        system_content += f"\n\n[项目笔记 — 供参考，不要在回复中提及。]\n{notes}"
```

---

## 五、开关行为定义

| 开关 | 默认状态 | 开启时 | 关闭时 |
|------|----------|--------|--------|
| 联网搜索 | — | **无开关**，web_search始终作为function calling工具可用，模型自行判断是否需要搜索 | — |
| RAG检索 | 关闭 | 优先检索知识库，片段注入system prompt（带约束前缀），模型优先基于RAG结果回答 | 不检索，模型基于自身知识回答 |
| 记忆注入 | 开启 | 注入跨会话记忆（去重后）+ 项目笔记到system prompt（带约束前缀） | 不注入任何记忆内容 |
| MCP工具 | 按配置 | 已启用且已连接的MCP工具加入tools参数 | 不注入MCP工具，模型无法调用 |
| Skill | 按配置 | 已启用Skill的名称+简短描述加入system prompt | 不注入Skill信息 |

---

## 六、Agent 循环规范

### 6.1 单次请求流程

```
1. 接收用户消息
2. 动态构建system prompt（角色+日期 + 可用工具声明 + 注入内容+约束前缀 + 行为约束）
3. 构建 messages（system + session_history + 用户消息）
4. 构建 tools 列表（MCP已连接工具 + web_search工具）
5. 调用LLM（streaming）
6. 判断返回：
   - 普通文本 → 流式推送给前端 → 结束
   - tool_call → 执行工具 → 结果返回模型 → 回到步骤5
7. 达到工具调用上限（10轮）→ 强制结束 → 告知用户
```

### 6.2 流式输出事件格式

| 事件 | 格式 | 说明 |
|------|------|------|
| 文本增量 | `{ "type": "text", "content": "增量" }` | 逐token推送 |
| 注入信息 | `{ "type": "inject_info", "items": [...] }` | RAG/记忆注入情况 |
| 工具调用 | `{ "type": "tool_call", "name": "...", "args": {...} }` | 模型发起工具调用 |
| 工具结果 | `{ "type": "tool_result", "name": "...", "result": "..." }` | 工具执行结果 |
| 完成 | `{ "type": "done" }` | 对话结束 |
| 错误 | `{ "type": "error", "content": "..." }` | 错误信息 |

### 6.3 角色切换流程

```
检测到角色切换 →
  1. 提取当前对话事实摘要（去掉旧角色语气）
  2. 清空session_history
  3. 新system prompt = 角色切换声明 + 事实摘要 + 新角色设定
  4. 通知前端切换完成
```

---

## 七、错误处理规范

| 场景 | 处理 |
|------|------|
| 模型API调用失败 | 前端显示："模型调用失败：{错误信息}" |
| 模型API超时 | 前端显示："模型响应超时，请稍后重试" |
| MCP连接断开 | 标记status="error"，从可用工具列表移除 |
| 工具调用失败 | 返回error给模型，模型告知用户 |
| 上下文压缩失败 | 保留原始消息不压缩，提示"压缩失败" |
| 未配置模型 | 前端显示："未配置模型，请先在模型页添加API配置" |
| 无可用工具 | system prompt注入"当前没有外部工具，不要编造调用" |

---

## 八、修改清单（对照 develop_new 代码）

| 优先级 | 文件 | 修改内容 |
|--------|------|----------|
| 🔴 | chat_ws.py | system_prompt追加当前日期时间 |
| 🔴 | chat_ws.py | 联网搜索始终加入tools，删掉toggles.web_search判断 |
| 🔴 | skill_loader.py | `build_skill_prompt()`只注入名称+简短描述，不注入完整SKILL.md |
| 🔴 | chat_ws.py | 注入内容加约束前缀（RAG/记忆/笔记） |
| 🔴 | chat_ws.py | system_prompt末尾追加行为约束 |
| 🟡 | chat_ws.py | 跨会话记忆去重（排除当前session已有的消息） |
| 🟡 | ChatPage.tsx | 删掉联网搜索开关，toggles改为 `{ rag: false, memory: true }` |
| 🟡 | chat_ws.py | 无可用工具时注入提示 |
| 💡 | chat_ws.py | 记忆开关默认开启（前端初始值改为true） |

---

## 九、与v6的关系

- **v6**：UI设计规范，管页面长什么样、组件怎么用、主题色是什么
- **v7**：Agent行为规范，管AI怎么思考、怎么调用工具、怎么避免幻觉
- v7的约束通过后端代码（chat_ws.py / agent_loop.py / skill_loader.py）实现
- 前端改动只有：删掉联网搜索开关、调整toggles默认值

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
