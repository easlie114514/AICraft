import { useState, useRef, useEffect } from 'react'
import { Check } from 'lucide-react'
import { useTheme, THEMES, type ThemeName } from '@/contexts/ThemeContext'

/** 渐变背景（无辅色的主题） */
function gradBg(c: string, cl: string, cd: string) {
  return `radial-gradient(circle at 35% 35%, ${cl}, ${c} 55%, ${cd})`
}

/** 对角线分割色球 — 用两个 clip-path 三角形拼成，避免 CSS gradient 渲染问题 */
function SplitBall({ topLeft, bottomRight }: { topLeft: string; bottomRight: string }) {
  return (
    <span className="absolute inset-0 rounded-full overflow-hidden">
      <span className="absolute inset-0" style={{ background: topLeft, clipPath: 'polygon(0 0, 100% 0, 0 100%)' }} />
      <span className="absolute inset-0" style={{ background: bottomRight, clipPath: 'polygon(100% 0, 100% 100%, 0 100%)' }} />
    </span>
  )
}

export default function ThemeSwitcher() {
  const { theme, setTheme } = useTheme()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // 点击外部关闭
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClick)
    }
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  const current = THEMES.find((t) => t.name === theme) ?? THEMES[0]

  return (
    <div ref={ref} className="relative flex items-center">
      <button
        onClick={() => setOpen(!open)}
        className="relative w-6 h-6 rounded-full border-2 border-white/30 hover:border-white/60 transition-colors cursor-pointer shrink-0"
        style={current.secondaryColor ? undefined : { background: gradBg(current.color, current.colorLight, current.colorDark) }}
        title={`主题: ${current.label}`}
      >
        {current.secondaryColor && <SplitBall topLeft={current.color} bottomRight={current.secondaryColor} />}
      </button>

      {open && (
        <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 bg-white rounded-xl shadow-dropdown border border-border p-1.5 z-50 flex gap-1.5 flex-wrap max-w-[320px]">
          {THEMES.map((t) => (
            <button
              key={t.name}
              onClick={() => { setTheme(t.name as ThemeName); setOpen(false) }}
              className="relative w-7 h-7 rounded-full border-2 transition-all cursor-pointer hover:scale-110 flex items-center justify-center"
              style={{
                borderColor: theme === t.name ? t.color : 'transparent',
                boxShadow: theme === t.name ? `0 0 0 2px #fff, 0 0 0 4px ${t.color}` : undefined,
                ...(t.secondaryColor ? {} : { background: gradBg(t.color, t.colorLight, t.colorDark) }),
              }}
              title={t.label}
            >
              {t.secondaryColor
                ? <SplitBall topLeft={t.color} bottomRight={t.secondaryColor} />
                : theme === t.name && (
                    <Check className="h-3.5 w-3.5 text-white drop-shadow-sm" strokeWidth={3} />
                  )
              }
              {t.secondaryColor && theme === t.name && (
                <Check className="relative z-10 h-3.5 w-3.5 text-white drop-shadow-sm" strokeWidth={3} />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
