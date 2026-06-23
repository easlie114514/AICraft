# AICraft — 个人桌面AI启动器

## 快速开始

1. **双击 `AICraft.exe`** 启动应用
2. 软件会自动打开一个桌面窗口
3. 首次使用时，进入「模型」页添加 API 配置
4. 配置完成后即可在「对话」页开始使用

## 目录结构

```
AICraft/
├── AICraft.exe          # 主程序
├── config/              # 全局配置（含profile）
│   ├── app.json
│   ├── defaults/        # 出厂默认配置
│   └── profiles/        # 项目配置
├── models/              # LLM API 配置（在此目录添加模型）
├── roles/               # 角色模板（.md 文件）
├── skills/              # Skill 模块
├── mcp/                 # MCP 连接配置
├── rag/                 # RAG 数据源配置
├── memory/              # 对话历史 & 笔记
│   ├── conversations/   # 自动保存的对话
│   └── project-notes/   # 项目笔记
├── chroma_db/           # 向量数据库（RAG检索用）
└── workspace/           # MCP 工具工作区
```

## 配置模型

1. 启动 AICraft
2. 点击底部「模型」标签
3. 点击「＋ 添加模型」
4. 填写：
   - **模型名称**: 任意名称，如 `DeepSeek-V4`
   - **Provider**: `openai`（DeepSeek 兼容 OpenAI API）
   - **Model ID**: `openai/deepseek-v4-pro`
   - **API Base URL**: `https://api.deepseek.com/v1`
   - **API Key**: 你的 API Key
5. 点击保存，测试连接

## 系统要求

- Windows 10/11（自带 WebView2 运行时）
- 首次 RAG 索引需要联网下载 Embedding 模型（~80MB）

## 功能

| 功能 | 说明 |
|------|------|
| Skill | 拖入 Skill 文件夹，一键启用/停用 |
| MCP | 添加 MCP 服务器，管理工具连接 |
| RAG | 指向文档目录，自动索引，智能检索 |
| 记忆 | 对话历史 + 项目笔记 + 跨会话智能检索 |
| 角色 | 切换 System Prompt，改变 AI 行为 |
| 模型 | 管理多个 LLM API 配置，一键切换 |
