import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'

export type ThemeName = 'blue' | 'purple' | 'orange' | 'rose' | 'teal' | 'slate'
  | 'crimson' | 'neon' | 'dusk' | 'forest' | 'gold' | 'lava'

interface ThemeInfo {
  name: ThemeName
  label: string
  color: string
  secondaryColor?: string  // 高冲击配色辅色，用于对角线分割色球展示
  colorLight: string
  colorLighter: string
  colorDark: string
  ring: string
  navBg: string
  input: string
}

export const THEMES: ThemeInfo[] = [
  { name: 'blue',   label: '字节蓝', color: '#165DFF', colorLight: '#E8F3FF', colorLighter: '#F2F7FF', colorDark: '#0E42D2', ring: '#165DFF', navBg: '#1E3A74', input: '#E4E8F0' },
  { name: 'purple', label: '暮光紫', color: '#7C3AED', colorLight: '#F5F3FF', colorLighter: '#FAF9FF', colorDark: '#6D28D9', ring: '#7C3AED', navBg: '#36285E', input: '#E9E5F0' },
  { name: 'orange', label: '日落橙', color: '#EA580C', colorLight: '#FFF7ED', colorLighter: '#FFFBEB', colorDark: '#C2410C', ring: '#EA580C', navBg: '#4C2A12', input: '#EDE7E1' },
  { name: 'rose',   label: '玫瑰红', color: '#DC2626', colorLight: '#FEF2F2', colorLighter: '#FFF7F7', colorDark: '#B91C1C', ring: '#DC2626', navBg: '#5C1E26', input: '#F0E6E7' },
  { name: 'teal',   label: '青碧色', color: '#0D9488', colorLight: '#F0FDFA', colorLighter: '#F6FEFC', colorDark: '#0F766E', ring: '#0D9488', navBg: '#184A40', input: '#E4EDEB' },
  { name: 'slate',   label: '石墨灰', color: '#475569', colorLight: '#F1F5F9', colorLighter: '#F8FAFC', colorDark: '#334155', ring: '#475569', navBg: '#384250', input: '#E5E8EC' },
  { name: 'crimson', label: '警戒红', color: '#D10B1E', secondaryColor: '#111111', colorLight: '#FBEBED', colorLighter: '#FDF5F6', colorDark: '#A50918', ring: '#D10B1E', navBg: '#111111', input: '#E7E1E6' },
  { name: 'neon',    label: '电光桃', color: '#DF2C88', secondaryColor: '#000000', colorLight: '#FCEEF5', colorLighter: '#FEF7FA', colorDark: '#B61B6B', ring: '#DF2C88', navBg: '#000000', input: '#E8E2EB' },
  { name: 'dusk',    label: '暮海蓝', color: '#BC5A8C', secondaryColor: '#4F467D', colorLight: '#FAF2F6', colorLighter: '#FCF8FA', colorDark: '#9C406F', ring: '#BC5A8C', navBg: '#4F467D', input: '#E6E5EB' },
  { name: 'forest',  label: '松林绿', color: '#C9A954', secondaryColor: '#145A33', colorLight: '#FBF8F1', colorLighter: '#FDFCF8', colorDark: '#AB8B36', ring: '#C9A954', navBg: '#145A33', input: '#E6E9E8' },
  { name: 'gold',    label: '古铜金', color: '#D8B241', secondaryColor: '#000000', colorLight: '#FCF9F0', colorLighter: '#FDFCF7', colorDark: '#B69225', ring: '#D8B241', navBg: '#000000', input: '#E7E9E7' },
  { name: 'lava',    label: '熔岩橙', color: '#FF6B0A', secondaryColor: '#222222', colorLight: '#FFF3EB', colorLighter: '#FFF9F5', colorDark: '#D15400', ring: '#FF6B0A', navBg: '#222222', input: '#E9E6E5' },
]

const THEME_CLASS_PREFIX = 'theme-'
const STORAGE_KEY = 'aicraft_theme'

function isValidTheme(v: string): v is ThemeName {
  return THEMES.some((t) => t.name === v)
}

function applyThemeClass(name: ThemeName) {
  const root = document.documentElement
  const target = THEME_CLASS_PREFIX + name
  // 同步写入内联 CSS 变量（覆盖 index.html 的初始值，确保切换主题时即刻生效）
  const info = THEMES.find((t) => t.name === name) ?? THEMES[0]
  const s = root.style
  s.setProperty('--theme-primary', info.color, 'important')
  s.setProperty('--theme-primary-hover', info.colorDark, 'important')
  s.setProperty('--theme-primary-light', info.colorLight, 'important')
  s.setProperty('--theme-primary-lighter', info.colorLighter, 'important')
  s.setProperty('--theme-ring', info.ring, 'important')
  s.setProperty('--theme-nav-bg', info.navBg, 'important')
  s.setProperty('--theme-input', info.input, 'important')
  // 只在 class 不同时才切换，避免移除再添加造成的主题闪烁
  if (root.classList.contains(target)) {
    try { localStorage.setItem(STORAGE_KEY, name) } catch { /* ignore */ }
    return
  }
  for (const t of THEMES) {
    root.classList.remove(THEME_CLASS_PREFIX + t.name)
  }
  root.classList.add(target)
  try {
    localStorage.setItem(STORAGE_KEY, name)
  } catch { /* ignore */ }
}

function getLocalTheme(): ThemeName | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && isValidTheme(stored)) return stored
  } catch { /* ignore */ }
  return null
}

/** 从后端 API 加载持久化的主题设置 */
async function fetchThemeFromBackend(): Promise<ThemeName | null> {
  try {
    const res = await fetch('/api/settings')
    if (res.ok) {
      const data = await res.json()
      if (data.theme && isValidTheme(data.theme)) {
        return data.theme as ThemeName
      }
    }
  } catch { /* ignore */ }
  return null
}

/** 将主题设置保存到后端 API */
async function saveThemeToBackend(name: ThemeName) {
  try {
    await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme: name }),
    })
  } catch { /* ignore */ }
}

interface ThemeContextValue {
  theme: ThemeName
  setTheme: (name: ThemeName) => void
  themeInfo: ThemeInfo
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  // 先用 localStorage 同步初始化（快，避免闪烁）
  const localTheme = getLocalTheme()
  const [theme, setThemeState] = useState<ThemeName>(localTheme ?? 'blue')

  // 启动时同步后端持久化设置
  // 策略：localStorage 优先（用户之前的选择），首次启动无 localStorage 时从后端加载
  useEffect(() => {
    if (localTheme) {
      // 已有 localStorage 值 → 应用到 DOM + 推送到后端（处理迁移：旧版本只写 localStorage）
      applyThemeClass(localTheme)
      saveThemeToBackend(localTheme)
    } else {
      // 无 localStorage → 从后端加载
      fetchThemeFromBackend().then((serverTheme) => {
        if (serverTheme) {
          setThemeState((prev) => {
            if (prev !== serverTheme) {
              applyThemeClass(serverTheme)
              return serverTheme
            }
            return prev
          })
        }
      })
    }
  }, []) // 只在首次挂载时执行

  // 用户主动切换主题时 → 应用到 DOM + 双写持久化
  const setTheme = (name: ThemeName) => {
    setThemeState(name)
    applyThemeClass(name)
    saveThemeToBackend(name)
  }

  const themeInfo = THEMES.find((t) => t.name === theme) ?? THEMES[0]

  return (
    <ThemeContext.Provider value={{ theme, setTheme, themeInfo }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) {
    throw new Error('useTheme must be used within <ThemeProvider>')
  }
  return ctx
}
