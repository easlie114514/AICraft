import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** 生成主题色变体卡片渐变背景 — 用 --theme-primary 与 --theme-nav-bg 混合
 *  @param enabled true=深色渐变+左上光照(启用态) false=暗色降饱和(关闭态)
 */
export function themeCardGradient(enabled: boolean = true): React.CSSProperties {
  if (!enabled) {
    // 关闭态：深色降饱和，近乎纯导航栏色，不加光照
    return {
      background: `linear-gradient(to bottom right, color-mix(in srgb, var(--theme-nav-bg) 92%, var(--theme-primary) 8%), color-mix(in srgb, var(--theme-nav-bg) 98%, var(--theme-primary) 2%))`,
    }
  }
  // 启用态：鲜艳渐变 + 左上角自然柔光
  return {
    background: `
      radial-gradient(ellipse 40% 50% at 18% 18%, rgba(255,255,255,0.10) 0%, transparent 60%),
      linear-gradient(to bottom right, color-mix(in srgb, var(--theme-nav-bg) 65%, var(--theme-primary) 35%), color-mix(in srgb, var(--theme-nav-bg) 88%, var(--theme-primary) 12%))
    `,
  }
}
