# AICraft 开发指南

> 本文档面向 Claude Code，指导其按规范开发 AICraft 项目

## 项目概述

AICraft 是一个个人桌面AI能力启动器，用 Python + Flet 构建。
核心理念：像MC启动器管理mod一样管理AI的Skill/MCP/RAG/记忆等能力。

## 项目结构

```
D:/AICraft/
├── aicraft.py              # 主入口
├── src/                    # 源码
│   ├── ui/                 # UI层（Flet页面）
│   ├── core/               # 核心逻辑
│   │   ├── llm.py          # LLM调用（litellm）
│   │   ├── mcp_client.py   # MCP客户端
│   │   ├── skill_loader.py # Skill加载器
│   │   ├── rag_engine.py   # RAG引擎
│   │   ├── memory.py       # 记忆管理
│   │   ├── role_loader.py  # 角色加载器
│   │   └── web_search.py   # 联网搜索
│   └── utils/              # 工具函数
│       ├── config.py       # 配置管理
│       └── file_watcher.py # 文件监听
├── config/                  # 全局配置
├── models/                  # 模型配置JSON
├── roles/                   # 角色md文件
├── skills/                  # Skill文件夹
├── rag/                     # RAG数据源配置
├── memory/                  # 记忆数据
├── chroma_db/               # 向量数据库
├── docs/                    # 文档
│   ├── TECH_SPEC.md        # 技术定型
│   └── DEV_GUIDE.md        # 本文档
└── requirements.txt
```

## 编码规范

### Python
- Python 3.11+
- 类型注解必须
- 异步优先（async/await），Flet支持异步
- 所有用户可见文字用中文
- 代码注释用中文
- 错误信息用中文

### 命名
- 文件名：snake_case
- 类名：PascalCase
- 函数/变量：snake_case
- 常量：UPPER_SNAKE_CASE
- UI组件变量：下划线前缀 _xxx 区分

### 配置文件
- JSON格式，UTF-8编码
- 缩进2空格
- 不存敏感信息到Git（.gitignore排除含api_key的文件）

## 关键约束

1. **用户只精通Python** — 所有代码必须Python可读，不用JS/TS/Qt
2. **单机桌面应用** — 不考虑服务器部署、多用户、并发
3. **配置即文件** — 所有配置都是JSON/MD文件，迁移=拷文件夹
4. **Flet框架** — UI全部用Flet实现，不混用其他UI框架
5. **litellm统一调用** — 所有LLM调用走litellm，不直接调各厂商SDK

## 开发流程

1. 每个Phase开始前，先读 docs/TECH_SPEC.md 了解该Phase的范围
2. 每个功能模块先写核心逻辑，再接UI
3. 提交信息格式：`[Phase N] 模块: 简要描述`
4. 遇到Flet/依赖问题，先查官方文档再查GitHub Issues

## 依赖版本注意

- Flet: >=0.25.0（需要稳定的导航栏和异步支持）
- litellm: >=1.50.0（需要稳定的streaming + tool calling）
- ChromaDB: >=0.5.0（PersistentClient API）
- sentence-transformers: >=3.0（本地embedding）

## Git规范

- 主分支: main
- 开发分支: dev
- 功能分支: feature/phase-N-module-name
- .gitignore: 排除 chroma_db/, *.pyc, __pycache__, config/profiles/*/api_keys, .env
