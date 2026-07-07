import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'

export type ThemeName = 'blue' | 'green' | 'purple' | 'orange' | 'rose' | 'teal' | 'amber' | 'pink' | 'slate'

interface ThemeInfo {
  name: ThemeName
  label: string
  color: string
  colorLight: string
  colorDark: string
  navBg: string
  input: string
}

export const THEMES: ThemeInfo[] = [
  { name: 'blue',   label: '字节蓝', color: '#165DFF', colorLight: '#5C8CFF', colorDark: '#0E42D2', navBg: '#1E3A74', input: '#E4E8F0' },
  { name: 'green',  label: '竹叶绿', color: '#16A34A', colorLight: '#4ADE80', colorDark: '#15803D', navBg: '#184A2C', input: '#E2EBE5' },
  { name: 'purple', label: '暮光紫', color: '#7C3AED', colorLight: '#A78BFA', colorDark: '#6D28D9', navBg: '#36285E', input: '#E9E5F0' },
  { name: 'orange', label: '日落橙', color: '#EA580C', colorLight: '#FB923C', colorDark: '#C2410C', navBg: '#4C2A12', input: '#EDE7E1' },
  { name: 'rose',   label: '玫瑰红', color: '#DC2626', colorLight: '#F87171', colorDark: '#B91C1C', navBg: '#5C1E26', input: '#F0E6E7' },
  { name: 'teal',   label: '青碧色', color: '#0D9488', colorLight: '#2DD4BF', colorDark: '#0F766E', navBg: '#184A40', input: '#E4EDEB' },
  { name: 'amber',  label: '琥珀金', color: '#F59E0B', colorLight: '#FBBF24', colorDark: '#D97706', navBg: '#4C3614', input: '#EDEAE2' },
  { name: 'pink',   label: '樱花粉', color: '#DB2777', colorLight: '#F472B6', colorDark: '#BE185D', navBg: '#581A3E', input: '#F0E4EC' },
  { name: 'slate',  label: '石墨灰', color: '#475569', colorLight: '#64748B', colorDark: '#334155', navBg: '#384250', input: '#E5E8EC' },
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
  s.setProperty('--theme-primary', info.color)
  s.setProperty('--theme-primary-hover', info.colorDark)
  s.setProperty('--theme-primary-light', info.colorLight)
  s.setProperty('--theme-nav-bg', info.navBg)
  s.setProperty('--theme-input', info.input)
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
