<div align="center">
  <img src="README_logo.png" width="280">

  <h1>AICraft</h1>

  <h3>🧩 让 配置 Agent 能力 比 游戏配置 Mod 还要简单</h3>

  <p><em>Skill 即 Mod · 角色即皮肤 · MCP 即工具 · 装好即玩</em></p>

  <p>
    <img src="https://img.shields.io/badge/Version-v1.0.6-165DFF">
    <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white">
    <img src="https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white">
    <img src="https://img.shields.io/badge/License-Apache_2.0-blue">
  </p>

  <p>
    <a href="https://github.com/Easlie114514/AICraft/releases"><img src="https://img.shields.io/badge/⬇️_下载最新版-Releases-brightgreen?style=for-the-badge"></a>
    <a href="#-快速开始"><img src="https://img.shields.io/badge/⚡_3_分钟上手-Quick_Start-orange?style=for-the-badge"></a>
  </p>
</div>

---

## 💡 一句话说清楚

> **AICraft 是一个桌面 AI 启动器。** 不需要 Python 环境，不需要手写配置，不需要敲命令行。打开 exe → 填 Key → 开聊。Skill、MCP、RAG、记忆、角色 —— 全部可视化，热插拔。

---

## 🎮 一览

<div align="center">
  <table><tr>
    <td><img src="docs/screenshots/chat.png" width="900"><br><sub><i>💬 对话：RAG · 记忆 · 深度思考 · Token 计费 · 项目上下文，开箱即用</i></sub></td>
  </tr></table>
</div>

<div align="center">
  <table><tr>
    <td><img src="docs/screenshots/deepseek.png" width="900"><br><sub><i>🔧 DeepSeek 一键接入，自动创建 V4 Pro + Flash 双模型</i></sub></td>
  </tr></table>
</div>

<div align="center">

| | | |
|:--:|:--:|:--:|
| <img src="docs/screenshots/skills.png" width="400"><br><sub><i>🧩 Skill 热插拔</i></sub> | <img src="docs/screenshots/mcp.png" width="400"><br><sub><i>🔧 MCP 工具管理</i></sub> | <img src="docs/screenshots/rag.png" width="400"><br><sub><i>📚 本地 RAG 知识库</i></sub> |
| <img src="docs/screenshots/memory.png" width="400"><br><sub><i>🧠 三层记忆</i></sub> | <img src="docs/screenshots/roles.png" width="400"><br><sub><i>🎭 角色管理</i></sub> | <img src="docs/screenshots/setting.png" width="400"><br><sub><i>⚙️ 设置</i></sub> |

</div>

---

## ✨ 能力矩阵

<div align="center">

| 🚀 | 🎭 | 🧩 | 🔧 |
|:--:|:--:|:--:|:--:|
| **DeepSeek 一键接入** | **角色快切** | **Skill 热插拔** | **MCP 工具** |
| 填入 Key 自动创建<br>V4 Pro + Flash 双模型 | 一键切换角色人格<br>记忆无痕保留 | 5 个出厂 Skill<br>一键启用/停用 | 文件管理 + 代码执行<br>Agent 真正能动手 |

| 📚 | 🧠 | 💭 | 💰 |
|:--:|:--:|:--:|:--:|
| **本地 RAG** | **三层记忆** | **深度思考** | **Token 计费** |
| ChromaDB 向量检索<br>数据不出本机 | L0 实时 → L1 短期<br>→ L2 长期持久化 | DeepSeek 深度思考<br>推理更深入 | 用量 & 费用实时统计<br>缓存命中单独展示 |

| 🤖 | 🎨 | 📂 | 🛡️ |
|:--:|:--:|:--:|:--:|
| **上下文管理** | **9 套主题** | **便携运行** | **权限管控** |
| 6 级优先级裁剪<br>1M 上下文不浪费 | 一键切换界面主题<br>色卡渐变光效 | 解压即用无需安装<br>数据跟随 exe 目录 | 文件/代码操作<br>逐次授权，60s 超时 |

</div>

---

## 🧩 出厂配置

| 模块 | 说明 |
|:-----|:-----|
| 🧩 **5 个 Skill** | 代码审查 · 写作助手 · 数据分析 · 翻译助手 · 角色设计师 |
| 🔧 **2 个 MCP** | 文件管理（读写本地文件）· 代码执行（Python 沙箱） |
| 🎭 **1 个角色** | AICraft 智能小助手（支持自定义创建） |
| 📚 **3 篇文档** | RAG 预置使用手册 · 开发指南 · FAQ |

---

## 🚀 3 分钟上手

```bash
# ①  下载
从 Releases 下载最新版 → 解压 → 双击 AICraft.exe

# ②  接入
切换到「模型」页 → DeepSeek 一键接入 → 粘贴 API Key → 保存

# ③  开聊
搞定。你现在拥有一个带文件管理、代码执行、RAG、记忆的桌面 Agent。
```

---

## 🛠️ 技术栈

| 层 | 技术 |
|:---|:-----|
| 🐍 后端 | Python · FastAPI · ChromaDB · httpx · WebSocket |
| ⚛️ 前端 | React 19 · Vite 8 · TailwindCSS 4 · Shadcn UI · StreamMD |
| 📦 打包 | PyInstaller onedir · 便携免安装 |

---

## 🗺️ 路线图

- [ ] 多模态输入 — 文件 + 图片拖拽上传
- [ ] AI 返回文件 — 工具产出 CSV、图片等直接下载
- [ ] SkillHub — 社区市场，分享和安装 Skill
- [ ] Token 统计增强 — 历史可查、数据导出

---

## 📄 License

[Apache 2.0](LICENSE) · Free to use, modify, and distribute.

---

<p align="center">
  <sub>❤️ Built by <a href="https://github.com/Easlie114514">Easlie</a></sub>
</p>
