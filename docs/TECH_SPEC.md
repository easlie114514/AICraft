# AICraft 技术定型文档

> 项目代号：AICraft
> 定位：个人桌面AI能力启动器
> 创建日期：2026-06-17
> 核心约束：用户只精通Python，所有技术栈以Python为主

---

## 一、技术栈总览

```
┌─────────────────────────────────────────┐
│              AICraft 桌面应用              │
│                                         │
│  前端框架：Flet (纯Python, Material Design) │
│  后端逻辑：Python 3.11+                  │
│  数据存储：本地JSON + SQLite              │
│  打包发布：PyInstaller → 单文件.exe       │
└─────────────────────────────────────────┘
```

### 为什么选Flet而不是PySide6/Electron

| 维度 | Flet | PySide6 | Electron |
|------|------|---------|----------|
| 语言 | 纯Python | 纯Python | JS+Python |
| UI风格 | Material Design开箱即用 | 需要手写样式 | Web自由 |
| 代码量 | 少（约PySide6的1/3） | 多 | 中 |
| 打包 | 原生支持 | PyInstaller | electron-builder |
| 学习曲线 | 低 | 中（Qt概念多） | 需学JS |
| 社区 | 活跃增长 | 成熟 | 成熟 |
| 本项目适配 | 标签页/列表/开关/聊天框全部内置 | 但代码多 | 但用户看不懂 |

**结论：Flet是Python开发者做桌面应用的最优解**

---

## 二、各模块技术选型

### 1. 对话模块

| 组件 | 选型 | 理由 |
|------|------|------|
| LLM调用 | **litellm** | 统一接口支持100+模型，换模型只改一个字符串 |
| 流式输出 | litellm自带streaming | 打字机效果 |
| 对话历史 | JSON文件存储 | 按项目/日期，简单可靠 |
| Function Calling | litellm + MCP工具列表 | 标准OpenAI格式 |

```python
from litellm import completion

response = completion(
    model="deepseek/deepseek-chat",  # 换模型只改这里
    messages=messages,
    tools=mcp_tools,  # MCP工具列表
    api_key="sk-xxx",
    stream=True
)
```

### 2. 模型模块

| 组件 | 选型 | 理由 |
|------|------|------|
| 配置存储 | JSON文件 | 每个模型一个配置 |
| 连通测试 | litellm轻量调用 | 发一条ping消息验证 |

```json
{
  "name": "DeepSeek-V4 Pro",
  "provider": "deepseek",
  "model_id": "deepseek/deepseek-chat",
  "api_key": "sk-xxx",
  "api_base": "https://api.deepseek.com",
  "is_default": true
}
```

### 3. MCP模块

| 组件 | 选型 | 理由 |
|------|------|------|
| MCP客户端 | **mcp Python SDK** | 官方SDK，稳定 |
| 连接方式 | HTTP/SSE（远程） | 填IP+Port即连 |
| 工具发现 | MCP协议自带 | 连上自动拉取工具列表 |
| 状态检测 | 定期ping | 每30秒检测一次连接状态 |

```python
from mcp import ClientSession
from mcp.client.sse import sse_client

async def connect_mcp(host, port):
    async with sse_client(f"http://{host}:{port}/sse") as (read, write):
        async with ClientSession(read, write) as session:
            tools = await session.list_tools()
            return tools
```

### 4. Skill模块

| 组件 | 选型 | 理由 |
|------|------|------|
| 识别方式 | 读取SKILL.md | 兼容扣子Skill格式 |
| 加载方式 | 注入system prompt | LLM自动理解技能描述 |
| 脚本执行 | subprocess沙箱 | 隔离运行，安全 |
| 文件监听 | watchdog | 放入新Skill自动识别 |

```python
def load_skills(skill_dir):
    skills = []
    for folder in Path(skill_dir).iterdir():
        skill_md = folder / "SKILL.md"
        if skill_md.exists():
            skills.append({
                "name": folder.name,
                "description": skill_md.read_text(),
                "enabled": True
            })
    return skills
```

### 5. RAG模块

| 组件 | 选型 | 理由 |
|------|------|------|
| 向量数据库 | **ChromaDB** | 纯Python，嵌入式运行，无需部署服务 |
| 文本切分 | langchain text_splitters | 成熟可靠 |
| Embedding | sentence-transformers | 本地运行，免费，无需API |
| 文档解析 | PyPDF2 + python-docx | PDF/Word通吃 |
| 文件监听 | watchdog | 文件变化自动重新索引 |

