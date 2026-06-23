import { useState, useEffect, useCallback } from 'react'
import { Brain, ChevronDown, Copy, Check } from 'lucide-react'
import MarkdownRenderer from '@/components/MarkdownRenderer'
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible'
import { cn } from '@/lib/utils'
import type { ChatMessage as ChatMessageType } from '@/hooks/useChat'

function formatTime(ts: number): string {
  const d = new Date(ts)
  const now = new Date()
  const sameDay = d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  const sameYear = d.getFullYear() === now.getFullYear()

  if (sameDay) {
    // 今天：只显示时间
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  if (sameYear) {
    // 同年不同天：月/日 时间
    return `${d.getMonth() + 1}/${d.getDate()} ` +
      d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  // 跨年：完整年月日 时间
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ` +
    d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

interface Props {
  message: ChatMessageType
}

export default function ChatMessage({ message }: Props) {
  const { role, content, timestamp, thinking, thinkingDuration } = message
  const isThinkingStreaming = thinking && thinking.trim() && thinkingDuration === undefined
  const hasThinking = thinking && thinking.trim()

  // 思考中默认展开，思考完成自动折叠
  const [thinkingOpen, setThinkingOpen] = useState(!!isThinkingStreaming)
  useEffect(() => {
    if (thinkingDuration !== undefined) {
      setThinkingOpen(false)
    }
  }, [thinkingDuration])

  // 一键复制
  const [copied, setCopied] = useState(false)
  const handleCopy = useCallback(async () => {
    const text = content || ''
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Fallback for older browsers or insecure contexts
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.left = '-9999px'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [content])

  if (role === 'divider') {
    return (
      <div className="flex items-center gap-3 py-3 px-1">
        <div className="flex-1 h-px bg-border/60" />
        <span className="text-[11px] text-muted-foreground/70 shrink-0 select-none">{content}</span>
        <div className="flex-1 h-px bg-border/60" />
      </div>
    )
  }

  if (role === 'system') {
    return (
      <div className="flex justify-center py-1.5">
        <span className="text-xs text-text-secondary bg-muted/50 px-3 py-1 rounded-lg">
          {content}
        </span>
      </div>
    )
  }

  if (role === 'tool_call' || role === 'tool_result') {
    return null // handled by ToolCallCard
  }

  const isUser = role === 'user'

  return (
    <div className={cn('flex flex-col py-1.5', isUser ? 'items-end' : 'items-start')}>
      {/* Timestamp */}
      <div className={cn('px-1 mb-0.5', isUser ? 'text-right' : 'text-left')}>
        <span className="text-[10px] text-text-tertiary/60">
          {formatTime(timestamp)}
        </span>
      </div>
      {/* Bubble */}
      <div
        className={cn(
          'max-w-[85%] px-4 py-2.5 rounded-xl text-sm leading-relaxed select-text',
          isUser
            ? 'bg-primary-light text-text-primary rounded-tr-sm'
            : 'bg-white border border-border-light rounded-tl-sm shadow-card'
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap break-words select-text">{content}</p>
        ) : (
          <div className="select-text">
            {/* Thinking 折叠区域 */}
            {hasThinking ? (
              <Collapsible open={thinkingOpen} onOpenChange={setThinkingOpen}>
                <CollapsibleTrigger className="flex items-center gap-1.5 w-full mb-2 text-xs text-muted-foreground hover:text-foreground transition-colors">
                  <Brain className="h-3.5 w-3.5" />
                  {isThinkingStreaming ? (
                    <span className="animate-pulse">正在思考...</span>
                  ) : (
                    <span>已思考 {(thinkingDuration! / 1000).toFixed(1)}s</span>
                  )}
                  <ChevronDown className={cn(
                    "h-3.5 w-3.5 transition-transform",
                    thinkingOpen && "rotate-180"
                  )} />
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <div className="text-xs text-muted-foreground bg-muted/50 p-2.5 rounded-lg mb-2 max-h-64 overflow-auto border border-border/50 select-text">
                    <MarkdownRenderer content={thinking} />
                  </div>
                </CollapsibleContent>
              </Collapsible>
            ) : null}

            {/* 正式回复 */}
            {content ? <MarkdownRenderer content={content} /> : null}
          </div>
        )}
      </div>

      {/* Copy Button */}
      {content ? (
        <div className={cn('px-1 mt-0.5', isUser ? 'text-right' : 'text-left')}>
          <button
            onClick={handleCopy}
            className={cn(
              'inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs',
              'text-text-tertiary/50 hover:text-text-secondary hover:bg-muted/50',
              'transition-colors'
            )}
          >
            {copied ? (
              <>
                <Check className="h-3 w-3 text-green-500" />
                <span className="text-green-500">已复制</span>
              </>
            ) : (
              <>
                <Copy className="h-3 w-3" />
                <span>复制</span>
              </>
            )}
          </button>
        </div>
      ) : null}
    </div>
  )
}
