import { useState, useEffect, useRef, useCallback } from 'react'
import { Send, Square, RefreshCw, ArrowDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import ChatMessage from '@/components/ChatMessage'
import { useChat } from '@/hooks/useChat'
import { api } from '@/lib/api'

const SCROLL_NEAR_BOTTOM_THRESHOLD = 60

interface ModelOption {
  name: string
  model_id: string
  is_current?: boolean
}

interface RoleOption {
  name: string
  is_current?: boolean
}

export default function ChatPage() {
  const { messages, streaming, error, sendMessage, stopStreaming, resetChat } = useChat()
  const [input, setInput] = useState('')
  const [toggles, setToggles] = useState({ rag: false, memory: true, thinking: false })
  const [models, setModels] = useState<ModelOption[]>([])
  const [roles, setRoles] = useState<RoleOption[]>([])
  const [selectedModel, setSelectedModel] = useState('')
  const [selectedRole, setSelectedRole] = useState('')
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const [isNearBottom, setIsNearBottom] = useState(true)

  // ── Smart auto-scroll: once user scrolls up during streaming, stop following ──
  const userPausedScrollRef = useRef(false)
  const streamingRef = useRef(false)
  streamingRef.current = streaming

  // Reset the pause flag when streaming ends
  const prevStreamingRef = useRef(false)
  useEffect(() => {
    const wasStreaming = prevStreamingRef.current
    prevStreamingRef.current = streaming
    if (wasStreaming && !streaming) {
      // Stream just ended — reset pause for next round
      userPausedScrollRef.current = false
    }
  }, [streaming])

  // Load models and roles
  useEffect(() => {
    api.get<ModelOption[]>('/models').then(setModels).catch(() => {})
    api.get<RoleOption[]>('/roles').then(setRoles).catch(() => {})
  }, [])

  // Set defaults
  useEffect(() => {
    if (models.length && !selectedModel) {
      const cur = models.find((m) => m.is_current) || models[0]
      setSelectedModel(cur.model_id)
    }
  }, [models, selectedModel])

  useEffect(() => {
    if (roles.length && !selectedRole) {
      const cur = roles.find((r) => r.is_current) || roles[0]
      setSelectedRole(cur.name)
    }
  }, [roles, selectedRole])

  // Persist role choice to backend when user changes role
  useEffect(() => {
    if (selectedRole) {
      api.put('/roles/current', { name: selectedRole }).catch(() => {})
    }
  }, [selectedRole])

  // ── Scroll helpers ──

  const scrollToBottom = useCallback(() => {
    const el = viewportRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [])

  // Check if near bottom; if user scrolls away during streaming, pause auto-scroll
  const checkNearBottom = useCallback(() => {
    const el = viewportRef.current
    if (!el) return
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight
    const near = dist <= SCROLL_NEAR_BOTTOM_THRESHOLD
    setIsNearBottom(near)
    // User scrolled away during streaming → pause auto-follow until stream ends
    if (!near && streamingRef.current) {
      userPausedScrollRef.current = true
    }
  }, [])

  // Auto-scroll when messages change — but NOT if user has paused
  useEffect(() => {
    if (!userPausedScrollRef.current && isNearBottom) {
      requestAnimationFrame(scrollToBottom)
    }
  }, [messages, isNearBottom, scrollToBottom])

  // When streaming starts and user hasn't paused, scroll to bottom (catch late-arriving renders)
  useEffect(() => {
    if (streaming && !userPausedScrollRef.current) {
      const id = setTimeout(() => {
        if (!userPausedScrollRef.current && isNearBottom) scrollToBottom()
      }, 50)
      return () => clearTimeout(id)
    }
  }, [streaming, isNearBottom, scrollToBottom])

  const handleSend = () => {
    const text = input.trim()
    if (!text || streaming) return
    setInput('')
    // Reset pause and force scroll to bottom when user sends a message
    userPausedScrollRef.current = false
    setIsNearBottom(true)
    scrollToBottom()
    sendMessage(text, selectedModel, selectedRole, toggles)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const hasMessages = messages.length > 0

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden relative">
      {/* Messages */}
      <ScrollArea
        className="flex-1 min-h-0 px-4"
        viewportRef={(el: HTMLDivElement | null) => { viewportRef.current = el }}
        onScroll={checkNearBottom}
      >
        {!hasMessages ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground py-20">
            <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
              <Send className="h-7 w-7 text-primary/50" />
            </div>
            <p className="text-sm font-medium">AICraft</p>
            <p className="text-xs mt-1">选择模型和角色，开始对话</p>
          </div>
        ) : (
          <div className="py-4 space-y-0 relative">
            {messages
              .filter((msg) => msg.role !== 'tool_call' && msg.role !== 'tool_result')
              .map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}
            {error && (
              <div className="flex justify-center py-2">
                <span className="text-xs text-destructive bg-destructive/10 px-3 py-1.5 rounded-lg">
                  {error}
                </span>
              </div>
            )}
          </div>
        )}
      </ScrollArea>

      {/* Scroll-to-bottom floating button */}
      {!isNearBottom && hasMessages && (
        <div className="absolute bottom-[140px] left-1/2 -translate-x-1/2 z-10">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => { userPausedScrollRef.current = false; scrollToBottom(); setIsNearBottom(true) }}
            className="rounded-full shadow-lg h-8 w-8 p-0"
          >
            <ArrowDown className="h-4 w-4" />
          </Button>
        </div>
      )}

      <Separator />

      {/* Input Area */}
      <div className="shrink-0 p-4 space-y-3">
        {/* Toggles */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <Switch
              id="toggle-rag"
              className="rounded-xl"
              checked={toggles.rag}
              onCheckedChange={(v) => setToggles({ ...toggles, rag: v })}
            />
            <Label htmlFor="toggle-rag" className="text-xs text-muted-foreground cursor-pointer">RAG检索</Label>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              id="toggle-memory"
              className="rounded-xl"
              checked={toggles.memory}
              onCheckedChange={(v) => setToggles({ ...toggles, memory: v })}
            />
            <Label htmlFor="toggle-memory" className="text-xs text-muted-foreground cursor-pointer">记忆注入</Label>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              id="toggle-thinking"
              className="rounded-xl"
              checked={toggles.thinking}
              onCheckedChange={(v) => setToggles({ ...toggles, thinking: v })}
            />
            <Label htmlFor="toggle-thinking" className="text-xs text-muted-foreground cursor-pointer">深度思考</Label>
          </div>
        </div>

        {/* Input Row */}
        <div className="flex items-end gap-2">
          <Textarea
            placeholder="输入消息... (Shift+Enter 换行)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 min-h-[40px] max-h-[120px] rounded-[10px] resize-none"
            rows={1}
            disabled={streaming}
          />

          <Select value={selectedModel} onValueChange={(v) => setSelectedModel(v ?? '')}>
            <SelectTrigger className="w-[140px] h-10 rounded-[10px] text-xs">
              <SelectValue placeholder="模型" />
            </SelectTrigger>
            <SelectContent>
              {models.map((m) => (
                <SelectItem key={m.model_id} value={m.model_id} className="text-xs">
                  {m.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={selectedRole} onValueChange={(v) => setSelectedRole(v ?? '')}>
            <SelectTrigger className="w-[110px] h-10 rounded-[10px] text-xs">
              <SelectValue placeholder="角色" />
            </SelectTrigger>
            <SelectContent>
              {roles.map((r) => (
                <SelectItem key={r.name} value={r.name} className="text-xs">
                  {r.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {streaming ? (
            <Button variant="destructive" size="icon" onClick={stopStreaming} className="h-10 w-10 rounded-xl shrink-0">
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button size="icon" onClick={handleSend} disabled={!input.trim()} className="h-10 w-10 rounded-xl shrink-0">
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