```python
import chromadb
from sentence_transformers import SentenceTransformer

embedder = SentenceTransformer('all-MiniLM-L6-v2')
client = chromadb.PersistentClient(path="./chroma_db")

def index_documents(doc_dir):
    collection = client.get_or_create_collection("knowledge")
    for file in Path(doc_dir).rglob("*"):
        text = parse_file(file)
        chunks = split_text(text)
        embeddings = embedder.encode(chunks)
        collection.add(documents=chunks, embeddings=embeddings, ids=[...])

def search(query, top_k=5):
    query_emb = embedder.encode([query])
    results = collection.query(query_embeddings=query_emb, n_results=top_k)
    return results["documents"]
```

### 6. 记忆模块

| 组件 | 选型 | 理由 |
|------|------|------|
| 对话历史 | JSON文件 | 按项目存储 |
| 项目笔记 | Markdown文件 | 放进memory文件夹自动识别 |
| 智能检索 | 复用RAG的ChromaDB | 同一套向量检索，不重复造 |
| 偏好记录 | JSON配置 | 用户习惯自动沉淀 |

```python
# 第一层：对话历史
def load_history(project):
    return json.loads(Path(f"memory/{project}/history.json").read_text())

# 第二层：项目笔记
def load_notes(project):
    notes_dir = Path(f"memory/{project}/notes")
    return "\n".join(f.read_text() for f in notes_dir.glob("*.md"))

# 第三层：智能检索（复用RAG）
def search_memory(query, project):
    return rag_search(query, source=f"memory/{project}")
```

### 7. 角色模块

| 组件 | 选型 | 理由 |
|------|------|------|
| 存储格式 | Markdown文件 | 一个角色一个md |
| 加载方式 | 作为system prompt注入 | 最简单的实现 |

```markdown
<!-- roles/测试工程师.md -->
你是资深软件测试工程师，专注于功能测试、接口测试和自动化测试。
输出风格：结论先行，结构化呈现，标注优先级。
重点关注：边界条件、异常路径、兼容性。
```

### 8. 联网搜索

| 组件 | 选型 | 理由 |
|------|------|------|
| 搜索引擎 | **duckduckgo-search** | 免费，无需API Key |
| 集成方式 | 作为MCP工具或直接调用 | 开关控制 |

---

## 三、数据存储结构

```
AICraft/
├── aicraft.py              # 主入口
├── config/                  # 全局配置
│   ├── app.json            # 应用设置（主题、语言等）
│   └── profiles/           # 项目配置隔离
│       ├── default/
│       │   ├── model.json  # 当前使用的模型
│       │   ├── role.json   # 当前使用的角色
│       │   ├── toggles.json # 各模块开关状态
│       │   └── mcp_connections.json
│       └── project_x/
│           └── ...
├── models/                  # 模型配置
│   ├── deepseek-v4.json
│   └── gpt-4o.json
├── roles/                   # 角色模板
│   ├── 通用助手.md
│   └── 测试工程师.md
├── skills/                  # 技能文件夹
│   ├── bug-analyzer/
│   │   └── SKILL.md
│   └── test-case-gen/
│       └── SKILL.md
├── rag/                     # RAG数据源配置
│   └── sources.json        # {name, path, enabled}
├── memory/                  # 记忆
│   ├── conversations/      # 对话历史
│   └── project-notes/      # 项目笔记
├── chroma_db/               # 向量数据库（ChromaDB自动管理）
├── docs/                    # 文档
│   └── TECH_SPEC.md        # 本文档
└── requirements.txt         # 依赖清单
```

---

## 四、UI结构

```
┌──────────────────────────────────────────────┐
│  AICraft                    [模型: DeepSeek ▼]  [角色: 通用助手 ▼]  │
├──────────────────────────────────────────────┤
│  对话  |  Skill  |  MCP  |  RAG  |  记忆  |  角色  |  模型  │
├──────────────────────────────────────────────┤
│                                              │
│  [当前标签页内容]                              │
│                                              │
└──────────────────────────────────────────────┘
```

### 对话页
```
┌──────────────────────────────────┐
│ [ON] 联网搜索  [ON] RAG检索  [OFF] 记忆注入  │
├──────────────────────────────────┤
│                                  │
│  AI: 你好，有什么可以帮你？        │
│  You: 帮我分析这轮bug分布         │
│  AI: [调用 bug-analyzer Skill]   │
│      [调用 Jira MCP 获取数据]    │
│      本轮bug共23个...            │
│                                  │
├──────────────────────────────────┤
│  [输入消息...]          [发送]    │
└──────────────────────────────────┘
```

