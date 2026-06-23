import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'

export type ThemeName = 'blue' | 'green' | 'purple' | 'orange'

interface ThemeInfo {
  name: ThemeName
  label: string
  color: string
}

export const THEMES: ThemeInfo[] = [
  { name: 'blue',   label: '字节蓝', color: '#165DFF' },
  { name: 'green',  label: '竹叶绿', color: '#16A34A' },
  { name: 'purple', label: '暮光紫', color: '#7C3AED' },
  { name: 'orange', label: '日落橙', color: '#EA580C' },
]

const THEME_CLASS_PREFIX = 'theme-'
const STORAGE_KEY = 'aicraft_theme'

function isValidTheme(v: string): v is ThemeName {
  return THEMES.some((t) => t.name === v)
}

function applyThemeClass(name: ThemeName) {
  const root = document.documentElement
  for (const t of THEMES) {
    root.classList.remove(THEME_CLASS_PREFIX + t.name)
  }
  root.classList.add(THEME_CLASS_PREFIX + name)
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
      // 已有 localStorage 值 → 推送到后端（处理迁移：旧版本只写 localStorage）
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
