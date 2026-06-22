---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_Auto_Router.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782106832472
    ReservedCode2: ""
---
# AICraft Auto模型路由方案

> 版本：v1.0 | 日期：2026-06-22

---

## 一、功能定义

在模型选择下拉框中增加 **⚡ Auto** 选项（默认选中）。用户选择Auto时，后端根据消息内容和开关状态自动决定用Pro还是Flash，用户无需手动切换。

**核心原则**：Pro兜底，Flash只在明确简单时才用。宁可多花一点，不要答错。

---

## 二、路由规则

### 决策流程

```
用户消息 + 开关状态 → Auto路由器
  ├─ 条件1命中 → Pro
  ├─ 条件2命中 → Pro
  ├─ ...
  └─ 全部未命中（确认简单）→ Flash
```

### 规则优先级表（从高到低）

| 优先级 | 条件 | 路由 | 理由 |
|---|---|---|---|
| 1 | 深度思考开关开启 | **Pro** | Flash不支持深度推理 |
| 2 | 本次请求涉及MCP工具调用 | **Pro** | 工具调用需要准确度，Flash可能调错参数 |
| 3 | RAG检索开关开启 | **Pro** | 需要综合检索结果，要求理解力 |
| 4 | 消息含复杂任务关键词 | **Pro** | 需要推理能力 |
| 5 | 消息长度 > 300字 | **Pro** | 长消息大概率复杂任务 |
| 6 | 消息包含代码块或结构化内容 | **Pro** | 技术场景 |
| 7 | 以上全部未命中 | **Flash** | 确认是简单闲聊/短问答 |

### 复杂任务关键词列表

```python
COMPLEX_KEYWORDS = [
    # 推理分析
    "分析", "比较", "评估", "推理", "论证", "辩证",
    "为什么", "原因", "逻辑", "原理", "机制",
    # 技术开发
    "代码", "编程", "函数", "算法", "debug", "调试",
    "修复", "bug", "实现", "开发", "部署",
    "sql", "api", "json", "html", "css",
    # 写作创作
    "写一篇", "撰写", "起草", "总结", "概括",
    "翻译", "润色", "改写", "扩写",
    # 计算
    "计算", "公式", "数学", "统计",
    # 规划
    "规划", "方案", "设计", "架构",
]
```

### 简单场景判定

以下特征同时满足时才走Flash：
- 消息 ≤ 300字
- 不含复杂关键词
- 不含代码块（```或缩进4行的模式）
- 不含多问号/多问题的结构（如同时出现2个以上"？"）
- 深度思考/RAG/MCP工具均为关闭状态

---

## 三、用户反馈

Auto模式下，用户需要知道当前用了哪个模型。通过 `inject_info` 机制告知：

```json
{"type": "inject_info", "items": ["⚡ Auto路由 → DeepSeek-Flash（简单问答）"]}
```

```json
{"type": "inject_info", "items": ["⚡ Auto路由 → DeepSeek-Pro（复杂任务）"]}
```

路由原因可选显示（后续可在设置中开关详细模式）：
- `（深度思考）`
- `（工具调用）`
- `（RAG检索）`
- `（复杂任务）`
- `（简单问答）`

---

## 四、代码改动

### 4.1 `src/core/model_selector.py` — 新增Auto路由函数

在现有 `select_model_for_task()` 下方新增：

```python
import re

COMPLEX_KEYWORDS = [
    "分析", "比较", "评估", "推理", "论证", "辩证",
    "为什么", "原因", "逻辑", "原理", "机制",
    "代码", "编程", "函数", "算法", "debug", "调试",
    "修复", "bug", "实现", "开发", "部署",
    "sql", "api", "json", "html", "css",
    "写一篇", "撰写", "起草", "总结", "概括",
    "翻译", "润色", "改写", "扩写",
    "计算", "公式", "数学", "统计",
    "规划", "方案", "设计", "架构",
]

# 代码块模式
_CODE_BLOCK_PATTERN = re.compile(r"```|\n    \w", re.IGNORECASE)


