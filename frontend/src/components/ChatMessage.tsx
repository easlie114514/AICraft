import { useState, useEffect, useCallback } from 'react'
import { Brain, ChevronDown, Copy, Check, ThumbsUp, ThumbsDown, RefreshCw } from 'lucide-react'
import MarkdownRenderer from '@/components/MarkdownRenderer'
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
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
  convId?: string
  userMessage?: string
  onRetry?: () => void
  streaming?: boolean
}

export default function ChatMessage({ message, convId, userMessage, onRetry, streaming }: Props) {
  const { id, role, content, timestamp, thinking, thinkingDuration } = message
  const isThinkingStreaming = thinking && thinking.trim() && thinkingDuration === undefined
  const hasThinking = thinking && thinking.trim()

  // ── 反馈状态 ──
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null)

  const handleFeedback = useCallback(async (rating: 'up' | 'down') => {
    if (feedback) return  // 已评价，不重复
    setFeedback(rating)
    try {
      await api.post('/feedback', {
        conv_id: convId || '',
        message_id: id,
        rating,
        message_preview: (content || '').slice(0, 200),
        user_message: (userMessage || '').slice(0, 200),
      })
    } catch {
      // 静默失败，不影响用户体验
    }
  }, [feedback, convId, id, content, userMessage])

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
          'max-w-[85%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed select-text',
          isUser
            ? 'bg-primary/10 text-text-primary rounded-tr-md'
            : 'bg-white border border-border/30 rounded-tl-md shadow-sm'
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap break-words select-text">{content}</p>
        ) : (
          <div className="select-text flex flex-col min-w-0">
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
            {content ? <MarkdownRenderer content={content} streaming={streaming} /> : null}
          </div>
        )}
      </div>

      {/* Copy & Feedback Buttons */}
      {content ? (
        <div className={cn('px-1 mt-0.5 flex items-center gap-1', isUser ? 'justify-end' : 'justify-start')}>
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

          {/* 反馈按钮 — 仅 AI 回复显示 */}
          {!isUser && (
            <>
              <span className="text-text-tertiary/30 mx-0.5">·</span>
              <button
                onClick={() => handleFeedback('up')}
                disabled={feedback !== null}
                className={cn(
                  'inline-flex items-center rounded-md px-1 py-0.5 text-xs transition-colors',
                  feedback === 'up'
                    ? 'text-green-500 bg-green-50'
                    : 'text-text-tertiary/40 hover:text-green-500 hover:bg-green-50/50'
                )}
                title="回答有帮助"
              >
                <ThumbsUp className="h-3 w-3" />
              </button>
              <button
                onClick={() => handleFeedback('down')}
                disabled={feedback !== null}
                className={cn(
                  'inline-flex items-center rounded-md px-1 py-0.5 text-xs transition-colors',
                  feedback === 'down'
                    ? 'text-red-500 bg-red-50'
                    : 'text-text-tertiary/40 hover:text-red-500 hover:bg-red-50/50'
                )}
                title="回答不够好"
              >
                <ThumbsDown className="h-3 w-3" />
              </button>
              {/* 点踩后显示"重新回答" */}
              {feedback === 'down' && onRetry && !message.readOnly && (
                <button
                  onClick={onRetry}
                  className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-orange-500 hover:text-orange-600 hover:bg-orange-50 transition-colors"
                >
                  <RefreshCw className="h-3 w-3" />
                  <span>换种方式</span>
                </button>
              )}
            </>
          )}
        </div>
      ) : null}
    </div>
  )
}
