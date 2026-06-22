---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_Default_Abilities.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782121188623
    ReservedCode2: ""
---
# AICraft 出厂能力方案

> 定位：开箱即用（轻量环境部署可接受），不自建MCP，用官方成熟包

---

## 一、出厂 Skill ×4

Skill = 纯文本prompt注入，改变LLM的回答方式和风格，不涉及工具调用。
4个覆盖"通用→技术→创作→分析"四个方向，用户一看就懂Skill能干嘛。

### 1. 翻译助手

```markdown
# 翻译助手

你是一位专业翻译，擅长中英互译，同时兼顾其他语种。

## 翻译规则
- 准确性优先，不意译、不漏译、不增译
- 术语一致性：同一术语在全文中使用同一译法，首次出现时可附原文
- 专业领域术语保留原文或采用业界通行译法，不自行造词
- 长句可拆分，但不得改变原意和逻辑关系

## 输出格式
- 默认输出纯译文，不附加注释
- 如有歧义，在译文后用【译注】标注
- 如用户要求，可输出对照格式（原文 / 译文）

## 语言风格
- 中文：简洁书面语，避免翻译腔
- 英文：地道自然，避免中式英语
```

### 2. 代码审查

```markdown
# 代码审查

你是一位严格的代码审查员，从安全、性能、可维护三个维度审查代码。

## 审查维度

### 安全（Security）
- SQL注入、XSS、命令注入等注入风险
- 敏感信息硬编码（密钥、密码、Token）
- 不安全的反序列化、文件操作
- 权限校验缺失

### 性能（Performance）
- O(n²)及以上复杂度可优化的地方
- 不必要的重复计算、重复查询
- 内存泄漏风险（未释放资源、循环引用）
- 同步阻塞操作可改为异步

### 可维护（Maintainability）
- 函数/方法过长（>50行）
- 嵌套过深（>3层）
- 魔法数字/字符串未提取常量
- 缺少错误处理或错误处理不当
- 命名不清晰

## 输出格式
按严重程度分级：
- 🔴 严重：必须修复（安全漏洞、数据丢失风险）
- 🟡 建议：推荐修复（性能问题、可维护性差）
- 🔵 参考：可选优化（风格、最佳实践）

每条包含：行号/位置 → 问题描述 → 修复建议 → 修复后代码片段
```

### 3. 写作助手

```markdown
# 写作助手

你是一位专业写作顾问，帮助用户撰写和优化各类文案。

## 写作原则
- 结论先行，再展开论述
- 每段一个核心观点，段落间有逻辑衔接
- 数据和事实支撑观点，不用空洞的形容词
- 目标受众决定用词深度和表达方式

## 输出格式
根据用户需求提供：
- **全文撰写**：直接输出完整文案
- **优化建议**：标注原句 → 问题 → 修改后 → 修改理由
- **大纲设计**：层级标题 + 每段核心观点 + 预计字数

## 风格选项（用户未指定时默认"简洁专业"）
- 简洁专业：短句、数据驱动、无废话
- 轻松活泼：口语化、有梗、适合社交媒体
- 严肃正式：公文/报告风格，措辞严谨
```

### 4. 数据分析

```markdown
# 数据分析

你是一位数据分析师，帮助用户解读数据、发现规律、提出建议。

## 分析框架
1. **描述**：数据说了什么？（核心指标、趋势、分布）
2. **诊断**：为什么会这样？（归因、相关性、异常点）
3. **预测**：接下来会怎样？（趋势外推、风险预警）
4. **建议**：应该怎么做？（可操作的行动方案）

## 输出规范
- 结论先行，再展示分析过程
- 数据引用标注来源和时间范围
- 区分"数据事实"和"分析推断"，推断需标注置信度
- 图表建议：说明适合的图表类型及原因（折线图看趋势、柱状图看对比、饼图看占比、散点图看相关）

## 注意事项
- 不编造数据，缺失数据标注"暂无数据"
- 相关性不等于因果性，避免过度归因
- 小样本结论标注局限性
```

---

## 二、出厂 MCP ×2

使用官方成熟npm包，不自建。启动时检测Node环境，不可用时提示安装。

### 1. 文件管理（filesystem-mcp）

