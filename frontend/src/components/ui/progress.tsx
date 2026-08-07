"use client"

import { cn } from "@/lib/utils"

interface ProgressProps {
  /** 0-100；null/undefined 时渲染不确定态（滑动动画） */
  value?: number | null
  className?: string
}

export function Progress({ value, className }: ProgressProps) {
  const indeterminate = value === undefined || value === null
  return (
    <div
      className={cn(
        "relative h-2 w-full overflow-hidden rounded-full bg-muted",
        className,
      )}
      role="progressbar"
      aria-valuenow={indeterminate ? undefined : Math.round(value!)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cn(
          "h-full rounded-full bg-primary transition-[width] duration-300 ease-out",
          indeterminate && "progress-indeterminate",
        )}
        style={
          indeterminate
            ? undefined
            : { width: `${Math.min(100, Math.max(0, value!))}%` }
        }
      />
    </div>
  )
}
