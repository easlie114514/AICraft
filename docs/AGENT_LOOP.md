# AICraft Agent 循环设计文档

> 本文档定义 AICraft 的核心——Agent 工具调用循环的实现规范

## 一、什么是 Agent 循环

AICraft 目前的状态：LLM 只能"说话"，不能"做事"。
Agent 循环就是让 LLM 能调用 MCP 工具、执行操作、拿到结果后继续回复。

```
用户输入 → 拼装上下文 → 调 LLM
                            ↓
                    LLM 返回 tool_call？
                      ↙          ↘
                   是              否
                    ↓              ↓
            执行 MCP 工具      返回最终回复给用户
                    ↓
            工具结果回传 LLM
                    ↓
            LLM 继续回复（可能再次 tool_call）
                    ↓
            循环直到 LLM 不再调工具
```

## 二、litellm 工具调用格式

### 2.1 注册工具

把已开启的 MCP 工具转换为 litellm 的 tools 格式：

```python
def build_tools_for_llm(mcp_tools: list[dict]) -> list[dict]:
    """把 MCP 工具列表转为 litellm function calling 格式"""
    tools = []
    for tool in mcp_tools:
        tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],           # 如 "search_issues"
                "description": tool["description"],  # 工具描述
                "parameters": tool["inputSchema"],    # JSON Schema 格式
            }
        })
    return tools
```

### 2.2 发送请求

```python
import litellm

response = litellm.completion(
    model="deepseek/deepseek-chat",
    messages=messages,        # 包含 system prompt + 历史对话 + RAG检索结果
    tools=tools,              # MCP 工具列表（可能为空）
    stream=True,              # 流式输出
)
```

### 2.3 解析 tool_call

```python
# 流式模式下收集 tool_call
tool_calls = []
tool_call_deltas = {}

for chunk in response:
    delta = chunk.choices[0].delta
    
    if delta.content:
        # 普通文本，流式输出到 UI
        yield {"type": "text", "content": delta.content}
    
    if delta.tool_calls:
        for tc in delta.tool_calls:
            idx = tc.index
            if idx not in tool_call_deltas:
                tool_call_deltas[idx] = {
                    "id": tc.id,
                    "name": "",
                    "arguments": ""
                }
            if tc.function.name:
                tool_call_deltas[idx]["name"] += tc.function.name
            if tc.function.arguments:
                tool_call_deltas[idx]["arguments"] += tc.function.arguments

tool_calls = list(tool_call_deltas.values())
```

### 2.4 执行工具并回传

```python
if tool_calls:
    # 1. 把 assistant 的 tool_call 消息加入历史
    messages.append({
        "role": "assistant",
        "tool_calls": tool_calls
    })
    
    # 2. 逐个执行工具
    for tc in tool_calls:
        tool_name = tc["name"]
        tool_args = json.loads(tc["arguments"])
        
        # 在 UI 显示工具调用状态
        yield {"type": "tool_call", "name": tool_name, "args": tool_args}
        
        # 执行 MCP 工具调用
        result = await execute_mcp_tool(tool_name, tool_args)
        
        # 在 UI 显示工具结果
        yield {"type": "tool_result", "name": tool_name, "result": result}
        
        # 3. 把工具结果加入历史
        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": str(result)
        })
    
    # 4. 再次调 LLM，让它基于工具结果回复
    # 递归或循环回到 2.2
```

## 三、完整循环实现

```python
async def agent_loop(messages: list[dict], tools: list[dict], max_rounds: int = 10):
    """
    Agent 主循环
    - messages: 完整对话历史（含 system prompt）
    - tools: MCP 工具列表（litellm 格式）
    - max_rounds: 最大工具调用轮次，防止无限循环
    """
    for round_num in range(max_rounds):
        # 调用 LLM
        response = litellm.completion(
            model=current_model,
            messages=messages,
            tools=tools if tools else None,
            stream=True,
        )
        
        # 收集流式输出
        full_text = ""
        tool_call_deltas = {}
        
        for chunk in response:
            delta = chunk.choices[0].delta
            
            if delta.content:
                full_text += delta.content
                yield {"type": "text", "content": delta.content}
            
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_call_deltas:
                        tool_call_deltas[idx] = {
                            "id": tc.id or "",
                            "name": "",
                            "arguments": ""
                        }
                    if tc.function and tc.function.name:
                        tool_call_deltas[idx]["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_call_deltas[idx]["arguments"] += tc.function.arguments
        
        # 没有工具调用 → 循环结束
        if not tool_call_deltas:
            # 把 assistant 回复加入历史
            messages.append({"role": "assistant", "content": full_text})
            break
        
        # 有工具调用 → 执行
        tool_calls_list = list(tool_call_deltas.values())
        
        # 补全 tool_call_id（某些模型流式返回时 id 可能为空）
        for i, tc in enumerate(tool_calls_list):
            if not tc["id"]:
                tc["id"] = f"call_{round_num}_{i}"
        
        # assistant 消息（含 tool_calls）
        messages.append({
            "role": "assistant",
            "content": full_text or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"]
                    }
                }
                for tc in tool_calls_list
            ]
        })
        
        # 逐个执行工具
        for tc in tool_calls_list:
            tool_name = tc["name"]
            try:
                tool_args = json.loads(tc["arguments"])
            except json.JSONDecodeError:
                tool_args = {}
            
            yield {"type": "tool_call", "name": tool_name, "args": tool_args}
            
            try:
                result = await execute_mcp_tool(tool_name, tool_args)
            except Exception as e:
                result = f"工具执行失败: {str(e)}"
            
            yield {"type": "tool_result", "name": tool_name, "result": result}
            
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(result)
            })
        
        # 继续下一轮循环，让 LLM 基于工具结果回复
    
    # 超过最大轮次
    if round_num >= max_rounds - 1:
        yield {"type": "text", "content": "\n\n[已达到最大工具调用轮次，停止执行]"}
```

