# 🎨 Design Brief: AICraft

**Generated:** 2026-07-14 | **Tool:** design-wizard | **Base System:** shadcn/ui

---

## 📋 Design Summary

| Dimension | Choice | Key Values |
|-----------|--------|------------|
| **Base System** | shadcn/ui | Headless + Tailwind, 与 base-ui/react 天然契合 |
| **Shape** | 温和圆角 (rounded) | 8px, ArcoDesign 克制风格 |
| **Colors** | electric-bold (紫罗兰) | Primary: #8B5CF6, 暖灰中性色 |
| **Typography** | 现代无衬线 | HarmonyOS Sans SC / PingFang SC |
| **Spacing** | 舒适 (standard) | 8px 基准 |
| **Elevation** | 微阴影 (subtle) | 卡片轻浮，不抢戏 |

---

## 🎯 Design Philosophy

**从企业工具 → 温暖 AI 伙伴**

| 维度 | 旧 | 新 | 变化理由 |
|------|-----|-----|---------|
| 默认主色 | #165DFF 字节蓝 | #8B5CF6 紫罗兰 | 蓝色=企业/银行，紫色=AI/创造 |
| 中性色系 | Slate 冷灰 | Stone 暖灰 | 暖灰降低工具冰冷感 |
| 背景色 | #F7F8FA | #FAFAF8 | 微暖底色更亲和 |
| 主题数 | 12 套 | 8 套精选 | 聚焦温暖+活力方向 |

---

## 🎯 Color Palette

**Primary (Violet):**
| 50 | 100 | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900 | 950 |
|----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
| #f5f3ff | #ede9fe | #ddd6fe | #c4b5fd | #a78bfa | #8b5cf6 | #7c3aed | #6d28d9 | #5b21b6 | #4c1d95 | #2e1065 |

**Neutral (Stone — Warm Gray):**
| 50 | 100 | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900 | 950 |
|----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
| #fafaf9 | #f5f5f4 | #e7e5e4 | #d6d3d1 | #a8a29e | #78716c | #57534e | #44403c | #292524 | #1c1917 | #0c0a09 |

**Semantic:**
- ✅ Success: #10B981
- ⚠️ Warning: #F59E0B
- ❌ Error: #EF4444
- ℹ️ Info: #3B82F6

---

## 🎨 8 套精选主题

| # | 名称 | 主色 | 导航栏 | 感觉 |
|---|------|------|--------|------|
| 1 | 暮光紫 ★默认 | #8B5CF6 | #2E1065 | AI 创造、现代科技 |
| 2 | 珊瑚橙 | #F0626E | #4A1A20 | 年轻活力、热情温暖 |
| 3 | 薄荷绿 | #10B981 | #064E3B | 清新自然、降低焦虑 |
| 4 | 暖阳金 | #F59E0B | #4A3000 | 温暖亲切、欢迎感 |
| 5 | 樱花粉 | #EC4899 | #4A1030 | 活泼创意、不拘束 |
| 6 | 天空蓝 | #0EA5E9 | #0C4A6E | 清爽干净、经典选择 |
| 7 | 极夜黑 | #6366F1 | #0F0F1A | 暗色沉浸、酷炫 |
| 8 | 森林绿 | #65A30D | #1A2E05 | 自然沉稳、护眼 |

---

## 🔲 Shape & Radius

保持现有 8px 基准不变：
- Button: 8px (rounded)
- Card: 8px
- Input: 8px
- Badge: 4px
- Modal: 12px

---

## 🌓 Elevation

保持现有 4 级阴影：
- Card: `0 1px 2px rgba(0,0,0,0.05)`
- Card Hover: `0 4px 12px rgba(0,0,0,0.08)`
- Dropdown: `0 8px 24px rgba(0,0,0,0.12)`
- Modal: `0 16px 48px rgba(0,0,0,0.16)`

---

## 🚀 组件兼容性

- ✅ **所有现有组件保持不变** — 只改 CSS 变量，不改 JSX 结构
- ✅ **Tailwind 类名不变** — `bg-primary`, `text-foreground` 等语义类自动跟随新变量
- ✅ **主题切换机制不变** — ThemeProvider + localStorage + 后端持久化完整保留
- ✅ **base-ui/react 组件不变** — 只通过 CSS 变量调整视觉效果
