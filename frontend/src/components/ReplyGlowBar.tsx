"use client"

import { cn } from '@/lib/utils'

interface Props {
  active: boolean
}

/**
 * 碗状呼吸灯带 — 整块碗形区域作为呼吸单元。
 * 底色始终与聊天区一致，active 时叠加主题色呼吸光效。
 */
export default function ReplyGlowBar({ active }: Props) {
  return (
    <div
      className="relative w-full h-[14px] rounded-b-[20px] overflow-hidden"
      aria-hidden
      style={{
        background: 'rgba(225,225,230,0.55)',
        backdropFilter: 'blur(3px)',
        WebkitBackdropFilter: 'blur(3px)',
        boxShadow: 'inset 0 -1px 0 rgba(0,0,0,0.06)',
      }}
    >
      {/* 呼吸光效层：active 时主题色 ↔ 透明呼吸 */}
      <div
        className={cn(
          'absolute inset-0',
          active ? 'glow-breathe' : 'opacity-0',
        )}
        style={{
          background: 'var(--theme-secondary, var(--theme-glow-bar))',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.3)',
        }}
      />
    </div>
  )
}
