import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'

export type ThemeName = 'sky' | 'mint' | 'sakura' | 'dusk-berry' | 'ocean-lime' | 'forest-gold' | 'royal-lemon'

interface ThemeInfo {
  name: ThemeName
  label: string
  color: string
  secondaryColor?: string
  colorLight: string
  colorLighter: string
  colorDark: string
  colorForeground: string
  ring: string
  navBg: string
  input: string
  glowBar: string
  background: string
}

export const THEMES: ThemeInfo[] = [
  // ─── 清新单色 ───
  { name: 'sky',         label: '天空蓝', color: '#0EA5E9', colorLight: '#F0F9FF', colorLighter: '#F7FDFF', colorDark: '#0284C7', colorForeground: '#FFFFFF', ring: '#0EA5E9', navBg: '#0C4A6E', input: '#E6F2F8', glowBar: '#38BDF8', background: '#F4F8FB' },
  { name: 'mint',        label: '薄荷绿', color: '#10B981', colorLight: '#ECFDF5', colorLighter: '#F6FEF9', colorDark: '#059669', colorForeground: '#FFFFFF', ring: '#10B981', navBg: '#064E3B', input: '#E6F5EE', glowBar: '#34D399', background: '#F3FAF6' },
  { name: 'sakura',      label: '樱花粉', color: '#EC4899', colorLight: '#FDF2F8', colorLighter: '#FEF7FB', colorDark: '#DB2777', colorForeground: '#FFFFFF', ring: '#EC4899', navBg: '#4A1030', input: '#F2E5ED', glowBar: '#F472B6', background: '#FBF6F9' },
  // ─── 高冲击拼色 — 主色（导航栏）= 主题名  |  辅色（按钮/标签线/卡片色条/泛光）= 另一色 ───
  { name: 'dusk-berry',  label: '暮海蓝', color: '#BC5A8C', secondaryColor: '#4F467D', colorLight: '#FBF5F8', colorLighter: '#FDF9FB', colorDark: '#A04470', colorForeground: '#FFFFFF', ring: '#BC5A8C', navBg: '#4F467D', input: '#EDE8EE', glowBar: '#BC5A8C', background: '#F7F4F8' },
  { name: 'ocean-lime',  label: '深海蓝', color: '#9FD60B', secondaryColor: '#2767C4', colorLight: '#F6FDE8', colorLighter: '#FBFEF4', colorDark: '#7FB000', colorForeground: '#0F172A', ring: '#9FD60B', navBg: '#2767C4', input: '#EAF0F8', glowBar: '#9FD60B', background: '#F8FAF4' },
  { name: 'forest-gold', label: '松林绿', color: '#C9A954', secondaryColor: '#145A33', colorLight: '#FBF8F1', colorLighter: '#FDFCF8', colorDark: '#AB8B36', colorForeground: '#0F172A', ring: '#C9A954', navBg: '#145A33', input: '#EAEDEA', glowBar: '#C9A954', background: '#FAF8F3' },
  { name: 'royal-lemon', label: '皇云紫', color: '#FFDC1E', secondaryColor: '#501E78', colorLight: '#FFFDEB', colorLighter: '#FFFEF5', colorDark: '#E5C500', colorForeground: '#0F172A', ring: '#FFDC1E', navBg: '#501E78', input: '#F2EDE8', glowBar: '#FFDC1E', background: '#FCFAF3' },
]

const THEME_CLASS_PREFIX = 'theme-'
const STORAGE_KEY = 'aicraft_theme'

function isValidTheme(v: string): v is ThemeName {
  return THEMES.some((t) => t.name === v)
}

function applyThemeClass(name: ThemeName) {
  const root = document.documentElement
  const target = THEME_CLASS_PREFIX + name
  const info = THEMES.find((t) => t.name === name) ?? THEMES[0]
  const s = root.style
  s.setProperty('--theme-primary', info.color, 'important')
  s.setProperty('--theme-primary-hover', info.colorDark, 'important')
  s.setProperty('--theme-primary-light', info.colorLight, 'important')
  s.setProperty('--theme-primary-lighter', info.colorLighter, 'important')
  s.setProperty('--theme-primary-foreground', info.colorForeground, 'important')
  s.setProperty('--theme-ring', info.ring, 'important')
  s.setProperty('--theme-nav-bg', info.navBg, 'important')
  s.setProperty('--theme-input', info.input, 'important')
  s.setProperty('--theme-glow-bar', info.glowBar, 'important')
  s.setProperty('--theme-secondary', info.secondaryColor || info.glowBar, 'important')
  s.setProperty('--theme-background', info.background, 'important')
  s.setProperty('--color-primary', info.color, 'important')
  s.setProperty('--color-primary-hover', info.colorDark, 'important')
  s.setProperty('--color-primary-light', info.colorLight, 'important')
  s.setProperty('--color-primary-lighter', info.colorLighter, 'important')
  s.setProperty('--color-ring', info.ring, 'important')
  s.setProperty('--color-nav-bg', info.navBg, 'important')
  s.setProperty('--color-input', info.input, 'important')
  s.setProperty('--color-glow-bar', info.glowBar, 'important')
  s.setProperty('--color-secondary-accent', info.secondaryColor || info.glowBar, 'important')
  s.setProperty('--color-background', info.background, 'important')
  if (root.classList.contains(target)) {
    try { localStorage.setItem(STORAGE_KEY, name) } catch { /* ignore */ }
    return
  }
  for (const t of THEMES) {
    root.classList.remove(THEME_CLASS_PREFIX + t.name)
  }
  root.classList.add(target)
  try { localStorage.setItem(STORAGE_KEY, name) } catch { /* ignore */ }
}

function getLocalTheme(): ThemeName | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && isValidTheme(stored)) return stored
  } catch { /* ignore */ }
  return null
}

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
  const localTheme = getLocalTheme()
  const [theme, setThemeState] = useState<ThemeName>(localTheme ?? 'sky')

  useEffect(() => {
    if (localTheme) {
      applyThemeClass(localTheme)
      saveThemeToBackend(localTheme)
    } else {
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
  }, [])

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
