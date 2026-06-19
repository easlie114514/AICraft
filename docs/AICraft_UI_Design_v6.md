---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_UI_Design_v6.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1781752967490
    ReservedCode2: ""
---
# AICraft UI 设计规范 v6 — React + Shadcn UI

> 基于 commit `159f761`（Flet全功能版本），React + Shadcn UI 重写前端
> 核心原则：兼容性(Win10/11) > 低性能消耗 > 美观 > 组件化
> 最终交付：PyInstaller打包为单个exe，双击即用

---

## 一、技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 前端框架 | React 19 | — |
| 构建工具 | Vite 8 | — |
| 组件库 | **Shadcn UI** | 全部UI必须用Shadcn组件，禁止手写 |
| 样式 | TailwindCSS 4 + Shadcn token | 禁止内联style |
| 图标 | Lucide React | 按需引入 |
| 后端 | FastAPI | 端口8765 |
| 桌面窗口 | pywebview | 无边框+自定义标题栏 |
| 打包 | PyInstaller | 单exe，内含前端静态文件 |
| 动效 | 仅CSS transition | 禁止JS动画库 |

### Shadcn 必装组件

```bash
npx shadcn@latest add button card dialog input label select switch tabs textarea badge separator dropdown-menu tooltip scroll-area sheet collapsible avatar popover command
```

### 铁律

1. **所有UI元素必须使用Shadcn组件**，禁止手写CSS布局和弹窗
2. **禁止内联style对象**，全部用Tailwind class
3. **唯一允许自定义CSS的是颜色变量和字体声明**

---

## 二、设计Token

### 2.1 色彩（PCL蓝色系）

在 `globals.css` 中覆盖Shadcn的CSS变量：

```css
:root {
  --primary: 215 48% 60%;          /* #5B9BD5 PCL蓝 */
  --primary-foreground: 0 0% 100%;
  --background: 210 20% 96%;       /* #F5F7FA */
  --foreground: 234 33% 14%;       /* #1A1A2E */
  --card: 0 0% 100%;
  --card-foreground: 234 33% 14%;
  --muted: 210 20% 93%;
  --muted-foreground: 220 9% 46%;
  --border: 220 13% 91%;
  --input: 220 13% 91%;
  --ring: 215 48% 60%;
  --destructive: 0 84% 60%;
  --nav-bg: #2B4C7E;               /* 深蓝顶栏 */
  --nav-text: #E2E8F0;
  --radius: 0.75rem;               /* 全局圆角12px */
}
```

### 2.2 字体

```css
body {
  font-family: "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
}
```

- 字体文件放 `frontend/public/fonts/`，**仅引入 Regular(400) + Medium(500) 两个字重**
- 禁止引入6个字重（减少体积和加载时间）

### 2.3 圆角

| 元素 | 圆角 | Tailwind class |
|------|------|---------------|
| 按钮/开关 | 12px | rounded-xl |
| 卡片 | 16px | rounded-2xl |
| 弹窗 | 20px | rounded-[20px] |
| 输入框 | 10px | rounded-[10px] |
| 徽章 | 8px | rounded-lg |

### 2.4 间距

统一4px基数：`p-3`(12) `p-4`(16) `p-6`(24) `gap-3`(12) `gap-4`(16)

---

## 三、窗口与全局布局

### 3.1 桌面窗口

- 尺寸：1280×800，最小800×600
- pywebview `frameless=True` + 自定义窗口控制按钮
- 居中显示

### 3.2 全局布局

```
┌─────────────────────────────────────────────────────┐
│  顶部导航栏（48px）深蓝底 #2B4C7E                      │
│  [对话] [Skill] [MCP] [RAG] [记忆] [角色] [模型]  ─ □ ✕│
├─────────────────────────────────────────────────────┤
│                                                     │
│              内容区域（自适应高度）                      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 3.3 顶部导航栏

- 背景：`#2B4C7E`
- 左侧：7个Tab，**独立圆角卡片样式**（不是连体Tab），间隔6px
  - 当前Tab：白底 + 品牌蓝文字 `bg-white text-primary`
  - 非当前Tab：半透明白底20% + 白色文字 `bg-white/20 text-white`
  - 每个Tab用 `<Button variant="ghost">` + 自定义className
- 右侧：窗口控制按钮（最小化 ─ / 最大化 □ / 关闭 ✕）
  - 使用 `<Button variant="ghost" size="icon">` + Lucide图标
  - 关闭按钮hover变红

---

## 四、页面设计

### 4.1 对话页

> **设计理念**：对话页始终只有一个持续对话，不做多会话管理。上下文接近模型token上限时自动压缩摘要存入记忆，用户无感。历史对话统一在记忆页查看。

