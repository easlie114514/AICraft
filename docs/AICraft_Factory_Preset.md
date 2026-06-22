---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_Factory_Preset.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782129915810
    ReservedCode2: ""
---
# AICraft 出厂预置方案

> 基于 develop_new 分支 commit `06e595f` 核查结果编写。Claude Code 可直接按本文档操作。

---

## 一、现状核查

### 已完成的出厂预置

| 模块 | 状态 | 说明 |
|------|------|------|
| MCP 出厂注入 | ✅ 已实现 | `deps.py` 首次启动检测 `mcp_connections.json` 为空时，自动从 `config/defaults/default_mcp.json` 导入 |
| MCP 配置模板 | ✅ 已实现 | `config/defaults/default_mcp.json` 含文件管理+代码执行，`{workspace_dir}` 占位符自动替换 |
| MCP Node环境检测 | ✅ 已实现 | `src/utils/env.py` + 前端 `FACTORY_MCP_NAMES` 标记 + `✅ 环境就绪/⚠️ 需要Node.js` Badge |
| MCP 路径解析 | ✅ 已实现 | `mcp_client.py` 的 `_resolve_mcp_args()` 对 args 中的路径参数调用 `resolve_path()` |
| Skill 出厂文件 | ✅ 已有 | `skills/` 下已有：翻译助手、代码审查、写作助手、数据分析、bug-analyzer、code-reviewer、sipp-script-generator |
| RAG 出厂文件 | ✅ 已有 | `rag/使用指导/` 下已有：Agent使用手册.md、插件开发指南.md、常见问题库.md |
| RAG 路径解析 | ✅ 已实现 | `rag_engine.py` 的 `add_source()` 和 `_index_local()` 均调用 `resolve_path()`，支持相对路径 |
| 全局路径解析 | ✅ 已实现 | `config.py` 的 `resolve_path()`：相对路径以 `BASE_DIR` 为基准解析 |
| 默认角色 | ⚠️ 需优化 | 4个角色（通用助手/猫/测试工程师/混的入），但通用助手过于简陋，且缺少出厂默认角色标记 |

### 未完成的出厂预置

| 模块 | 缺失内容 |
|------|---------|
| RAG 出厂注入 | `rag/sources.json` 为空，首次启动不会自动创建出厂 RAG 数据源 |
| Skill 出厂清理 | `skills/` 下混入了个人技能（bug-analyzer、code-reviewer、sipp-script-generator）和旧版同名技能（code-reviewer vs 代码审查） |
| 角色出厂优化 | 「通用助手」内容单薄，缺少一个更专业的默认角色；无出厂默认角色标记机制 |
| 默认模型配置 | `model.json` 里默认角色硬编码为「猫」，新用户首次启动不应选「猫」 |

---

## 二、出厂预置改动清单

### 改动 1：RAG 出厂注入（对标 MCP 的 default_mcp.json 机制）

**原理**：和 MCP 一样，首次启动时检测 `rag/sources.json` 为空则自动注入出厂配置。

#### 1.1 创建 `config/defaults/default_rag.json`

```json
[
  {
    "name": "使用指导",
    "path": "rag/使用指导",
    "type": "local",
    "enabled": true
  }
]
```

> `path` 用相对路径，`rag_engine.add_source()` 内部已有 `resolve_path()` 会自动转为绝对路径。

#### 1.2 修改 `backend/deps.py` 的 `init_deps()`

在 MCP 出厂注入逻辑之后，RAG 加载之前，加入 RAG 出厂注入：

```python
def init_deps() -> AppDeps:
    global _deps

    # ── MCP ──
    mcp = MCPManager()
    mcp.load_connections()

    # 首次启动自动导入出厂 MCP 配置
    if not mcp.connections:
        defaults_file = BASE_DIR / "config" / "defaults" / "default_mcp.json"
        if defaults_file.exists():
            import json as _json
            default_data = _json.loads(defaults_file.read_text(encoding="utf-8"))
            workspace_path = str(BASE_DIR / "workspace")
            for item in default_data:
                substituted_args = [
                    arg.replace("{workspace_dir}", workspace_path)
                    for arg in item.get("args", [])
                ]
                mcp.add_connection(
                    name=item["name"],
                    conn_type=item.get("type", "stdio"),
                    host=item.get("host", ""),
                    port=item.get("port", 0),
                    url=item.get("url", ""),
                    command=item.get("command", ""),
                    args=substituted_args,
                    env=item.get("env", {}),
                )

    # ── RAG ──
    rag = RAGEngine()
    rag.load_sources()

    # 首次启动自动导入出厂 RAG 配置
    if not rag.sources:
        defaults_file = BASE_DIR / "config" / "defaults" / "default_rag.json"
        if defaults_file.exists():
            import json as _json
            default_data = _json.loads(defaults_file.read_text(encoding="utf-8"))
            for item in default_data:
                rag.add_source(
                    name=item["name"],
                    path=item["path"],  # add_source() 内部会 resolve_path
                    source_type=item.get("type", "local"),
                )

    # ── 其余不变 ──
    memory = MemoryManager()
    role = RoleLoader()
    role.scan()
    skill = SkillLoader(skill_dir=get_skills_dir())
    skill.scan()
    _deps = AppDeps(
        mcp_manager=mcp,
        rag_engine=rag,
        memory_manager=memory,
        role_loader=role,
        skill_loader=skill,
    )
    return _deps
```