## 四、MCP 工具执行器

```python
async def execute_mcp_tool(tool_name: str, tool_args: dict) -> str:
    """执行 MCP 工具调用"""
    # 从已连接的 MCP 服务器中找到拥有该工具的服务器
    for server_name, session in active_mcp_sessions.items():
        tools = await session.list_tools()
        tool_names = [t.name for t in tools.tools]
        if tool_name in tool_names:
            result = await session.call_tool(tool_name, tool_args)
            # 提取文本结果
            if result.content:
                return "\n".join(
                    c.text for c in result.content 
                    if hasattr(c, 'text')
                )
            return str(result)
    
    return f"未找到工具: {tool_name}"
```

## 五、上下文拼装

每次用户发消息时，按以下顺序拼装 messages：

```python
def build_messages(user_input: str, history: list[dict]) -> list[dict]:
    messages = []
    
    # 1. System prompt（角色 + Skill 描述）
    system_parts = []
    
    # 角色
    if current_role:
        system_parts.append(current_role_content)
    
    # Skill
    for skill in enabled_skills:
        system_parts.append(f"[Skill: {skill.name}]\n{skill.description}")
    
    # RAG 检索结果
    if rag_enabled:
        rag_results = rag_engine.search(user_input, top_k=3)
        if rag_results:
            system_parts.append("[相关知识]\n" + "\n".join(rag_results))
    
    # 记忆检索结果
    if memory_enabled:
        memory_results = memory_manager.search_memory(user_input, top_k=3)
        if memory_results:
            system_parts.append("[相关记忆]\n" + "\n".join(memory_results))
    
    messages.append({
        "role": "system",
        "content": "\n\n".join(system_parts)
    })
    
    # 2. 历史对话（裁剪到最近 N 轮）
    max_history_rounds = 20
    trimmed = trim_history(history, max_history_rounds)
    messages.extend(trimmed)
    
    # 3. 当前用户输入
    messages.append({"role": "user", "content": user_input})
    
    return messages
```

## 六、UI 集成

### 6.1 对话页显示工具调用

在聊天气泡中展示工具调用过程：

```
用户: 帮我查一下 Jira 上 P0 级别的 bug 有多少

AI: 我来帮你查一下...
    🔧 调用工具: search_issues(query="priority=P0")
    ✅ 返回结果: 共 5 条 P0 级别 bug
    
    当前 P0 级别 bug 共 5 条，分别是：
    1. BUG-1234: 登录页面白屏
    2. BUG-1235: 支付接口超时
    ...
```

### 6.2 实现方式

在 Flet 的聊天区域中，工具调用用特殊样式的控件展示：

```python
# 工具调用中
yield {"type": "tool_call", "name": "search_issues", "args": {"query": "priority=P0"}}
# → 在聊天区添加一个带 loading 动画的工具调用卡片

# 工具结果
yield {"type": "tool_result", "name": "search_issues", "result": "共 5 条..."}
# → 更新卡片状态为完成，显示结果摘要

# 普通文本
yield {"type": "text", "content": "当前 P0 级别 bug 共 5 条..."}
# → 正常的 AI 回复气泡
```

## 七、安全与限制

1. **max_rounds = 10**：防止 LLM 陷入无限工具调用循环
2. **工具执行超时**：单个工具调用最多等 30 秒
3. **用户确认**（可选）：高风险操作前弹窗让用户确认
4. **错误处理**：工具调用失败不影响循环，把错误信息回传 LLM 让它换策略

## 八、注意事项

- 不同模型对 function calling 的支持程度不同，DeepSeek 和 OpenAI 系列支持最好
- 流式模式下 tool_call 的拼接比较复杂，需要按 index 累加 delta
- tool_call_id 必须跟 tool 消息的 tool_call_id 一一对应
- 如果没有开启任何 MCP，tools 参数传 None，LLM 就不会尝试调工具
- Skill 不走工具调用，而是注入 system prompt 让 LLM 理解技能描述