```
┌──────────────────────────────────────────────────┐
│                                                  │
│              消息区域（ScrollArea，全宽）           │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │  AI: 你好啊...                            │    │
│  └──────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────┐    │
│  │  You: 帮我写个脚本                         │    │
│  └──────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────┐    │
│  │  🔧 调用工具: read_file                   │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  ─────────────────────────────────────────────── │
│  [联网] [RAG] [记忆]                              │
│  ┌──────────────────────────────┬──────────┐    │
│  │ 输入消息...                   │模型▼ 角色▼ ➤│   │
│  └──────────────────────────────┴──────────┘    │
└──────────────────────────────────────────────────┘
```

**无左侧栏**：对话页全宽，所有页面布局一致，不做特例。

**消息区域**：
- `<ScrollArea>` 自动滚底，全宽
- 用户气泡：右对齐 `bg-primary/10 rounded-2xl`
- AI气泡：左对齐 `bg-muted rounded-2xl`
- 工具调用卡片：`<Card>` + 🔧图标 + `<Collapsible>` 折叠参数/结果
- AI回复用Markdown渲染，代码块语法高亮
- 上下文压缩提示：当自动压缩发生时，插入一条系统提示「已将早期对话摘要存入记忆」

**输入区域**：
- 开关：`<Switch>` ×3（联网/RAG/记忆），横排
- 输入框：`<Textarea>` maxRows=5 自动扩展
- 内嵌右侧：
  - `<Select>` 模型选择（small size）
  - `<Select>` 角色选择（small size）
  - `<Button>` 发送 `<Send>` 图标
  - 流式中变 `<Button variant="destructive">` 停止 `<Square>` 图标

**上下文自动压缩（后端逻辑）**：
- 上下文（发给LLM的消息）和聊天记录（UI展示的消息）是两回事
- UI上用户可以无限往上滚动查看所有历史消息，不会被截断
- 后端只把「摘要 + 最近N条消息」作为上下文发给LLM，早期原文不发送但前端保留
- 当对话token用量达到模型上限的80%时，触发压缩
- 压缩方式：调用同一模型对早期对话生成摘要
- 摘要写入记忆页（标记为「对话摘要」类型）
- 前端在压缩发生处插入一条系统提示「已将早期对话摘要存入记忆」，用户点击可跳转记忆页查看摘要

---

### 4.2 模型页

**布局**：全宽 `<ScrollArea>` + 卡片网格

**模型卡片**：`<Card>`
- 左：`<Avatar>` 内放 `<Cpu>` 图标，品牌蓝渐变底
- 中：模型名 `<CardTitle>` + `provider · model_id` `<p className="text-sm text-muted-foreground font-mono">`
- 右上：`<Badge>` 默认/已配置
- 右下操作：
  - `<Button variant="outline" size="sm">` 测试连接
  - `<Button variant="ghost" size="icon">` ⭐设为默认
  - `<Button variant="ghost" size="icon">` 🗑删除
- 测试结果：成功/失败 `<Badge variant="default/destructive">`

**添加模型**：`<Dialog>` （！禁止手写弹窗！）
- `<DialogTitle>` 添加模型
- 表单：
  - `<Label>` 模型名称 + `<Input placeholder="DeepSeek-V4 Pro">`
  - `<Label>` Provider + `<Select>` (OpenAI / DeepSeek / Anthropic / 其他)
  - `<Label>` Model ID + `<Input placeholder="deepseek/deepseek-chat">`
  - `<Label>` API Key + `<Input type="password">`
  - `<Label>` API Base（可选）+ `<Input placeholder="https://api.deepseek.com">`
- `<DialogFooter>`：`<Button variant="outline">` 取消 + `<Button>` 添加

---

### 4.3 角色页

**角色卡片**：`<Card>`
- `<Avatar>` + 角色名 + `<Badge>` 当前
- 操作：查看 / 设为当前 / 编辑 / 删除

**创建角色**：`<Dialog>`
- 角色名称 `<Input>`
- 角色内容 `<Textarea rows={8}>`

**查看角色**：`<Dialog>` + `<ScrollArea>`

---

### 4.4 Skill页

**Skill卡片**：`<Card>`
- 图标 + 名称 + 描述
- `<Switch>` 启用/禁用
- `<Button variant="outline" size="sm">` 打开目录

---

### 4.5 MCP页

**MCP卡片**：`<Card>`
- 名称 + 类型(SSE/Stdio) `<Badge>`
- 连接地址/命令 `<p className="font-mono text-sm text-muted-foreground">`
- 工具列表：`<Collapsible>` + 工具数 `<Badge>`
- 操作：`<Switch>` 启用 + `<Button>` 连接/断开 + `<Button variant="ghost">` 删除
- 状态：`<Badge variant="default/secondary/destructive">` 已连接/未连接/错误