---

### 改动 2：Skill 出厂清理

#### 2.1 删除个人/旧版 Skill 目录

这些是你个人开发的 Skill，不应出现在出厂包里：

- `skills/bug-analyzer/` — 旧版bug分析，和出厂「数据分析」功能重叠
- `skills/code-reviewer/` — 旧版英文代码审查，和出厂「代码审查」重复
- `skills/sipp-script-generator/` — 你个人工作用的SIPP脚本生成器，通用用户用不到

删除命令：
```bash
rm -rf skills/bug-analyzer
rm -rf skills/code-reviewer
rm -rf skills/sipp-script-generator
```

#### 2.2 保留的出厂 Skill（4个，已就位）

| 目录 | 状态 |
|------|------|
| `skills/翻译助手/SKILL.md` | ✅ 内容完善 |
| `skills/代码审查/SKILL.md` | ✅ 内容完善 |
| `skills/写作助手/SKILL.md` | ✅ 内容完善 |
| `skills/数据分析/SKILL.md` | ✅ 内容完善 |

> 清理后 Skill 页面只显示这 4 个，干净整齐。

---

### 改动 3：角色出厂优化

#### 3.1 重写「通用助手」角色

当前 `roles/通用助手.md` 内容太简陋（只有3行），重写为更专业的版本：

```markdown
你是 AI 助手，请用中文回答问题。

## 回答原则
- 结论先行，再展开论述
- 不确定的信息标注来源或声明"未经验证"
- 涉及代码时给出完整可运行的片段，不省略关键部分
- 多步骤任务按 1-2-3 有序列出，每步一个动作

## 工具使用
- 需要联网搜索时直接调用搜索工具
- 需要读写文件时调用 MCP 文件管理工具
- 需要执行代码时调用 MCP 代码执行工具

## 边界
- 不编造事实，不知道就说不知道
- 不提供医疗/法律/金融的投资建议，只提供信息参考
- 涉及危险操作（删除文件、执行命令等）先确认再操作
```

#### 3.2 删除娱乐角色

以下角色是你的个人趣味，不应出现在出厂包：

- `roles/猫.md` — "你是一只猫"
- `roles/混的入.md` — "90年代香港街头混的人"

删除命令：
```bash
rm roles/猫.md
rm roles/混的入.md
```

#### 3.3 保留的出厂角色（2个）

| 文件 | 定位 |
|------|------|
| `roles/通用助手.md` | 默认角色，适用所有场景 |
| `roles/测试工程师.md` | 专业角色，面向测试场景 |

#### 3.4 修改默认角色配置

`config/profiles/default/model.json` 当前默认角色是「猫」，需改为「通用助手」：

```json
{
  "model_id": "",
  "role": "通用助手",
  ...
}
```

> `model_id` 也应清空——新用户首次启动还没配模型，不应硬编码你的模型ID。

---

### 改动 4：清理本地调试残留

#### 4.1 重置 `rag/sources.json`

当前内容是你本地调试的「SDK测试报告」硬编码路径，出厂时应为空：

```json
{
  "sources": []
}
```

#### 4.2 重置 `config/profiles/default/mcp_connections.json`

当前内容是已解析的绝对路径，出厂时应为空（首次启动由 default_mcp.json 自动注入）：

```json
{
  "connections": []
}
```

#### 4.3 重置 `config/profiles/default/model.json`

