import { useState, useRef, useEffect } from 'react'
import { Check } from 'lucide-react'
import { useTheme, THEMES, type ThemeName } from '@/contexts/ThemeContext'

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
        className="w-6 h-6 rounded-full border-2 border-white/30 hover:border-white/60 transition-colors cursor-pointer shrink-0"
        style={{ backgroundColor: current.color }}
        title={`主题: ${current.label}`}
      />

      {open && (
        <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 bg-white rounded-xl shadow-dropdown border border-border p-1.5 z-50 flex gap-1.5">
          {THEMES.map((t) => (
            <button
              key={t.name}
              onClick={() => { setTheme(t.name as ThemeName); setOpen(false) }}
              className="relative w-7 h-7 rounded-full border-2 transition-all cursor-pointer hover:scale-110 flex items-center justify-center"
              style={{
                backgroundColor: t.color,
                borderColor: theme === t.name ? t.color : 'transparent',
                boxShadow: theme === t.name ? `0 0 0 2px #fff, 0 0 0 4px ${t.color}` : undefined,
              }}
              title={t.label}
            >
              {theme === t.name && (
                <Check className="h-3.5 w-3.5 text-white drop-shadow-sm" strokeWidth={3} />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
