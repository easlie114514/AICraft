import MarkdownRenderer from '@/components/MarkdownRenderer'
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
  const { role, content, timestamp } = message

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
          <MarkdownRenderer content={content} />
        )}
      </div>
    </div>
  )
}
