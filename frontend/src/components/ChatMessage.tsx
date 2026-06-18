import MarkdownRenderer from '@/components/MarkdownRenderer'
import { cn } from '@/lib/utils'
import type { ChatMessage as ChatMessageType } from '@/hooks/useChat'

interface Props {
  message: ChatMessageType
}

export default function ChatMessage({ message }: Props) {
  const { role, content } = message

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
    <div className={cn('flex py-2', isUser ? 'justify-end' : 'justify-start')}>
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
