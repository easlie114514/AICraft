"use client"

import { Button } from '@/components/ui/button'

// ═══════════════════════════════════════════════════════════════
// 共享设置 UI 组件 — 被 SettingsPage、RAGPage 等页面复用
// ═══════════════════════════════════════════════════════════════

/** A single setting row — clean text label + control, no icon */
export function SettingRow({ title, description, children }: {
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-6 px-4 py-3.5">
      <div className="space-y-0.5 min-w-0">
        <span className="text-sm text-text-primary">{title}</span>
        {description && (
          <p className="text-xs text-text-tertiary leading-relaxed">{description}</p>
        )}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

/** Section label with icon, placed above a group of rows */
export function SectionLabel({ icon: Icon, title, description }: {
  icon: React.ComponentType<{ className?: string }>
  title: string
  description?: string
}) {
  return (
    <div className="flex items-center gap-2.5 mb-3 ml-1">
      <Icon className="w-4 h-4 text-text-secondary" />
      <div>
        <h3 className="text-sm font-medium text-text-primary">{title}</h3>
        {description && (
          <p className="text-xs text-text-tertiary">{description}</p>
        )}
      </div>
    </div>
  )
}

/** Number stepper with - / input / + buttons */
export function NumberStepper({ value, min, max, onChange }: {
  value: number
  min: number
  max: number
  onChange: (v: number) => void
}) {
  return (
    <div className="flex items-center gap-1">
      <Button
        variant="outline"
        size="icon"
        className="h-8 w-8"
        disabled={value <= min}
        onClick={() => onChange(value - 1)}
      >
        −
      </Button>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => {
          const v = parseInt(e.target.value, 10)
          if (!isNaN(v)) onChange(v)
        }}
        className="h-8 w-14 text-center text-sm border border-border rounded-lg bg-background text-text-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
      />
      <Button
        variant="outline"
        size="icon"
        className="h-8 w-8"
        disabled={value >= max}
        onClick={() => onChange(value + 1)}
      >
        +
      </Button>
    </div>
  )
}
