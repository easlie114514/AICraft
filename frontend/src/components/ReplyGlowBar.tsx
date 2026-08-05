"use client"

import { cn } from '@/lib/utils'

interface Props {
  active: boolean
  variant?: 'bar' | 'bloom'
}

/**
 * 呼吸灯带 — 支持两种样式：
 * - "bar"（条状）：碗形区域，独立布局空间，底色与聊天区同色，active 时主题色呼吸
 * - "bloom"（泛光）：径向渐变椭圆泛光，悬浮于聊天区与输入区交界处
 */
export default function ReplyGlowBar({ active, variant = 'bar' }: Props) {
  if (variant === 'bloom') {
    return (
      <div className="relative h-0 w-full z-10 pointer-events-none">
        <div className="absolute -top-[10px] left-0 right-0">
          <div className={cn(
            'flex justify-center w-full h-4 px-[5%] transition-opacity duration-700',
            active ? 'opacity-100' : 'opacity-25',
          )}>
            <div
              className="w-full h-full"
              style={{
                background: 'radial-gradient(ellipse 50% 100% at 50% 100%, var(--theme-secondary, var(--theme-glow-bar)), transparent)',
                clipPath: 'inset(0 0 50% 0)',
                animation: 'glow-bloom 2s ease-in-out infinite',
              }}
            />
          </div>
        </div>
      </div>
    )
  }

  // "bar" — 条状碗形呼吸
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
