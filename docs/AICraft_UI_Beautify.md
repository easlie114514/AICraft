---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_UI_Beautify.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782207199593
    ReservedCode2: ""
---
# AICraft UI 美化方案

> 目标：基于现有 React + Shadcn UI + TailwindCSS 前端，沿用 WebFlowMapper 的 ArcoDesign 风格，将主色从 PCL蓝(#5B9BD5) 替换为字节蓝(#165DFF)，全面提升视觉品质
> 参考资产：`AICraft_Design_System_Ref.md`
> 执行者：Claude Code

---

## 一、全局色彩替换

### 1.1 globals.css 变量覆盖

将现有 PCL 蓝色系替换为字节蓝色系：

```css
:root {
  /* 主色：字节蓝 */
  --primary: 219 100% 55%;           /* #165DFF */
  --primary-foreground: 0 0% 100%;

  /* 背景 */
  --background: 210 20% 97%;          /* #F7F8FA */
  --foreground: 220 33% 11%;         /* #1D2129 */

  /* 卡片 */
  --card: 0 0% 100%;
  --card-foreground: 220 33% 11%;

  /* 柔和 */
  --muted: 210 17% 93%;              /* #ECEEF2 */
  --muted-foreground: 215 16% 47%;   /* #4E5969 */

  /* 边框 */
  --border: 220 13% 91%;             /* #E5E6EB */
  --input: 220 13% 91%;
  --ring: 219 100% 55%;

  /* 危险 */
  --destructive: 0 84% 60%;

  /* 顶栏 */
  --nav-bg: #1D2129;                 /* 深灰底（替代深蓝） */
  --nav-text: #FFFFFF;

  /* 圆角收小，ArcoDesign风格偏克制 */
  --radius: 0.5rem;                  /* 8px 全局圆角 */
}
```

**关键变更**：
- `--primary`: `215 48% 60%` → `219 100% 55%`（PCL蓝 → 字节蓝）
- `--nav-bg`: `#2B4C7E` → `#1D2129`（深蓝 → 深灰，更现代）
- `--background`: `#F5F7FA` → `#F7F8FA`（ArcoDesign 标准背景）
- `--radius`: `0.75rem` → `0.5rem`（12px → 8px，ArcoDesign 偏克制）

### 1.2 Tailwind 配置扩展

在 `tailwind.config.js` 中添加自定义颜色，确保与设计系统一致：

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#165DFF',
          hover: '#0E42D2',
          light: '#E8F3FF',
          lighter: '#F2F7FF',
        },
        success: { DEFAULT: '#00B42A', light: '#E8FFEA' },
        warning: { DEFAULT: '#FF7D00', light: '#FFF7E8' },
        danger: { DEFAULT: '#F53F3F', light: '#FFECE8' },
        text: {
          primary: '#1D2129',
          secondary: '#4E5969',
          tertiary: '#86909C',
          disabled: '#C9CDD4',
        },
        border: { DEFAULT: '#E5E6EB', light: '#F2F3F5' },
        surface: { DEFAULT: '#FFFFFF', secondary: '#F7F8FA', tertiary: '#F2F3F5' },
      },
      boxShadow: {
        'card': '0 1px 2px rgba(0,0,0,0.05)',
        'card-hover': '0 4px 12px rgba(0,0,0,0.08)',
        'dropdown': '0 8px 24px rgba(0,0,0,0.12)',
        'modal': '0 16px 48px rgba(0,0,0,0.16)',
      },
    },
  },
}
```

---

## 二、全局样式补充

在 `globals.css` 末尾追加：

```css
/* === ArcoDesign 风格滚动条 === */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #F7F8FA; }
::-webkit-scrollbar-thumb { background: #C9CDD4; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #86909C; }

/* === 全局选中态 === */
::selection { background: #E8F3FF; color: #0E42D2; }

/* === 输入框 focus 光环 === */
input:focus, textarea:focus, select:focus {
  box-shadow: 0 0 0 2px #E8F3FF;
  border-color: #165DFF;
}

/* === 代码块 === */
.prose pre {
  background: #1D2129;
  color: #E8E8E8;
  border-radius: 6px;
  font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.7;
}
.prose pre .token.keyword { color: #C678DD; }
.prose pre .token.string { color: #98C379; }
.prose pre .token.comment { color: #5C6370; font-style: italic; }
.prose pre .token.number { color: #D19A66; }
```

---

## 三、顶部导航栏重设计

### 3.1 布局

```
┌──────────────────────────────────────────────────────────────────┐
│  🔷 AICraft    对话  Skill  MCP  RAG  记忆  角色  模型     ─ □ ✕ │
│  56px 深灰底(#1D2129)                                           │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 实现要点

- 背景：`bg-[#1D2129]`，底部 `border-b border-white/5`
- 左侧 Logo：28×28 圆角方块 `rounded-md bg-gradient-to-br from-primary to-[#4080FF]`，内含白色 `<Cpu>` 图标
- 品牌名：`text-white font-medium text-sm ml-2`，"AICraft"
- Tab 项：不用圆角卡片，改用**下划线指示器**（ArcoDesign 风格）
  - 当前 Tab：`text-white border-b-2 border-white`
  - 非 Tab：`text-white/60 hover:text-white/80`，无下划线
  - padding：`px-4 py-[18px]`（上下各18px，撑满56px）
  - Tab 之间无 gap，紧密排列
- 右侧窗口控制按钮：`text-white/60 hover:text-white hover:bg-white/10`，关闭 hover `hover:bg-danger hover:text-white`

**代码示例**（导航栏 Tab）：
```jsx
<nav className="flex items-center h-14">
  {tabs.map(tab => (
    <button
      key={tab.id}
      onClick={() => setActiveTab(tab.id)}
      className={cn(
        "px-4 h-full text-sm font-medium transition-colors",
        activeTab === tab.id
          ? "text-white border-b-2 border-white"
          : "text-white/60 hover:text-white/80 border-b-2 border-transparent"
      )}
    >
      {tab.label}
    </button>
  ))}
</nav>
```

---

## 四、7个页面逐页美化

### 4.1 对话页

**当前问题**：消息气泡生硬，输入区简陋，缺乏层次感

**改动**：

1. **消息气泡**：
   - 用户消息：右对齐，`bg-primary-light (#E8F3FF) text-text-primary rounded-2xl rounded-tr-sm`
   - AI消息：左对齐，`bg-white border border-border-light rounded-2xl rounded-tl-sm shadow-card`
   - 消息间距：`space-y-4`，每条消息 `py-3 px-4`
   - AI头像：32×32 圆形 `bg-gradient-to-br from-primary to-[#4080FF]` + 白色 `<Bot>` 图标

2. **工具调用卡片**：
   - `<Card className="border-l-4 border-l-warning bg-warning-light/30">`
   - 头部：`🔧 工具调用 · {tool_name}` + `<Badge variant="secondary">` 运行中/完成
   - 参数/结果：`<Collapsible>`，默认折叠，`font-mono text-xs`

3. **输入区域**：
   - 外层：`bg-white border border-border rounded-xl shadow-card p-3`
   - Textarea：无边框无背景，`placeholder:text-text-tertiary`，focus时外层边框变色
   - 底部工具栏：`flex items-center gap-2 pt-2 border-t border-border-light`
   - Switch 标签：`text-xs text-text-secondary`，RAG/记忆
   - Select：Shadcn `<Select>` small size
   - 发送按钮：`<Button size="icon" className="rounded-lg">`，流式中变红色停止

4. **空状态**（新对话）：
   - 垂直居中，`text-center`
   - 大图标：64px `<MessageSquare className="text-text-disabled">`
   - 标题：`text-lg text-text-secondary` "开始新对话"
   - 描述：`text-sm text-text-tertiary` "输入消息，AI 将为你解答"

### 4.2 Skill 页

**改动**：

1. **页面标题区**：
   - `text-xl font-semibold text-text-primary` "Skill 管理"
   - 右侧 `<Button size="sm"><Plus className="w-4 h-4 mr-1" />添加 Skill</Button>`

2. **Skill 卡片**：
   - `<Card className="hover:shadow-card-hover transition-shadow">`
   - 布局：左侧图标区 + 中间信息区 + 右侧操作区
   - 图标区：40×40 `rounded-lg bg-primary-light`，内含 `<Zap className="text-primary">`
   - 信息区：名称 `font-medium text-text-primary` + 描述 `text-sm text-text-secondary line-clamp-2`
   - 操作区：`<Switch />` 启用/禁用 + `<Button variant="ghost" size="icon"><FolderOpen /></Button>`
   - 卡片间距：`grid grid-cols-1 md:grid-cols-2 gap-4`

3. **空状态**：
   - `<Zap className="w-16 h-16 text-text-disabled mb-4" />`
   - "暂无 Skill" + "点击右上角添加"

### 4.3 MCP 页

**改动**：

1. **MCP 卡片**：
   - `<Card className="hover:shadow-card-hover transition-shadow">`
   - 头部：名称 + 状态 `<Badge>` (已连接=success, 未连接=secondary, 错误=danger)
   - 类型：`<Badge variant="outline">` SSE / Stdio
   - 连接信息：`font-mono text-xs text-text-tertiary` URL 或命令
   - 工具列表：`<Collapsible>`，trigger 显示 "N 个工具"，内容列表 `text-sm space-y-1`
   - 操作栏：`<Switch />` + `<Button variant="outline" size="sm">` 连接/断开 + 删除
   - 卡片间距：`grid grid-cols-1 gap-4`

2. **添加 MCP 弹窗**：
   - `<Dialog>` + Shadcn 表单
   - 类型选择后，SSE 显示 URL 输入框，Stdio 显示命令+参数输入框
   - 底部：取消 + 确认添加

### 4.4 RAG 页

**改动**：

1. **RAG 卡片**：
   - `<Card className="hover:shadow-card-hover transition-shadow">`
   - 图标区：40×40 `rounded-lg bg-success-light`，内含 `<Database className="text-success">`
   - 信息区：名称 + 文件路径 `font-mono text-xs text-text-tertiary` + 文件数 `<Badge>`
   - 操作栏：`<Switch />` + `<Button variant="outline" size="sm">` 索引 + 删除
   - 索引状态：`<Badge>` 已索引(成功)/未索引(secondary)/索引中(warning + pulse动画)

2. **添加数据源弹窗**：
   - `<Dialog>` 标准表单

3. **空状态**：
   - `<Database className="w-16 h-16 text-text-disabled mb-4" />`

### 4.5 记忆页

**改动**：

1. **Tabs 布局**：
   - Shadcn `<Tabs>`，默认"笔记" Tab
   - Tab 样式：ArcoDesign 下划线风格（非圆角卡片）

2. **搜索栏**：
   - 顶部 `<Input placeholder="搜索记忆...">` + `<Search />` 图标前缀
   - `bg-white border-border`

3. **记忆项**：
   - 笔记：`<Card>` 左侧彩色边框 `border-l-4 border-l-primary`
   - 摘要：`<Card>` 左侧彩色边框 `border-l-4 border-l-warning`
   - 每项：标题 + 摘要预览(2行截断) + 时间戳 `text-xs text-text-tertiary` + 类型 `<Badge>`

4. **空状态**：
   - `<Brain className="w-16 h-16 text-text-disabled mb-4" />`

### 4.6 角色页

**改动**：

1. **角色卡片**：
   - `<Card className="hover:shadow-card-hover transition-shadow">`
   - `<Avatar>` 40×40 `bg-gradient-to-br from-primary/20 to-primary/5` + `<User className="text-primary">`
   - 名称 + 描述预览(1行截断)
   - 当前角色：`<Badge variant="default">` 当前
   - 操作：`<Button variant="outline" size="sm">` 查看详情 + 设为当前 + 编辑 + 删除

2. **创建/编辑角色弹窗**：
   - `<Dialog>` + `<Textarea rows={8}>` 角色内容

### 4.7 模型页

**改动**：

1. **模型卡片**：
   - `<Card className="hover:shadow-card-hover transition-shadow">`
   - `<Avatar>` 40×40 `bg-gradient-to-br from-primary to-[#4080FF]` + `<Cpu className="text-white">`
   - 名称 `font-semibold` + provider/model_id `font-mono text-xs text-text-secondary`
   - 状态：`<Badge>` 默认(default) / 已配置(secondary)
   - 操作：测试连接 + ⭐设为默认 + 🗑删除
   - 卡片间距：`grid grid-cols-1 md:grid-cols-2 gap-4`

2. **添加模型弹窗**：
   - `<Dialog>` 标准表单
   - Provider 下拉：OpenAI / DeepSeek / Anthropic / Ollama / 其他
   - API Base 输入框 placeholder 根据 Provider 自动变化

---

## 五、弹窗统一规范

所有弹窗统一使用 Shadcn `<Dialog>`，统一以下 className：

```jsx
<DialogContent className="sm:max-w-[480px]">
  <DialogHeader>
    <DialogTitle className="text-text-primary">{title}</DialogTitle>
  </DialogHeader>
  <div className="space-y-4 py-4">
    {/* 表单项，每项： */}
    <div className="space-y-2">
      <Label className="text-text-secondary">{label}</Label>
      <Input className="border-border" />
    </div>
  </div>
  <DialogFooter className="gap-2">
    <Button variant="outline">取消</Button>
    <Button>确认</Button>
  </DialogFooter>
</DialogContent>
```

---

## 六、动效规范（仅 CSS transition）

| 场景 | 实现 | 时长 |
|------|------|------|
| 卡片 hover 阴影 | `transition-shadow duration-200` | 200ms |
| 按钮 hover | `transition-colors duration-150` | 150ms |
| Tab 切换下划线 | `transition-all duration-200` | 200ms |
| 弹窗入场 | Shadcn Dialog 默认 | 200ms |
| 索引中脉冲 | `animate-pulse` | 2s |

**禁止**：JS 动画库、粒子特效、复杂 CSS 动画

---

## 七、执行步骤

### Step 1：全局色彩和样式
1. 修改 `globals.css` 的 CSS 变量（一全部替换）
2. 修改 `tailwind.config.js` 添加自定义颜色和阴影
3. 添加全局滚动条、focus 光环、代码块样式

### Step 2：导航栏重设计
1. 背景从 `#2B4C7E` 改为 `#1D2129`
2. Tab 从圆角卡片改为下划线指示器
3. 添加 Logo 方块 + 品牌名

### Step 3：逐页美化（按以下顺序）
1. 对话页（使用频率最高，优先处理）
2. 模型页
3. Skill 页
4. MCP 页
5. RAG 页
6. 记忆页
7. 角色页

### Step 4：验收
1. 启动 exe 确认所有页面正常渲染
2. 检查所有弹窗打开/关闭正常
3. 检查所有 Switch/Select/Button 交互正常
4. 确认打包体积无异常增长
5. VirusTotal 扫描新 exe

---

## 八、注意事项

1. **所有 UI 必须用 Shadcn 组件**，禁止手写 CSS 布局和弹窗
2. **禁止内联 style 对象**，全部用 Tailwind class
3. **主色 #165DFF 不可再改**，这是最终确定的品牌色
4. **圆角统一 8px**（`--radius: 0.5rem`），不再用 12px/16px/20px 大圆角
5. **每改完一个页面立即测试**，不要攒到最后一起测
6. **打包前确认 `sentence-transformers` 和 `torch` 已从 requirements.txt 移除**

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
