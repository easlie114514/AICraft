"use client"

import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export type EmotionKey = 'neutral' | 'happy' | 'thinking' | 'confused' | 'working' | 'concerned'

const EMOTION_DEFS: { key: EmotionKey; label: string; icon: string }[] = [
  { key: 'neutral', label: '平静', icon: '😐' },
  { key: 'happy', label: '开心', icon: '😊' },
  { key: 'thinking', label: '思考', icon: '🤔' },
  { key: 'confused', label: '疑惑', icon: '😕' },
  { key: 'working', label: '工作', icon: '⚙️' },
  { key: 'concerned', label: '担心', icon: '⚠️' },
]

interface EmotionSlotGridProps extends ComponentProps<'div'> {
  roleName: string
  available: string[]
  version?: number
  onSlotClick: (key: EmotionKey) => void
}

export default function EmotionSlotGrid({
  roleName,
  available,
  version = 0,
  onSlotClick,
  className,
  ...props
}: EmotionSlotGridProps) {
  return (
    <div className={cn("grid grid-cols-3 gap-3", className)} {...props}>
      {EMOTION_DEFS.map(({ key, label, icon }) => {
        const configured = available.includes(key)
        return (
          <button
            key={key}
            type="button"
            onClick={() => onSlotClick(key)}
            className={cn(
              "flex flex-col items-center gap-1 p-2 rounded-lg transition-colors cursor-pointer border-2",
              configured
                ? "border-border bg-card hover:border-primary/40"
                : "border-dashed border-muted-foreground/25 hover:border-muted-foreground/50 bg-transparent"
            )}
          >
            {configured ? (
              <img
                src={`/api/roles/${encodeURIComponent(roleName)}/emotion/${key}?v=${version}`}
                alt={label}
                className="w-16 h-16 object-contain rounded"
              />
            ) : (
              <span className="w-16 h-16 flex items-center justify-center text-2xl text-muted-foreground/40">
                {icon}
              </span>
            )}
            <span className="text-xs text-text-secondary">{label}</span>
            <span className={cn(
              "text-[10px]",
              configured ? "text-green-600" : "text-muted-foreground/50"
            )}>
              {configured ? '已配' : '空'}
            </span>
          </button>
        )
      })}
    </div>
  )
}
