"use client"

import { cn } from '@/lib/utils'

interface Props {
  active: boolean
}

export default function ReplyGlowBar({ active }: Props) {
  return (
    <div className={cn(
      'flex justify-center w-full h-4 px-[5%] transition-opacity duration-700',
      active ? 'opacity-100' : 'opacity-25'
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
  )
}
