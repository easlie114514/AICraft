import { useState, useEffect } from 'react'
import { Brain, ChevronDown } from 'lucide-react'
import MarkdownRenderer from '@/components/MarkdownRenderer'
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible'
import { cn } from '@/lib/utils'
import type { ChatMessage as ChatMessageType } from '@/hooks/useChat'

function formatTime(ts: number): string {
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
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

  if (role === 'system') {
    return (
      <div className="flex justify-center py-1.5">
        <span className="text-xs text-muted-foreground bg-muted/50 px-3 py-1 rounded-lg">
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
        <span className="text-[10px] text-muted-foreground/60">
          {formatTime(timestamp)}
        </span>
      </div>
      {/* Bubble */}
      <div
        className={cn(
          'max-w-[85%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed',
          isUser
            ? 'bg-primary/10 text-foreground'
            : 'bg-muted text-foreground'
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap break-words">{content}</p>
        ) : (
          <>
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
                  <div className="text-xs text-muted-foreground bg-muted/50 p-2.5 rounded-lg mb-2 max-h-64 overflow-auto border border-border/50">
                    <MarkdownRenderer content={thinking} />
                  </div>
                </CollapsibleContent>
              </Collapsible>
            ) : null}

            {/* 正式回复 */}
            {content ? <MarkdownRenderer content={content} /> : null}
          </>
        )}
      </div>
    </div>
  )
}
