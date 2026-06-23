import { useState } from 'react'
import { Activity } from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Types ──

export interface TokenStats {
  input_tokens: number
  input_cache_hit_tokens: number
  input_cache_miss_tokens: number
  output_tokens: number
  total_cost: number
  request_count: number
}

export interface TokenStatsData {
  current: TokenStats
  lifetime: TokenStats
}

// ── Helpers ──

function fmt(n: number): string {
  return n.toLocaleString('en-US')
}

function fmtCost(cost: number): string {
  if (cost <= 0) return '--'
  if (cost < 0.01) return '< $0.01'
  return `$${cost.toFixed(4)}`
}

function fmtTokens(n: number): string {
  if (n <= 0) return '--'
  return `${fmt(n)} tokens`
}

// ── Component ──

interface TokenPanelProps {
  stats: TokenStatsData | null
  isOpen: boolean
  onToggle: () => void
}

export default function TokenPanel({ stats, isOpen, onToggle }: TokenPanelProps) {
  const [view, setView] = useState<'current' | 'lifetime'>('current')

  const s = stats ? (view === 'current' ? stats.current : stats.lifetime) : null
  const hasData = s && s.request_count > 0

  return (
    <div className="relative">
      {/* Toggle Button */}
      <button
        onClick={onToggle}
        className={cn(
          'h-10 w-12 rounded-lg flex items-center justify-center transition-colors shrink-0',
          isOpen
            ? 'bg-primary text-white'
            : 'bg-secondary text-text-secondary hover:text-primary hover:bg-primary-light'
        )}
        title="Token 用量"
      >
        <Activity className="h-4 w-4" />
      </button>

      {/* Popover Panel */}
      {isOpen && (
        <div
          className="absolute bottom-full right-0 mb-2 w-[240px] bg-white rounded-lg shadow-dropdown border border-border z-50"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-border-light">
            <span className="text-xs font-medium text-text-primary">Token 用量</span>
            <div className="flex items-center bg-muted rounded-md p-0.5">
              <button
                onClick={() => setView('current')}
                className={cn(
                  'px-2 py-0.5 text-[10px] rounded font-medium transition-colors',
                  view === 'current'
                    ? 'bg-white text-text-primary shadow-sm'
                    : 'text-text-tertiary hover:text-text-secondary'
                )}
              >
                本次
              </button>
              <button
                onClick={() => setView('lifetime')}
                className={cn(
                  'px-2 py-0.5 text-[10px] rounded font-medium transition-colors',
                  view === 'lifetime'
                    ? 'bg-white text-text-primary shadow-sm'
                    : 'text-text-tertiary hover:text-text-secondary'
                )}
              >
                累计
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="px-3 py-2 space-y-1.5 text-xs">
            {/* Input */}
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">输入</span>
              <span className="text-text-primary font-mono tabular-nums">
                {hasData ? fmtTokens(s!.input_tokens) : '--'}
              </span>
            </div>

            {/* Cache Hit */}
            <div className="flex items-center justify-between pl-3">
              <span className="text-[11px] text-success">├ 缓存命中</span>
              <span className="text-[11px] text-success font-mono tabular-nums">
                {hasData && s!.input_cache_hit_tokens > 0
                  ? fmtTokens(s!.input_cache_hit_tokens)
                  : '--'}
              </span>
            </div>

            {/* Cache Miss */}
            <div className="flex items-center justify-between pl-3">
              <span className="text-[11px] text-text-tertiary">└ 缓存未命中</span>
              <span className="text-[11px] text-text-tertiary font-mono tabular-nums">
                {hasData && s!.input_cache_miss_tokens > 0
                  ? fmtTokens(s!.input_cache_miss_tokens)
                  : '--'}
              </span>
            </div>

            {/* Output */}
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">输出</span>
              <span className="text-text-primary font-mono tabular-nums">
                {hasData ? fmtTokens(s!.output_tokens) : '--'}
              </span>
            </div>

            {/* Divider */}
            <div className="border-t border-border-light my-1" />

            {/* Request Count */}
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">请求次数</span>
              <span className="text-text-primary font-mono tabular-nums">
                {hasData ? fmt(s!.request_count) : '--'}
              </span>
            </div>

            {/* Cost */}
            <div className="flex items-center justify-between pt-0.5">
              <span className="text-text-secondary">费用</span>
              <span className="font-mono tabular-nums font-bold text-primary">
                {hasData ? fmtCost(s!.total_cost) : '--'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