def select_model_auto(
    user_message: str,
    toggles: dict,
    has_mcp_tools: bool,
    user_model_config: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Auto路由：根据消息内容和开关状态自动选择Pro/Flash

    Args:
        user_message: 用户发送的原始消息
        toggles: 开关状态 {"thinking": bool, "rag": bool, "memory": bool}
        has_mcp_tools: 当前是否有启用的MCP工具
        user_model_config: 用户当前模型配置（用于兜底）

    Returns:
        (model_config, reason) — 选中的模型配置 + 路由原因
    """
    models = get_all_model_configs()
    pro_model = None
    flash_model = None

    for m in models:
        if m.get("tier") == "pro":
            pro_model = m
        elif m.get("tier") == "flash":
            flash_model = m

    # 没有Flash模型时，全走Pro（兜底）
    if not flash_model:
        return user_model_config, "无Flash模型"

    # ── 规则1：深度思考 → Pro ──
    if toggles.get("thinking"):
        return pro_model or user_model_config, "深度思考"

    # ── 规则2：MCP工具调用 → Pro ──
    if has_mcp_tools:
        return pro_model or user_model_config, "工具调用"

    # ── 规则3：RAG检索 → Pro ──
    if toggles.get("rag"):
        return pro_model or user_model_config, "RAG检索"

    # ── 规则4：复杂关键词 → Pro ──
    msg_lower = user_message.lower()
    for kw in COMPLEX_KEYWORDS:
        if kw in msg_lower:
            return pro_model or user_model_config, "复杂任务"

    # ── 规则5：消息长度 > 300字 → Pro ──
    if len(user_message) > 300:
        return pro_model or user_model_config, "复杂任务"

    # ── 规则6：包含代码块 → Pro ──
    if _CODE_BLOCK_PATTERN.search(user_message):
        return pro_model or user_model_config, "复杂任务"

    # ── 规则7：多问题结构 → Pro ──
    if user_message.count("？") + user_message.count("?") >= 2:
        return pro_model or user_model_config, "复杂任务"

    # ── 全部未命中 → Flash（确认简单） ──
    return flash_model, "简单问答"
```

### 4.2 `backend/chat_ws.py` — 集成Auto路由

在 `model_id` 获取后、`model_config` 赋值处，增加Auto判断：

```python
# ── 获取模型配置 ──
model_config = get_model_config(model_id) if model_id else get_current_model_config()

# ── Auto路由 ──
if model_id == "auto":
    has_mcp_tools = bool(deps.mcp_manager.get_enabled_tools())
    model_config, auto_reason = select_model_auto(
        user_message=user_text,
        toggles=toggles,
        has_mcp_tools=has_mcp_tools,
        user_model_config=model_config or get_current_model_config(),
    )
    # 通知用户路由结果
    tier_name = "Pro" if model_config.get("tier") == "pro" else "Flash" if model_config.get("tier") == "flash" else ""
    await ws.send_json({
        "type": "inject_info",
        "items": [f"⚡ Auto路由 → {model_config.get('name', tier_name)}（{auto_reason}）"]
    })
```

### 4.3 `frontend/src/pages/ChatPage.tsx` — 增加Auto选项

模型下拉框第一项添加Auto：

```tsx
// 加载模型时，在列表最前面插入Auto选项
useEffect(() => {
  api.get<ModelOption[]>('/models').then((data) => {
    setModels([{ name: 'Auto', model_id: 'auto', is_current: false }, ...data])
  }).catch(() => {})
}, [])

// 默认选中Auto
useEffect(() => {
  if (models.length && !selectedModel) {
    setSelectedModel('auto')
  }
}, [models, selectedModel])
```

下拉框渲染部分对Auto项做特殊展示：

```tsx
<SelectItem key="auto" value="auto" className="text-xs">
  ⚡ Auto（智能路由）
</SelectItem>
```

### 4.4 `backend/routers/models.py` — current模型接口兼容

`PUT /models/current` 接收到 `model_id: "auto"` 时，不写入配置文件，仅作为前端标识。Auto是运行时路由，不持久化。

---

## 五、不做什么

| 不做 | 理由 |
|---|---|
| Embedding语义路由 | 维护参考向量库对小项目不划算 |
| 小模型分类器 | 需要标注数据集+训模型，个人桌面工具没必要 |
| 级联路由（Flash先答→不行再Pro） | 最坏case双倍费用，个人钱包受不了 |
| Auto路由学习/自适应 | 训练数据不足，过拟合风险大 |

---

## 六、后续可选优化

1. **路由统计面板**：记录Auto模式下Pro/Flash的使用比例，用户能看到省了多少钱
2. **自定义关键词**：允许用户在设置中添加自己的复杂关键词
3. **Auto模式白名单**：用户可指定"某些场景永远Pro/永远Flash"
4. **路由详细日志**：记录每条消息的路由决策和原因，便于调试

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