### Skill页
```
┌──────────────────────────────────┐
│  [打开Skill文件夹]               │
├──────────────────────────────────┤
│  ON  bug-analyzer                │
│      BUG数据多维度分析并生成报表   │
│  ON  test-case-gen               │
│      需求文档分析->测试用例生成    │
│  OFF report-generator            │
│      自动生成测试报告             │
└──────────────────────────────────┘
```

### MCP页
```
┌──────────────────────────────────┐
│  [添加MCP]                       │
├──────────────────────────────────┤
│  ON  jira       已连接   :8080   │
│  ON  gitlab     已连接   :8081   │
│  OFF sipp       断开     :8082   │
│                                  │
│  [jira 工具列表]                  │
│  - search_issues                │
│  - create_bug                   │
│  - update_status                │
└──────────────────────────────────┘
```

### RAG页
```
┌──────────────────────────────────┐
│  [添加数据源]                     │
├──────────────────────────────────┤
│  ON  project-docs  rag/使用指导    │
│      已索引 156 个文件            │
│  OFF api-specs    192.168.1.100  │
│      未索引                      │
│                                  │
│  [索引状态] 正在索引... 45/156    │
└──────────────────────────────────┘
```

### 记忆页
```
┌──────────────────────────────────┐
│  [打开记忆文件夹]                 │
├──────────────────────────────────┤
│  对话历史                         │
│  ON  project-x (23条对话)         │
│  OFF project-y (8条对话)          │
│                                  │
│  项目笔记                         │
│  ON  测试策略.md                  │
│  ON  bug模式记录.md               │
└──────────────────────────────────┘
```

### 角色页
```
┌──────────────────────────────────┐
│  [打开角色文件夹]                 │
├──────────────────────────────────┤
│  > 通用助手 (当前)                │
│  > 测试工程师                     │
│  > 代码审查员                     │
│  > + 新建角色                    │
└──────────────────────────────────┘
```

### 模型页
```
┌──────────────────────────────────┐
│  [添加模型]                       │
├──────────────────────────────────┤
│  * DeepSeek-V4 Pro (默认)        │
│    api.deepseek.com  已连接      │
│                                  │
│    GPT-4o                        │
│    api.openai.com    未配置Key   │
│                                  │
│  [测试连接]  [设为默认]           │
└──────────────────────────────────┘
```

---

## 五、依赖清单

```
# 核心
flet>=0.25.0              # UI框架
litellm>=1.50.0           # 统一LLM调用

# MCP
mcp>=1.0.0                # MCP官方SDK

# RAG
chromadb>=0.5.0           # 向量数据库
sentence-transformers>=3.0 # 本地Embedding
langchain-text-splitters  # 文本切分

# 文档解析
PyPDF2                    # PDF
python-docx               # Word

# 联网搜索
duckduckgo-search         # 搜索

# 工具
watchdog                  # 文件监听
pyperclip                 # 剪贴板

# 打包
pyinstaller               # 打包成exe
```

---

## 六、开发里程碑

### Phase 1 — 最小可用（1周）
- [ ] Flet框架搭建 + 7标签页骨架
- [ ] 对话页：接通LLM，流式输出
- [ ] 模型页：填API Key，连通测试，切换模型
- [ ] 角色页：读md文件，下拉选择
- [ ] 基础配置存读

### Phase 2 — 核心能力（1周）
- [ ] MCP页：添加连接，状态检测，工具发现
- [ ] Skill页：打开文件夹，自动识别，开关
- [ ] 对话页集成MCP工具调用
- [ ] 对话页集成Skill注入

### Phase 3 — 知识与记忆（1周）
- [ ] RAG页：指定目录，自动索引，开关
- [ ] 对话页集成RAG检索
- [ ] 联网搜索开关
- [ ] 记忆页：对话历史 + 项目笔记 + 智能检索

### Phase 4 — 打磨发布（1周）
- [ ] 项目隔离（多profile切换）
- [ ] 错误处理 + 状态提示
- [ ] PyInstaller打包成exe
- [ ] 使用文档

---

## 七、风险与备选

| 风险 | 影响 | 备选方案 |
|------|------|---------|
| Flet不够成熟，遇到无法解决的问题 | 高 | 降级到PySide6 |
| ChromaDB性能不足 | 低 | 换SQLite-vss或Qdrant本地模式 |
| sentence-transformers模型太大 | 低 | 换OpenAI Embedding API（远程） |
| MCP SSE连接不稳定 | 中 | 加重连逻辑 + 降级到stdio模式 |
