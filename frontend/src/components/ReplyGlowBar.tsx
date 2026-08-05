"use client"

import { useState, useEffect, useRef, useCallback } from 'react'
import { cn } from '@/lib/utils'

interface Props {
  active: boolean
  variant?: 'bar' | 'bloom'
}

/**
 * 呼吸灯带 — 同一外层容器，内层样式不同：
 * - "bar"（条状）：整块区域填满主题色呼吸
 * - "bloom"（泛光）：区域内一条呼吸线 + 柔光泛光
 * AI 停止后走完当前呼吸周期再自然消失。
 */
export default function ReplyGlowBar({ active, variant = 'bar' }: Props) {
  const [breathing, setBreathing] = useState(false)
  const pendingStop = useRef(false)
  const innerRef = useRef<HTMLDivElement>(null)

  // 跟踪 active → 控制 breathing 启停
  useEffect(() => {
    if (active) {
      pendingStop.current = false
      setBreathing(true)
    } else if (breathing) {
      // 标记等待当前周期结束
      pendingStop.current = true
    }
  }, [active])

  // 监听动画周期结束
  const handleIteration = useCallback(() => {
    if (pendingStop.current) {
      pendingStop.current = false
      setBreathing(false)
    }
  }, [])

  const animClass = variant === 'bloom' ? 'glow-bloom' : 'glow-breathe'

  return (
    <div
      className="relative w-full h-[14px] rounded-b-[20px] overflow-hidden"
      aria-hidden
      style={{
        background: 'rgba(0,0,0,0.30)',
        boxShadow: 'inset 0 -1px 0 rgba(0,0,0,0.04)',
      }}
    >
      {variant === 'bloom' ? (
        /* ── 泛光：呼吸线 + 柔光 ── */
        <div
          ref={innerRef}
          className={cn('absolute inset-0', breathing ? animClass : 'opacity-0')}
          onAnimationIteration={handleIteration}
        >
          <div
            className="absolute inset-0"
            style={{
              background: 'radial-gradient(ellipse 85% 200% at 50% 100%, color-mix(in srgb, var(--theme-secondary, var(--theme-glow-bar)) 55%, transparent) 0%, color-mix(in srgb, var(--theme-secondary, var(--theme-glow-bar)) 30%, transparent) 40%, transparent 70%)',
            }}
          />
          <div
            className="absolute bottom-[2px] left-[20px] right-[20px] h-[2px] rounded-full"
            style={{
              background: 'var(--theme-secondary, var(--theme-glow-bar))',
              boxShadow: '0 0 8px var(--theme-secondary, var(--theme-glow-bar))',
            }}
          />
        </div>
      ) : (
        /* ── 条状：整块呼吸 ── */
        <div
          ref={innerRef}
          className={cn('absolute inset-0', breathing ? animClass : 'opacity-0')}
          onAnimationIteration={handleIteration}
          style={{
            background: 'var(--theme-secondary, var(--theme-glow-bar))',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.3)',
          }}
        />
      )}
    </div>
  )
}
