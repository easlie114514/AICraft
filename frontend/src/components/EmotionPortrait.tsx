"use client"

import { cn } from '@/lib/utils'

const EMOTION_EMOJIS: Record<string, string> = {
  neutral: '😐',
  happy: '😊',
  thinking: '🤔',
  confused: '😕',
  working: '⚙️',
  concerned: '⚠️',
}

interface EmotionPortraitProps {
  roleName: string | null
  emotion: string | null
  available: string[]
  visible: boolean
  version?: number
  className?: string
}

export default function EmotionPortrait({
  roleName,
  emotion,
  available,
  visible,
  version = 0,
  className,
}: EmotionPortraitProps) {
  if (!roleName) {
    return null
  }

  const hasFrames = available.length > 0
  const currentEmotion = hasFrames
    ? ((emotion && available.includes(emotion)) ? emotion : available[0])
    : null

  return (
    <div className={cn(
      "shrink-0 flex items-center justify-center w-24 h-24",
      "border border-border rounded-xl bg-white shadow-card overflow-hidden",
      className,
    )}>
      {visible && currentEmotion ? (
        <img
          key={currentEmotion}
          src={`/api/roles/${encodeURIComponent(roleName)}/emotion/${currentEmotion}?v=${version}`}
          alt={currentEmotion}
          className="w-[80px] h-[80px] object-contain rounded-lg"
        />
      ) : hasFrames ? (
        <div className="w-16 h-16" />
      ) : (
        <span className="text-3xl text-muted-foreground/25">
          {EMOTION_EMOJIS.neutral}
        </span>
      )}
    </div>
  )
}