```json
{
  "model_id": "",
  "role": "通用助手",
  "toggles": {
    "web_search": false,
    "rag": false,
    "memory": true
  },
  "context": {
    "max_history_chars": 50000,
    "memory_compact_enabled": true,
    "memory_compact_trigger": "messages",
    "memory_compact_interval_chars": 8000,
    "memory_compact_interval_msgs": 20,
    "memory_compact_window": 40,
    "memory_compact_max_tokens": 800,
    "memory_merge_threshold": 8,
    "memory_inject_max_chars": 4000,
    "memory_inject_strategy": "latest",
    "cross_session_inject_count": 10,
    "context_budget_enabled": true,
    "context_window_override": 0,
    "output_reserve_ratio": 0.2,
    "budget_alert_threshold": 0.75
  }
}
```

#### 4.4 删除 `memory/` 下的调试数据

```
memory/project-notes/scene_compact_20260622_161251.md
memory/project-notes/scene_compact_20260622_171627.md
```

这些是你本地对话的压缩记忆片段，出厂不应携带。

---

## 三、文件级改动汇总

### 新增文件

| 文件 | 内容 |
|------|------|
| `config/defaults/default_rag.json` | RAG 出厂数据源配置（见改动1.1） |

### 修改文件

| 文件 | 改动 |
|------|------|
| `backend/deps.py` | `init_deps()` 增加 RAG 出厂注入逻辑（见改动1.2） |
| `roles/通用助手.md` | 重写为更专业的版本（见改动3.1） |
| `rag/sources.json` | 清空为 `{"sources": []}` |
| `config/profiles/default/mcp_connections.json` | 清空为 `{"connections": []}` |
| `config/profiles/default/model.json` | 清空 model_id、改默认角色为「通用助手」 |

### 删除文件

| 文件/目录 | 原因 |
|-----------|------|
| `skills/bug-analyzer/` | 个人旧版Skill，和出厂重叠 |
| `skills/code-reviewer/` | 个人旧版Skill，和出厂重叠 |
| `skills/sipp-script-generator/` | 个人工作用Skill，通用用户不需要 |
| `skills/toggles.json` | 运行时生成，不应入库（如已入库则删） |
| `roles/猫.md` | 个人趣味角色 |
| `roles/混的入.md` | 个人趣味角色 |
| `memory/project-notes/scene_compact_*.md` | 本地调试残留 |

---

## 四、出厂预置最终清单

### Skill ×4

| 名称 | 一句话描述 | 开关 |
|------|-----------|------|
| 翻译助手 | 专业翻译，中英互译，准确性优先 | 默认启用 |
| 代码审查 | 安全/性能/可维护三维度审查 | 默认启用 |
| 写作助手 | 专业写作顾问，结论先行 | 默认启用 |
| 数据分析 | 描述→诊断→预测→建议分析框架 | 默认启用 |

### MCP ×2

| 名称 | 类型 | 命令 | 前置条件 |
|------|------|------|---------|
| 文件管理 | stdio | `npx -y @modelcontextprotocol/server-filesystem {workspace_dir}` | Node.js |
| 代码执行 | stdio | `npx -y @modelcontextprotocol/server-python` | Node.js |

### RAG ×1

| 名称 | 路径 | 文档数 |
|------|------|--------|
| 使用指导 | `rag/使用指导` | 3个md文件（Agent使用手册/插件开发指南/常见问题库） |

### 角色 ×2

| 名称 | 定位 |
|------|------|
| 通用助手 | 默认角色，专业简洁 |
| 测试工程师 | 专业角色，测试场景 |

---

## 五、验证步骤

改动完成后，按以下步骤验证出厂预置：

1. **清空运行时数据**：
   ```bash
   rm -rf chroma_db/*
   rm -rf memory/conversations/*
   rm -rf memory/project-notes/*
   ```
   
2. **重置配置文件**（按上面第四节的内容）

3. **启动应用**：`python run.py`

4. **验证 MCP 页面**：
   - 应自动出现「文件管理」和「代码执行」两个连接
   - 点「连接」应成功（前提：Node.js已装）
   - 未装 Node.js 时应显示「⚠️ 需要Node.js」

5. **验证 RAG 页面**：
   - 应自动出现「使用指导」数据源
   - 路径显示为绝对路径（`resolve_path` 转换后）
   - 点「索引」应成功，显示3个文件

6. **验证 Skill 页面**：
   - 应显示4个Skill（翻译助手/代码审查/写作助手/数据分析）
   - 无 bug-analyzer / code-reviewer / sipp-script-generator

7. **验证对话页**：
   - 默认角色应为「通用助手」
   - 模型选择器为空（需用户自行配置）
   - 开关状态：RAG关、搜索关、记忆开

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