**添加MCP**：`<Dialog>`
- 连接名称 `<Input>`
- 类型 `<Select>` SSE / Stdio
- URL `<Input>` + 命令 `<Input>` + 参数 `<Input>`（全部平铺显示，不做显隐切换）

---

### 4.6 RAG页

**RAG卡片**：`<Card>`
- 名称 + 类型 + 文件数 `<Badge>`
- 操作：`<Switch>` + `<Button>` 索引 + 删除

**添加数据源**：`<Dialog>`
- 名称 + 路径 + 类型 `<Select>`

---

### 4.7 记忆页

> 记忆页是唯一的「历史管理中心」，包含手动笔记和对话自动摘要。

**布局**：`<Tabs>` 切换笔记/对话摘要
- 笔记Tab：笔记列表 + 搜索 `<Input>`
- 对话摘要Tab：自动压缩产生的对话摘要，按时间倒序，可展开查看摘要内容
- 搜索：`<Input placeholder="搜索记忆...">`
- 每条记录标注类型：`<Badge>` 笔记 / 对话摘要

---

## 五、弹窗规范

### 统一使用 Shadcn `<Dialog>`

**禁止任何形式的自定义弹窗/overlay/modal。**

```jsx
// ✅ 正确：Shadcn Dialog
<Dialog>
  <DialogContent className="sm:max-w-[520px]">
    <DialogHeader>
      <DialogTitle>添加模型</DialogTitle>
    </DialogHeader>
    <div className="space-y-4 py-4">
      {/* 表单 */}
    </div>
    <DialogFooter>
      <Button variant="outline">取消</Button>
      <Button>确认</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>

// ❌ 禁止
<div className="modal-overlay" onClick={onClose}>
  <div className="modal-card">...</div>
</div>
```

Shadcn Dialog自带：
- ✅ 垂直居中（不再翻车）
- ✅ 点击遮罩关闭
- ✅ ESC关闭
- ✅ 长内容可滚动
- ✅ 入场/出场动画

---

## 六、动效规范

### 允许（仅3个CSS transition）

| 场景 | 实现 | 时长 |
|------|------|------|
| 页面切换淡入 | `animate-in fade-in` | 200ms |
| 弹窗入场 | Shadcn Dialog默认 | 200ms |
| 按钮hover | `transition-colors` | 150ms |

### 禁止

- ❌ 粒子特效（ClickSpark）
- ❌ 光晕卡片（SpotlightCard）
- ❌ 解密文字（DecryptedText）
- ❌ JS动画库（framer-motion / gsap）
- ❌ 复杂CSS动画（旋转/弹跳/波浪）

---

## 七、性能优化

### 7.1 前端

- 字体仅2字重（Regular 400 + Medium 500）
- 图标按需引入
- 弹窗懒加载（不在初始渲染时挂载所有Dialog）
- 长列表虚拟滚动（对话记录>100条）

### 7.2 后端

- WebSocket长连接，不轮询
- litellm支持代理配置（从配置文件读取）
- 生产模式：Vite build后FastAPI托管静态文件

---

## 八、API清单

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/models | 模型列表 |
| POST | /api/models | 添加模型 |
| DELETE | /api/models/{name} | 删除模型 |
| POST | /api/models/{name}/test | 测试连接 |
| GET/POST | /api/models/current | 当前模型 |
| GET | /api/roles | 角色列表 |
| POST | /api/roles | 创建角色 |
| DELETE | /api/models/{name} | 删除角色 |
| GET/POST | /api/roles/current | 当前角色 |
| GET | /api/skills | Skill列表 |
| POST | /api/skills/{name}/toggle | 启停 |
| GET | /api/mcp | MCP列表 |
| POST | /api/mcp | 添加MCP |
| DELETE | /api/mcp/{name} | 删除MCP |
| POST | /api/mcp/{name}/connect | 连接 |
| POST | /api/mcp/{name}/disconnect | 断开 |
| GET | /api/rag | RAG列表 |
| POST | /api/rag | 添加数据源 |
| DELETE | /api/rag/{name} | 删除 |
| POST | /api/rag/{name}/index | 索引 |
| POST | /api/rag/search | 检索 |
| GET | /api/memory/notes | 笔记 |
| GET | /api/memory/summaries | 对话摘要 |
| POST | /api/memory/search | 搜索 |
| POST | /api/search | 联网搜索 |
| WS | /api/chat/ws | 对话 |

### WebSocket消息格式

发送：`{ "type": "message", "content": "...", "model_id": "...", "role": "...", "toggles": {...}, "conversation_id": "..." }`
发送：`{ "type": "stop" }`

推送：`{ "type": "text", "content": "增量" }` / `{ "type": "tool_call", ... }` / `{ "type": "tool_result", ... }` / `{ "type": "done" }` / `{ "type": "error", ... }`

---

## 九、文件结构