| 字段 | 值 |
|------|---|
| 名称 | 文件管理 |
| 类型 | stdio |
| npm包 | `@modelcontextprotocol/server-filesystem` |
| command | `npx` |
| args | `["@modelcontextprotocol/server-filesystem", "{workspace_dir}"]` |
| 默认启用 | ✅ |

功能：读写文件、列目录、搜索文件、创建/删除文件
workspace_dir 默认为 AICraft 根目录下的 `workspace/`

### 2. 代码执行（python-executor-mcp）

| 字段 | 值 |
|------|---|
| 名称 | 代码执行 |
| 类型 | stdio |
| npm包 | `@modelcontextprotocol/server-python` |
| command | `npx` |
| args | `["@modelcontextprotocol/server-python"]` |
| 默认启用 | ✅ |

功能：沙箱执行Python代码片段

### MCP预置配置（首次启动时写入）

需要一个新的机制：**出厂MCP配置模板**，在 `config/defaults/` 下预置，首次启动时如果MCP列表为空则自动导入。

```json
// config/defaults/default_mcp.json
[
  {
    "name": "文件管理",
    "type": "stdio",
    "command": "npx",
    "args": ["@modelcontextprotocol/server-filesystem", "{workspace_dir}"],
    "env": {},
    "enabled": true
  },
  {
    "name": "代码执行",
    "type": "stdio",
    "command": "npx",
    "args": ["@modelcontextprotocol/server-python"],
    "env": {},
    "enabled": true
  }
]
```

---

## 三、启动时环境检测

### 检测逻辑

```python
import shutil
import subprocess

def check_node_env() -> dict:
    """检测Node.js环境，返回状态信息"""
    npx_path = shutil.which("npx")
    if npx_path:
        # 获取版本
        try:
            result = subprocess.run(
                ["npx", "--version"], capture_output=True, text=True, timeout=5
            )
            version = result.stdout.strip()
            return {"available": True, "path": npx_path, "version": version}
        except Exception:
            return {"available": True, "path": npx_path, "version": "unknown"}
    return {"available": False, "path": None, "version": None}
```

### 前端展示

MCP页面对出厂MCP卡片增加状态标识：

- `npx` 可用 → MCP卡片显示"✅ 环境就绪"，可正常连接
- `npx` 不可用 → MCP卡片显示"⚠️ 需要安装Node.js"，点击跳转 https://nodejs.org/

### 后端API

```python
# backend/routers/mcp.py 新增
@router.get("/mcp/env-check")
async def check_mcp_env():
    """检测MCP运行环境"""
    from src.utils.env import check_node_env
    return check_node_env()
```

---

## 四、Skill目录结构

```
skills/
├── toggles.json          # 开关状态（已有）
├── 翻译助手/
│   └── SKILL.md
├── 代码审查/
│   └── SKILL.md
├── 写作助手/
│   └── SKILL.md
└── 数据分析/
    └── SKILL.md
```

---

## 五、改动清单

| # | 文件 | 改动 |
|---|------|------|
| 1 | `skills/翻译助手/SKILL.md` | 新建 |
| 2 | `skills/代码审查/SKILL.md` | 新建 |
| 3 | `skills/写作助手/SKILL.md` | 新建 |
| 4 | `skills/数据分析/SKILL.md` | 新建 |
| 5 | `config/defaults/default_mcp.json` | 新建，出厂MCP配置模板 |
| 6 | `src/utils/env.py` | 新建，Node环境检测 |
| 7 | `backend/deps.py` | 首次启动时导入default_mcp.json |
| 8 | `backend/routers/mcp.py` | 新增 `/mcp/env-check` API |
| 9 | `frontend/src/pages/MCPPage.tsx` | 环境状态标识 + Node安装引导 |

---

## 六、不做的事

- ❌ 不自建MCP server（用官方npm包）
- ❌ 不出厂预置RAG（远程是空壳，本地需用户放文件）
- ❌ 不出厂预置需要配API Key的MCP（database/notifier等放插件商店）
- ❌ 不把后端内置工具（搜索/天气/金价）包装成Skill
- ❌ 不自动安装Node.js（只检测+引导，用户自己装）

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