```
AICraft/
├── app.py                  ← pywebview启动入口
├── backend/
│   ├── server.py           ← FastAPI主服务
│   └── chat_ws.py          ← WebSocket处理器
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx         ← 路由+布局
│   │   ├── components/
│   │   │   └── ui/         ← Shadcn组件（npx shadcn生成）
│   │   ├── pages/          ← 7个页面
│   │   ├── hooks/
│   │   │   └── useApi.js
│   │   └── lib/
│   │       └── utils.js    ← cn()工具
│   ├── components.json     ← Shadcn配置
│   └── package.json
├── src/
│   ├── core/               ← 业务逻辑（零修改复用）
│   └── utils/
│       └── config.py
├── models/  roles/  skills/  rag/  memory/
├── AICraft.spec            ← PyInstaller配置
└── requirements.txt
```

---

## 十、打包方案

### PyInstaller打包流程

```
1. Vite build → frontend/dist/ 静态文件
2. FastAPI启动时挂载dist/为静态文件目录
3. pywebview指向FastAPI地址（http://127.0.0.1:8765）
4. PyInstaller打包：
   - 单文件模式 --onefile
   - 包含 frontend/dist/ 数据
   - 包含 src/ 业务代码
   - 包含字体文件
   - 排除 aicraft.py（Flet旧入口）
```

### 运行架构

```
用户双击 AICraft.exe
  → PyInstaller解压到临时目录
  → 启动FastAPI后端（127.0.0.1:8765）
  → 启动pywebview窗口指向localhost:8765
  → 关闭窗口 → 后端自动清理退出
```

### 兼容性保障

- Win10/11统一体验：浏览器渲染不依赖系统UI组件
- 不依赖.NET/WPF/WinUI等系统框架
- 内置Chromium渲染（pywebview基于WebView2/CEF）

---

## 十一、代码复用策略

### 不需要重写的（直接复用）

| 文件 | 来源 | 说明 |
|------|------|------|
| src/core/ 全部 | commit 159f761 | 业务逻辑层，零修改 |
| src/utils/config.py | commit 159f761 | 配置管理，零修改 |

### 需要重写的

| 文件 | 说明 | 参考 |
|------|------|------|
| backend/server.py | FastAPI后端全新写 | 参照aicraft.py中的交互逻辑，1:1转成REST API |
| backend/chat_ws.py | WebSocket处理器全新写 | 参照aicraft.py中的流式对话逻辑 |
| frontend/src/** | React + Shadcn 全新写 | 参照v6规范 |
| run.py | pywebview启动入口 | 参照develop分支的run.py改 |

### 需要删除的

| 文件 | 说明 |
|------|------|
| aicraft.py | Flet旧入口（1841行），功能已迁移到backend+frontend |

### 关键原则：以159f761的功能为唯一标准

- 159f761的Flet版功能是经过用户验证OK的，所有后端API和前端交互必须1:1还原
- develop分支的后端仅作参考，不直接搬用（用户反馈develop部分功能不对劲）
- 具体做法：读aicraft.py中每个页面的交互逻辑 → 转成对应的FastAPI接口 → 前端Shadcn页面调接口

### 开发前置步骤

从159f761代码出发，执行：
1. 创建 `backend/` 目录，全新写FastAPI后端
2. 创建 `frontend/` 目录，Vite + React + Shadcn 初始化
3. 创建/修改 `run.py`（pywebview启动）
4. 删除 `aicraft.py`
5. 按v6规范重写所有页面

---

## 十二、开发顺序

| Step | 内容 | 验收标准 |
|------|------|---------|
| 1 | 项目初始化 + Shadcn安装 + 主题配置 | Vite dev跑起来，PCL蓝色主题生效 |
| 2 | 全局布局（顶栏+7Tab+窗口控制） | Tab切换正常，窗口控制按钮可用 |
| 3 | 模型页（CRUD+测试连接） | 能添加DeepSeek并测试连接成功 |
| 4 | 对话页（WebSocket+流式+上下文压缩） | 能对话，流式输出正常，压缩提示显示 |
| 5 | 角色/Skill/MCP/RAG/记忆页 | 全部CRUD正常 |
| 6 | pywebview桌面窗口 | 无边框窗口+自定义标题栏 |
| 7 | 打包exe（最后做，功能全验收完再打包） | 双击AICraft.exe启动，完整功能可用 |

---

## 十三、Claude Code 开发约束

1. **必须使用Shadcn组件**，先查Shadcn有没有，有则必须用
2. **禁止内联style对象**，全部Tailwind class
3. **禁止手写弹窗/overlay/modal**，统一 `<Dialog>`
4. **禁止引入动画库或React Bits特效**
5. **字体只引入2字重**
6. **每次提交前自检**：弹窗是否居中、表单是否可滚动、是否用了Shadcn组件
7. **删除aicraft.py**（Flet旧入口，打包时不包含）

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
